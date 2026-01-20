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
    prompt = f"A professional stylized storyboard frame. Subject: {description}. Art Style: {global_style}. High resolution, 16:9 cinematic framing."

    print(f"🖼️  AI 正在尝试生成定妆图: {shot['shot_id']}")

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
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})

    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"
    if out_path.exists(): os.remove(out_path)

    img_rel = shot.get("assets", {}).get("stylized_frame") or f"stylized_frames/{shot['shot_id']}.png"
    img_path = job_dir / img_rel

    if not img_path.exists():
        ai_stylize_frame(job_dir, wf, shot)

    print(f"🚀 [Veo 3.1] 正在渲染分镜视频: {shot['shot_id']}")
    
    try:
        operation = client.models.generate_videos(
            model="models/veo-3.1-generate-preview", 
            prompt=f"Cinematic video, {shot.get('description', '')}. Style: {wf.get('global', {}).get('style_prompt', '')}.",
            image=types.Image(
                image_bytes=img_path.read_bytes(),
                mime_type="image/png"
            ),
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=6.0
            ),
        )

        while not operation.done:
            time.sleep(20)
            operation = client.operations.get(operation.name)
            print(f"⏳ 视频渲染中...")

        if operation.error:
            raise RuntimeError(f"Veo 后端报错: {operation.error}")

        resp = operation.response
        if resp is None or not hasattr(resp, 'generated_videos') or not resp.generated_videos:
            raise RuntimeError("Veo 任务完成但未返回视频数据。原因：可能触发了内容安全审核拦截。")

        # 💡 核心修复：处理 video 字段可能是 str 也可能是 Object 的情况
        video_output = resp.generated_videos[0].video
        file_id = None
        
        if isinstance(video_output, str):
            # 如果直接返回的是字符串 ID
            file_id = video_output
        else:
            # 如果返回的是对象，尝试多种取值方式
            file_id = getattr(video_output, 'name', None)
            if not file_id and hasattr(video_output, 'uri'):
                # 兼容 URI 格式: https://.../files/xyz -> files/xyz
                file_id = f"files/{video_output.uri.split('/')[-1]}"
        
        if not file_id:
            raise RuntimeError(f"无法从响应中解析有效的 File ID: {video_output}")

        # 确保 ID 格式正确 (必须包含 files/ 前缀)
        if '/' not in file_id:
            file_id = f"files/{file_id}"

        print(f"✅ 生成成功，正在下载文件: {file_id}")
        
        download_url = f"https://generativelanguage.googleapis.com/v1beta/{file_id}"
        query_params = {'alt': 'media', 'key': api_key}
        response = requests.get(download_url, params=query_params, stream=True)
        
        if response.status_code == 200:
            with open(out_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024): f.write(chunk)
            print(f"💾 视频生成成功: {out_path}")
            return f"videos/{out_path.name}"
        else:
            raise RuntimeError(f"下载失败: 状态码 {response.status_code}")
    except Exception as e:
        print(f"❌ Veo 失败: {str(e)}")
        raise e


def run_stylize(job_dir: Path, wf: dict, target_shot: str | None = None) -> None:
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot: continue
        status = shot.get("status", {}).get("stylize", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"): continue
        
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
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot: continue
        status = shot.get("status", {}).get("video_generate", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"): continue
        
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



