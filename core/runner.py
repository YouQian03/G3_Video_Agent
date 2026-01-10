# core/runner.py
from pathlib import Path
import shutil
import subprocess
import time

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
    """
    Demo 版：用 input.mp4 的前 1 秒做占位视频，验证 runner 的工作方式。
    """
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
    Veo 3.1 图生视频（官方写法：types.Image.from_file）
    - stylized_frame 作为 opening frame
    - 先做最小验证：5 秒、1 个视频
    """
    import os
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
    if not img_path.exists():
        raise FileNotFoundError(f"找不到 stylized_frame：{img_path}")

    global_style = wf.get("global", {}).get("style_prompt", "")
    desc = shot.get("description", "")

    prompt = (
        "Use the reference image as the opening frame of the video, fully retaining its visual texture.\n"
        f"Scene: {desc}\n"
        f"Style: {global_style}\n"
        "Camera: slow cinematic push-in.\n"
    )

    # 关键：用官方推荐的方式读取本地图片（会自动推断 mimeType）
    image = types.Image.from_bytes(
    data=img_path.read_bytes(),
    mime_type="image/png",
)


    client = genai.Client(api_key=api_key)

    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        image=image,
        config=types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=5,
            enhance_prompt=True,
        ),
    )

    # 轮询 operation（官方示例写法）
    while not getattr(operation, "done", False):
        time.sleep(20)
        operation = client.operations.get(operation)  # :contentReference[oaicite:2]{index=2}

    resp = getattr(operation, "response", None)
    if not resp or not getattr(resp, "generated_videos", None):
        raise RuntimeError(f"Veo 返回为空：{operation}")

    video = resp.generated_videos[0].video

    # 尽量保存到本地：不同版本 SDK video 对象接口可能略有差异
    if hasattr(video, "save"):
        video.save(str(out_path))
    else:
        # 兜底：至少把对象返回信息打印出来，避免你“啥也没拿到”
        raise RuntimeError(f"SDK 返回 video 对象不支持 save(): {video}")

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
        shot.setdefault("errors", {})["stylize"] = None
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
        shot.setdefault("errors", {})["video_generate"] = None
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
            shot["status"]["video_generate"] = "FAILED"
            shot.setdefault("errors", {})["video_generate"] = str(e)
            print(f"❌ video_generate FAILED: {sid} -> {e}")

        save_workflow(job_dir, wf)


def run_pipeline(job_dir: Path, target_shot: str | None = None) -> None:
    wf = load_workflow(job_dir)
    run_stylize(job_dir, wf, target_shot=target_shot)
    wf = load_workflow(job_dir)
    run_video_generate(job_dir, wf, target_shot=target_shot)



