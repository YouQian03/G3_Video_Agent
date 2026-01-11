# core/runner.py
from pathlib import Path
import shutil
import subprocess
import time
import os
import requests 

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
    Veo 3.1 图生视频 - 最终修复版
    1. 使用 v1alpha 生成（必须）
    2. 使用 v1beta 下载（更稳定）
    3. 使用 requests params 字典避免 URL 拼接错误
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

    # 1. 初始化客户端 (生成阶段用 v1alpha)
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})

    # 2. 发起 Veo 请求
    print(f"🚀 发起 Veo 请求 (Shot: {shot['shot_id']})...")
    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview", 
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

    # 3. 轮询状态
    print(f"⏳ 任务已提交，Veo 正在生成视频 (约 1-3 分钟)...")
    while not operation.done:
        time.sleep(20)
        operation = client.operations.get(operation)
        print(f"⏳ 仍在生成中...")

    if operation.error:
        raise RuntimeError(f"Veo 后端报错: {operation.error}")

    # 4. 准备下载
    resp = operation.response
    video_obj = resp.generated_videos[0].video
    
    # file_id 通常是 "files/xxxx"
    file_id = getattr(video_obj, 'name', None)
    if not file_id and hasattr(video_obj, 'uri'):
        file_id = f"files/{video_obj.uri.split('/')[-1]}"

    if not file_id:
        raise RuntimeError(f"无法定位生成的视频文件: {video_obj}")

    # 5. 核心修复：使用 v1beta 端点和 requests 自动参数处理
    print(f"✅ 生成成功，正在通过 v1beta 稳定端点下载视频...")
    
    # 使用 v1beta 往往能解决 alpha 端点的 alt=media 解析 Bug
    download_url = f"https://generativelanguage.googleapis.com/v1beta/{file_id}"
    
    # 使用 params 字典，requests 会自动处理成 ?alt=media&key=...
    # 这种方式比字符串格式化更安全，不会出现 ? 和 & 混淆
    query_params = {
        'alt': 'media',
        'key': api_key
    }

    try:
        response = requests.get(download_url, params=query_params, stream=True)
        
        # 如果 v1beta 不通，再最后尝试一次 v1alpha
        if response.status_code != 200:
            print(f"⚠️ v1beta 下载失败 (Code: {response.status_code})，尝试 v1alpha...")
            alpha_url = f"https://generativelanguage.googleapis.com/v1alpha/{file_id}"
            response = requests.get(alpha_url, params=query_params, stream=True)

        if response.status_code == 200:
            with open(out_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024): # 1MB chunks
                    if chunk:
                        f.write(chunk)
            print(f"💾 视频生成并下载成功！本地路径: {out_path}")
        else:
            raise RuntimeError(f"下载依然失败。状态码: {response.status_code}, 详情: {response.text}")
            
    except Exception as e:
        print(f"❌ 下载过程发生致命错误: {e}")
        raise e

    return f"videos/{out_path.name}"


def run_stylize(job_dir: Path, wf: dict, target_shot: str | None = None) -> None:
    for shot in wf.get("shots", []):
        sid = shot.get("shot_id")
        if target_shot and sid != target_shot: continue
        status = shot.get("status", {}).get("stylize", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"): continue
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
        if target_shot and sid != target_shot: continue
        status = shot.get("status", {}).get("video_generate", "NOT_STARTED")
        if not target_shot and status not in ("NOT_STARTED", "FAILED"): continue
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
            print("❌ video_generate FAILED:")
            traceback.print_exc()
        save_workflow(job_dir, wf)


def run_pipeline(job_dir: Path, target_shot: str | None = None) -> None:
    wf = load_workflow(job_dir)
    run_stylize(job_dir, wf, target_shot=target_shot)
    wf = load_workflow(job_dir)
    run_video_generate(job_dir, wf, target_shot=target_shot)



