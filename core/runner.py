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
    🎬 Cinematography Fidelity: Hard-coded enforcement of source shot parameters
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

    # 🎬 Extract cinematography parameters for fidelity enforcement
    cinema = shot.get("cinematography", {})
    shot_scale = cinema.get("shot_scale", "")
    subject_position = cinema.get("subject_frame_position", "")
    subject_orientation = cinema.get("subject_orientation", "")
    gaze_direction = cinema.get("gaze_direction", "")
    motion_vector = cinema.get("motion_vector", "")

    # 🎯 Build cinematography constraint block
    cinema_constraints = []

    # 1️⃣ Shot Scale Mapping
    scale_instructions = {
        "EXTREME_WIDE": "EXTREME WIDE SHOT - Subject very small in frame, vast environment dominates",
        "WIDE": "WIDE SHOT - Full body visible, significant environment context",
        "MEDIUM_WIDE": "MEDIUM WIDE SHOT - Subject from knees up, environmental context",
        "MEDIUM": "MEDIUM SHOT - Subject from waist up, balanced framing",
        "MEDIUM_CLOSE": "MEDIUM CLOSE-UP - Subject from chest up, intimate but contextual",
        "CLOSE_UP": "CLOSE-UP - Face fills most of frame, minimal background",
        "EXTREME_CLOSE_UP": "EXTREME CLOSE-UP - Single feature (eyes, lips) fills frame"
    }
    if shot_scale and shot_scale in scale_instructions:
        cinema_constraints.append(f"📐 SHOT SCALE: {scale_instructions[shot_scale]}")

    # 2️⃣ Subject Position in Frame
    if subject_position:
        cinema_constraints.append(f"📍 FRAME POSITION: Subject MUST be positioned at {subject_position} of the 16:9 frame")

    # 3️⃣ Orientation & Facing
    if subject_orientation:
        orientation_map = {
            "facing-camera": "Subject facing directly toward camera (frontal view)",
            "back-to-camera": "Subject's back facing camera (rear view)",
            "profile-left": "Subject in left profile (nose pointing to frame left)",
            "profile-right": "Subject in right profile (nose pointing to frame right)",
            "three-quarter-left": "Subject in 3/4 view facing left (showing right side of face)",
            "three-quarter-right": "Subject in 3/4 view facing right (showing left side of face)"
        }
        orient_desc = orientation_map.get(subject_orientation, subject_orientation)
        cinema_constraints.append(f"🧭 BODY ORIENTATION: {orient_desc}")

    # 4️⃣ Gaze Direction
    if gaze_direction:
        gaze_map = {
            "looking-at-camera": "Eyes looking directly into camera lens",
            "looking-left": "Eyes directed toward the left side of frame",
            "looking-right": "Eyes directed toward the right side of frame",
            "looking-up": "Eyes directed upward",
            "looking-down": "Eyes directed downward",
            "looking-off-screen-left": "Eyes looking past the left edge of frame",
            "looking-off-screen-right": "Eyes looking past the right edge of frame"
        }
        gaze_desc = gaze_map.get(gaze_direction, gaze_direction)
        cinema_constraints.append(f"👁️ GAZE DIRECTION: {gaze_desc}")

    # 5️⃣ Motion Vector
    if motion_vector and motion_vector != "static":
        cinema_constraints.append(f"🏃 MOTION VECTOR: Capture mid-action of '{motion_vector}' - body pose and motion blur should indicate this movement")

    # Build final constraint string
    cinematography_block = ""
    if cinema_constraints:
        cinematography_block = "\n\n🎬 CINEMATOGRAPHY FIDELITY - MANDATORY CONSTRAINTS (from source shot):\n" + "\n".join(cinema_constraints) + "\n⚠️ These parameters are LOCKED and must be preserved exactly as specified."

    # 🎨 Conditional Design Elements: Only trigger graphic layouts if explicitly requested
    design_keywords = ['poster', 'layout', 'magazine', 'border', 'collage', 'graphic design', 'storyboard paper']
    style_lower = global_style.lower()
    is_design_style = any(kw in style_lower for kw in design_keywords)

    if is_design_style:
        # User explicitly requested a design/layout style
        prompt = f"""STYLIZED GRAPHIC DESIGN COMPOSITION.
Create a {global_style} layout with intentional design elements.
Subject: {description}.
Style: {global_style} - Apply graphic design aesthetics as requested.
Format: 16:9 aspect ratio with artistic layout elements.{cinematography_block}"""
    else:
        # 🎬 DEFAULT: Full-bleed cinematic film still using structured prompt format
        # Format: [Subject], [Action/Pose], [Environment], [Style & Atmosphere], [Lighting & Color], [Camera & Tech Specs]

        # Extract action/pose from motion vector
        action_pose = motion_vector if motion_vector and motion_vector != "static" else "in a natural pose"

        # Build structured prompt components
        subject_block = f"[SUBJECT]: {description}"
        action_block = f"[ACTION/POSE]: {action_pose}, captured mid-motion with dynamic energy"
        environment_block = "[ENVIRONMENT]: Immersive scene environment extending to all edges of the 16:9 frame, rich background details"
        style_block = f"[STYLE & ATMOSPHERE]: {global_style} aesthetic, visually striking, enhanced visual impact with refined details and textures"
        lighting_block = "[LIGHTING & COLOR]: Dramatic cinematic lighting, rich color grading, depth through light and shadow layers, volumetric atmosphere"
        tech_block = "[CAMERA & TECH]: 35mm cinematic lens, 8K ultra high resolution, shallow depth of field, natural bokeh, film grain texture"

        prompt = f"""PROFESSIONAL CINEMATIC FILM STILL - TEXT-TO-IMAGE GENERATION

{subject_block}
{action_block}
{environment_block}
{style_block}
{lighting_block}
{tech_block}
{cinematography_block}

COMPOSITION RULES:
- Full-bleed edge-to-edge rendering filling 100% of the 16:9 canvas
- ZERO borders, margins, or white space - render as if captured from cinema camera sensor
- Subject photographed as cinematic scene, NOT shrunk into centered box
- Professional cinematography with rule of thirds and depth of field
- ALL cinematography constraints above MUST be strictly followed

QUALITY ENHANCEMENT:
- More visually impactful than standard output
- Rich detail textures and refined material quality
- Dramatic light/shadow interplay for depth
- Cinematic color palette with professional grading

FORBIDDEN:
- Any white/black borders or margins
- Changing shot scale, subject position, orientation, or gaze from source
- Poster layouts, magazine compositions, or storyboard aesthetics
- Any graphic design elements unless explicitly in style prompt

--ar 16:9"""

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

    # 🎬 Extract cinematography parameters for video fidelity
    cinema = shot.get("cinematography", {})
    shot_scale = cinema.get("shot_scale", "")
    subject_position = cinema.get("subject_frame_position", "")
    subject_orientation = cinema.get("subject_orientation", "")
    gaze_direction = cinema.get("gaze_direction", "")
    motion_vector = cinema.get("motion_vector", "static")

    # Build video-specific cinematography constraints
    video_constraints = []
    if shot_scale:
        video_constraints.append(f"Maintain {shot_scale} framing throughout")
    if subject_position:
        video_constraints.append(f"Subject stays at {subject_position} of frame")
    if subject_orientation:
        video_constraints.append(f"Subject maintains {subject_orientation} body angle")
    if gaze_direction:
        video_constraints.append(f"Gaze direction: {gaze_direction}")

    constraints_str = ". ".join(video_constraints) if video_constraints else ""

    # 🎬 Structured Image-to-Video Prompt Format
    # Format: [Camera Movement], [Specific Action], [Physics Details], [Atmosphere Change]

    # Determine camera movement based on motion vector
    if motion_vector and motion_vector != "static":
        if "walking" in motion_vector or "running" in motion_vector:
            camera_movement = "subtle tracking shot following subject movement"
        elif "toward" in motion_vector:
            camera_movement = "gentle dolly back as subject approaches"
        elif "away" in motion_vector:
            camera_movement = "slow push in as subject recedes"
        else:
            camera_movement = "steady shot with minimal camera drift"
        specific_action = f"Subject performs: {motion_vector}"
    else:
        camera_movement = "locked static shot with subtle breathing movement"
        specific_action = "Subject maintains pose with natural micro-movements (breathing, blinking, subtle weight shifts)"

    # Physics details for realism
    physics_details = "natural physics: hair/fabric responds to movement, ambient particles float in light beams, subtle environmental motion (leaves, dust, reflections)"

    # Atmosphere continuity
    atmosphere_change = f"maintain {style} atmosphere throughout, consistent lighting evolution, seamless style continuity"

    prompt = f"""PROFESSIONAL IMAGE-TO-VIDEO GENERATION - 3-5 SECOND CINEMATIC CLIP

[CAMERA MOVEMENT]: {camera_movement}
[SPECIFIC ACTION]: {specific_action}
[PHYSICS DETAILS]: {physics_details}
[ATMOSPHERE]: {atmosphere_change}

SCENE CONTEXT: {description}
ART STYLE: {style} - Maintain CONSISTENT style across ALL frames

🎬 CINEMATOGRAPHY LOCK (from source shot - DO NOT CHANGE):
{constraints_str}

MOTION QUALITY REQUIREMENTS:
- High motion quality, cinematic fluidity
- Smooth interpolation between frames
- Subject position and composition MUST remain STABLE
- No sudden flips, mirror effects, or jarring camera changes
- Preserve exact shot scale and framing from reference image

PHYSICS ENHANCEMENT:
- Realistic material physics (cloth flow, hair dynamics)
- Environmental interaction (wind effects, light particles)
- Natural motion blur on moving elements
- Atmospheric depth continuity

CRITICAL: Cinematography parameters are LOCKED - preserve exactly as specified.
high motion quality, cinematic, professional cinematography"""

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

            # 防御性修复：file_id 可能自带 ?alt=media 或 ?key=...
            clean_file_id = file_id.split("?", 1)[0]

            print(f"✅ 生成成功，正在下载文件: {clean_file_id}")

            download_url = f"https://generativelanguage.googleapis.com/v1beta/{clean_file_id}"
            query_params = {
                "alt": "media",
                "key": api_key,
            }

            response = requests.get(
                download_url,
                params=query_params,
                stream=True,
            )

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






