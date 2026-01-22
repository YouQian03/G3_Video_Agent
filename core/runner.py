# core/runner.py
from pathlib import Path
import shutil
import subprocess
import time
import os
import requests 
import io
from PIL import Image

from .workflow_io import save_workflow, load_workflow


def ensure_videos_dir(job_dir: Path) -> Path:
    videos_dir = job_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    return videos_dir


def ai_stylize_frame(job_dir: Path, wf: dict, shot: dict) -> str:
    """
    💡 使用 Imagen 4.0 或 Gemini 2.0 Image Gen 确保定妆图生成成功
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    src = job_dir / shot["assets"]["first_frame"]
    dst = job_dir / "stylized_frames" / f"{shot['shot_id']}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists(): os.remove(dst)

    global_style = wf.get("global", {}).get("style_prompt", "Cinematic")
    description = shot.get("description", "")

    # 🎬 风格强控：使用强力变换指令，确保 AI 大胆改变风格
    prompt = f"""TOTAL VISUAL TRANSFORMATION REQUIRED.
Hyper-stylized storyboard frame with COMPLETE aesthetic overhaul.
Subject: {description}.
Art Style: {global_style} - Apply this style AGGRESSIVELY and BOLDLY.
Requirements: High resolution, 16:9 cinematic framing, dramatic lighting, professional composition.
IMPORTANT: Do NOT preserve original appearance. FULLY transform into the specified art style."""

    print(f"️  AI 正在尝试生成定妆图: {shot['shot_id']}")

    try:
        print(f"📡 尝试调用 Imagen 4.0 (models/imagen-4.0-generate-001)...")
        response = client.models.generate_images(
            model="models/imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9"
            )
        )
        if response.generated_images:
            gen_img = response.generated_images[0]
            if hasattr(gen_img.image, 'save'):
                gen_img.image.save(dst)
            else:
                with open(dst, 'wb') as f: f.write(gen_img.image.image_bytes)
            print(f"✅ 使用 Imagen 4.0 生成成功！")
            return f"stylized_frames/{dst.name}"
    except Exception as e:
        print(f"⚠️ Imagen 4.0 调用失败: {str(e)[:100]}...")

    try:
        print(f"📡 尝试调用集成生图模型 (models/gemini-2.0-flash-exp-image-generation)...")
        response = client.models.generate_content(
            model="models/gemini-2.0-flash-exp-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )
        for part in response.parts:
            if part.inline_data is not None:
                img = Image.open(io.BytesIO(part.inline_data.data))
                img.save(dst)
                print(f"✅ 使用 Gemini 2.0 集成模型生成成功！")
                return f"stylized_frames/{dst.name}"
    except Exception as e:
        print(f"❌ 所有生图模型均失败: {str(e)[:100]}...")

    print("⚠️ 执行原图占位。")
    shutil.copyfile(src, dst)
    return f"stylized_frames/{dst.name}"


def mock_generate_video(job_dir: Path, shot: dict) -> str:
    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"
    if out_path.exists(): os.remove(out_path)
    src_video = job_dir / "input.mp4"
    ffmpeg = "/opt/homebrew/bin/ffmpeg"
    cmd = [ffmpeg, "-y", "-i", str(src_video), "-t", "1.0", "-c", "copy", str(out_path)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"videos/{out_path.name}"


def veo_generate_video(job_dir: Path, wf: dict, shot: dict) -> str:
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    # 使用与 video_generator.py 相同的客户端初始化方式
    client = genai.Client(api_key=api_key)

    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"
    if out_path.exists(): os.remove(out_path)

    img_rel = shot.get("assets", {}).get("stylized_frame") or f"stylized_frames/{shot['shot_id']}.png"
    img_path = job_dir / img_rel

    if not img_path.exists():
        ai_stylize_frame(job_dir, wf, shot)

    print(f"🚀 [Veo 3.1] 正在渲染分镜视频: {shot['shot_id']}")

    image_bytes = img_path.read_bytes()
    description = shot.get('description', '')
    style = wf.get('global', {}).get('style_prompt', '')

    # 🎬 风格强控：确保视频生成保持一致性和风格化
    prompt = f"""Cinematic video with CONSISTENT visual style throughout.
Scene: {description}.
Art Style: {style} - Maintain this style CONSISTENTLY across all frames.
Requirements: Smooth motion, professional cinematography, dramatic lighting.
CRITICAL: Keep subject position and composition STABLE. No sudden flips or mirror effects."""

    # 🔄 自愈式重试逻辑：遇到 429 错误时自动等待并重试
    max_retries = 3
    retry_wait_seconds = 60

    for attempt in range(max_retries):
        try:
            # image 作为独立参数传递，不在 config 内
            operation = client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt,
                image=types.Image(
                    image_bytes=image_bytes,
                    mime_type="image/png"
                ),
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9"
                )
            )

            print(f"⏳ 视频正在云端渲染 (Operation ID: {operation.name})")

            poll_count = 0
            max_polls = 60  # 20 minutes max
            while not operation.done:
                poll_count += 1
                if poll_count > max_polls:
                    raise RuntimeError(f"Veo 轮询超时: 已等待超过 20 分钟")
                print(f"⏳ 视频渲染中... (轮询 {poll_count})")
                time.sleep(20)
                operation = client.operations.get(operation)

            # 检查错误
            if operation.error:
                raise RuntimeError(f"Veo 后端报错: {operation.error}")

            # 检查结果
            if not operation.result or not operation.result.generated_videos:
                raise RuntimeError("Veo 任务完成但未返回视频数据。原因：可能触发了内容安全审核拦截。")

            generated_video = operation.result.generated_videos[0]

            # 优先使用 SDK 原生 save 方法
            try:
                generated_video.video.save(str(out_path))
                print(f"💾 视频生成成功 (SDK save): {out_path}")
                return f"videos/{out_path.name}"
            except Exception as save_err:
                print(f"⚠️ SDK save 失败 ({save_err})，尝试手动下载...")

            # 备用：手动下载
            file_id = None
            video_obj = generated_video.video if hasattr(generated_video, 'video') else generated_video

            if hasattr(video_obj, 'name') and video_obj.name:
                file_id = video_obj.name if "/" in video_obj.name else f"files/{video_obj.name}"
            elif hasattr(video_obj, 'uri') and video_obj.uri:
                file_id = f"files/{video_obj.uri.split('/')[-1]}"

            if not file_id:
                raise RuntimeError(f"无法从响应中解析有效的 File ID: {type(video_obj).__name__}")

            print(f"✅ 生成成功，正在下载文件: {file_id}")

            download_url = f"https://generativelanguage.googleapis.com/v1beta/{file_id}"
            query_params = {'alt': 'media', 'key': api_key}
            response = requests.get(download_url, params=query_params, stream=True)

            if response.status_code == 200:
                with open(out_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024): f.write(chunk)
                print(f"💾 视频生成成功 (手动下载): {out_path}")
                return f"videos/{out_path.name}"
            else:
                raise RuntimeError(f"下载失败: 状态码 {response.status_code}")

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "rate" in error_str or "quota" in error_str or "resource_exhausted" in error_str

            if is_rate_limit and attempt < max_retries - 1:
                wait_time = retry_wait_seconds * (attempt + 1)  # 递增等待时间
                print(f"⚠️ 触发 RPM 限制 (429)，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ Veo 失败: {str(e)}")
                raise e

    # 如果所有重试都失败
    raise RuntimeError(f"Veo 生成失败：已重试 {max_retries} 次")


def run_stylize(job_dir: Path, wf: dict, target_shot: str | None = None) -> None:
    shots_to_process = []
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot: continue
        status = shot.get("status", {}).get("stylize", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"): continue
        shots_to_process.append(shot)

    for idx, shot in enumerate(shots_to_process):
        sid = shot.get("shot_id")

        # 🚦 RPM 限流：批量执行时，每个分镜之间休眠 35 秒
        if idx > 0 and target_shot is None:
            print(f"⏳ RPM 限流：等待 35 秒后处理下一个分镜...")
            time.sleep(35)

        shot.setdefault("status", {})["stylize"] = "RUNNING"
        save_workflow(job_dir, wf)
        try:
            rel_path = ai_stylize_frame(job_dir, wf, shot)
            shot.setdefault("assets", {})["stylized_frame"] = rel_path
            shot["status"]["stylize"] = "SUCCESS"
            print(f"✅ Stylize SUCCESS: {sid}")
        except Exception as e:
            shot["status"]["stylize"] = "FAILED"
            shot.setdefault("errors", {})["stylize"] = str(e)
        save_workflow(job_dir, wf)


def run_video_generate(job_dir: Path, wf: dict, target_shot: str | None = None) -> None:
    shots_to_process = []
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot: continue
        status = shot.get("status", {}).get("video_generate", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"): continue
        shots_to_process.append(shot)

    for idx, shot in enumerate(shots_to_process):
        sid = shot.get("shot_id")

        # 🚦 RPM 限流：批量执行时，每个分镜之间休眠 35 秒
        if idx > 0 and target_shot is None:
            print(f"⏳ RPM 限流：等待 35 秒后处理下一个分镜...")
            time.sleep(35)

        shot.setdefault("status", {})["video_generate"] = "RUNNING"
        save_workflow(job_dir, wf)
        try:
            video_model = wf.get("global", {}).get("video_model", "mock")
            if video_model == "veo":
                rel_video_path = veo_generate_video(job_dir, wf, shot)
            else:
                rel_video_path = mock_generate_video(job_dir, shot)
            shot.setdefault("assets", {})["video"] = rel_video_path
            shot["status"]["video_generate"] = "SUCCESS"
            print(f"✅ Video SUCCESS: {sid}")
        except Exception as e:
            shot["status"]["video_generate"] = "FAILED"
            shot.setdefault("errors", {})["video_generate"] = str(e)
            print(f"❌ Video FAILED: {sid} -> {e}")
        save_workflow(job_dir, wf)


def run_pipeline(job_dir: Path, target_shot: str | None = None) -> None:
    wf = load_workflow(job_dir)
    run_stylize(job_dir, wf, target_shot=target_shot)
    wf = load_workflow(job_dir)
    run_video_generate(job_dir, wf, target_shot=target_shot)






