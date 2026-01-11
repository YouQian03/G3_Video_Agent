# core/runner.py
from pathlib import Path
import shutil
import subprocess
import time
import os

from .workflow_io import save_workflow, load_workflow


def ensure_videos_dir(job_dir: Path) -> Path:
    videos_dir = job_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    return videos_dir


def mock_stylize_frame(job_dir: Path, shot: dict) -> str:
    src = job_dir / shot["assets"]["first_frame"]
    if not src.exists():
        raise FileNotFoundError(f"找不到 first_frame：{src}")

    dst = job_dir / "stylized_frames" / f"{shot['shot_id']}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return f"stylized_frames/{dst.name}"


def mock_generate_video(job_dir: Path, shot: dict) -> str:
    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"
    src_video = job_dir / "input.mp4"
    if not src_video.exists():
        raise FileNotFoundError(f"找不到源视频：{src_video}")
    ffmpeg = "/opt/homebrew/bin/ffmpeg"
    cmd = [
        ffmpeg, "-y",
        "-i", str(src_video),
        "-t", "1.0",
        "-c", "copy",
        str(out_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"videos/{out_path.name}"


def veo_generate_video(job_dir: Path, wf: dict, shot: dict) -> str:
    """
    Veo 3.1 图生视频 - 最终修正版
    1. 修正 Polling 逻辑：直接传递 operation 对象
    2. duration_seconds 设为 6.0
    3. 使用 image_bytes 结构
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("没有检测到 GEMINI_API_KEY 环境变量")

    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"

    img_rel = shot.get("assets", {}).get("stylized_frame")
    if not img_rel:
        raise RuntimeError("shot 缺少 assets.stylized_frame")
    img_path = job_dir / img_rel

    # 1. 初始化客户端
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})

    # 2. 准备 Prompt
    global_style = wf.get("global", {}).get("style_prompt", "")
    desc = shot.get("description", "")
    prompt = f"Cinematic video, {desc}. Style: {global_style}."

    # 3. 发起 Veo 请求
    print(f"🚀 发起 Veo 请求 (Shot: {shot['shot_id']})...")
    
    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview", 
        prompt=prompt,
        image=types.Image(
            image_bytes=img_path.read_bytes(),
            mime_type="image/png"
        ),
        config=types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=6.0
        ),
    )

    # 4. 轮询状态 - 修复点
    print(f"⏳ 任务已提交，Veo 正在生成视频，请耐心等待 (约 1-3 分钟)...")
    while not operation.done:
        time.sleep(20)
        # 注意这里：直接传入 operation 对象，不要加 .name
        operation = client.operations.get(operation)
        print(f"⏳ 仍在生成中...")

    if operation.error:
        raise RuntimeError(f"Veo 后端报错: {operation.error}")

    # 5. 下载结果
    resp = operation.response
    if not resp or not resp.generated_videos:
        raise RuntimeError(f"Veo 未返回视频数据")

    video_obj = resp.generated_videos[0].video
    print(f"✅ 生成成功，正在下载到: {out_path}")
    
    # 使用 SDK 的文件下载功能
    if hasattr(video_obj, "name"):
        client.files.download(file=video_obj.name, path=str(out_path))
    elif hasattr(video_obj, "uri"):
        fname = video_obj.uri.split('/')[-1]
        client.files.download(file=fname, path=str(out_path))
    else:
        raise RuntimeError("无法下载视频：返回对象缺失标识符")

    return f"videos/{out_path.name}"


def run_stylize(job_dir: Path, wf: dict, target_shot: str | None = None) -> None:
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot:
            continue
        status = shot.get("status", {}).get("stylize", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"):
            continue

        shot.setdefault("status", {})["stylize"] = "RUNNING"
        save_workflow(job_dir, wf)

        try:
            rel_path = mock_stylize_frame(job_dir, shot)
            shot.setdefault("assets", {})["stylized_frame"] = rel_path
            shot["status"]["stylize"] = "SUCCESS"
            print(f"✅ stylize SUCCESS: {sid} -> {rel_path}")
        except Exception as e:
            shot["status"]["stylize"] = "FAILED"
            shot.setdefault("errors", {})["stylize"] = str(e)
            print(f"❌ stylize FAILED: {sid} -> {e}")
        save_workflow(job_dir, wf)


def run_video_generate(job_dir: Path, wf: dict, target_shot: str | None = None) -> None:
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot:
            continue
        status = shot.get("status", {}).get("video_generate", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"):
            continue

        shot.setdefault("status", {})["video_generate"] = "RUNNING"
        save_workflow(job_dir, wf)

        try:
            video_model = wf.get("global", {}).get("video_model", "mock")
            if video_model == "veo":
                print("🔥 USING VEO PATH")
                rel_video_path = veo_generate_video(job_dir, wf, shot)
            else:
                rel_video_path = mock_generate_video(job_dir, shot)

            shot.setdefault("assets", {})["video"] = rel_video_path
            shot["status"]["video_generate"] = "SUCCESS"
            print(f"✅ video_generate SUCCESS: {sid} -> {rel_video_path}")
        except Exception as e:
            import traceback
            shot["status"]["video_generate"] = "FAILED"
            shot.setdefault("errors", {})["video_generate"] = repr(e)
            print("❌ video_generate FAILED (full traceback below):")
            traceback.print_exc()
        save_workflow(job_dir, wf)


def run_pipeline(job_dir: Path, target_shot: str | None = None) -> None:
    wf = load_workflow(job_dir)
    run_stylize(job_dir, wf, target_shot=target_shot)
    wf = load_workflow(job_dir)
    run_video_generate(job_dir, wf, target_shot=target_shot)



