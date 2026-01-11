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
    Veo 3.1 图生视频 - 严格参数修复版
    根据 API 报错提示：durationSeconds 必须在 4-8 秒之间。
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

    # 2. 准备 Prompt (尽量简洁，符合预览版习惯)
    global_style = wf.get("global", {}).get("style_prompt", "")
    desc = shot.get("description", "")
    prompt = f"Cinematic scene: {desc}. Style: {global_style}. Smooth motion."

    # 3. 发起 Veo 请求
    print(f"🚀 发起 Veo 请求 (Shot: {shot['shot_id']})...")
    
    try:
        # 核心修正：
        # - 将 duration_seconds 设为 6 (在 4-8 的正中间)
        # - 确保 image 传递方式保持上一步验证通过的状态
        operation = client.models.generate_videos(
            model="veo-3.1-generate-preview", 
            prompt=prompt,
            image=types.Image(
                image_bytes=img_path.read_bytes(),
                mime_type="image/png"
            ),
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=6  # 明确设为 6，避开 5
            ),
        )
    except Exception as e:
        # 诚实的错误上报：如果参数没问题还报错，多半是 Google 接口不稳定
        print(f"❌ API 调用阶段崩溃: {e}")
        raise e

    # 4. 轮询状态
    print(f"⏳ 任务已提交，Veo 正在生成视频，请耐心等待 (约 1-2 分钟)...")
    while not operation.done:
        time.sleep(20)
        operation = client.operations.get(operation.name)
        print(f"⏳ 视频生成中...")

    if operation.error:
        raise RuntimeError(f"Veo 任务失败: {operation.error}")

    # 5. 下载结果
    resp = operation.response
    if not resp or not resp.generated_videos:
        raise RuntimeError(f"Veo 返回响应异常: {operation}")

    video_file = resp.generated_videos[0].video
    print(f"✅ 生成成功，正在下载文件...")
    
    # 尝试多种下载方式
    if hasattr(video_file, "name"):
        client.files.download(file=video_file.name, path=str(out_path))
    else:
        uri = getattr(video_file, "uri", None)
        if uri:
            file_name = uri.split('/')[-1]
            client.files.download(file=file_name, path=str(out_path))
        else:
            raise RuntimeError("无法找到可供下载的视频文件标识")

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



