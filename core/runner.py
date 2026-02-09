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
from .utils import get_ffmpeg_path
from .film_ir_io import load_film_ir, film_ir_exists
from typing import Dict, Any, Optional, Tuple


def ensure_videos_dir(job_dir: Path) -> Path:
    videos_dir = job_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    return videos_dir


def get_remix_shot_data(job_dir: Path, shot_id: str, force_reload: bool = True) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict]]:
    """
    🎬 获取 Remix 后的分镜数据（强制从磁盘重新读取）

    检查 Film IR 是否有 remixed 层，如果有则返回：
    1. remixed i2v prompt 数据
    2. identity anchors (角色/环境锚点)
    3. visual style 配置

    ⚠️ 重要：force_reload=True 确保读取最新的 film_ir.json，
    以获取 Storyboard Chat 的所有修改。这是数据唯一事实来源。

    Returns:
        Tuple of (i2v_prompt_data, identity_anchors, visual_style) or (None, None, None)
    """
    if not film_ir_exists(job_dir):
        return None, None, None

    try:
        # 🔄 强制从磁盘重新读取，确保获取 Storyboard Chat 的最新修改
        if force_reload:
            import json
            film_ir_path = job_dir / "film_ir.json"
            if not film_ir_path.exists():
                return None, None, None
            with open(film_ir_path, 'r', encoding='utf-8') as f:
                ir = json.load(f)
            print(f"🔄 [Remix Data] Force reloaded film_ir.json from disk for {shot_id}")
        else:
            ir = load_film_ir(job_dir)

        if not ir:
            return None, None, None

        # 🎯 关键：remixedLayer 在 userIntent 下，不在 pillars 下
        remixed = ir.get("userIntent", {}).get("remixedLayer", {})

        if not remixed:
            print(f"⚠️ [Remix Data] No remixedLayer found in userIntent for {shot_id}")
            return None, None, None

        # 查找对应的 shot
        remixed_shots = remixed.get("shots", [])
        target_shot = None
        for shot in remixed_shots:
            if shot.get("shotId") == shot_id:
                target_shot = shot
                break

        if not target_shot:
            print(f"⚠️ [Remix Data] Shot {shot_id} not found in remixedLayer")
            return None, None, None

        # 获取 identity anchors
        identity_anchors = remixed.get("identityAnchors", {})

        # 获取 visual style 配置
        render_strategy = ir.get("pillars", {}).get("IV_renderStrategy", {})
        visual_style = render_strategy.get("visualStyleConfig", {})

        # 📋 打印关键数据用于调试
        i2v_prompt = target_shot.get("I2V_VideoGen", "") or target_shot.get("remixedI2VPrompt", "")
        print(f"🎬 [Remix Data] Found remixed data for {shot_id}")
        print(f"   📝 I2V Prompt: {i2v_prompt[:80]}..." if i2v_prompt else "   📝 I2V Prompt: (empty)")

        return target_shot, identity_anchors, visual_style

    except Exception as e:
        print(f"⚠️ [Remix Data] Error loading remix data: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def build_remix_prompt(remixed_shot: Dict, identity_anchors: Dict, visual_style: Dict) -> str:
    """
    🎨 构建基于 Remix 数据的生成 Prompt（增强版）

    整合：
    1. remixed shot 的 i2v prompt (优先级: I2V_VideoGen > visualDescription > remixedI2VPrompt)
    2. identity anchors 的详细描述
    3. visual style 的风格配置
    4. 🔗 语义桥梁：确保 Veo 参考第0帧的角色和光照一致性
    5. 🎬 动作对位：确保用户在 Chat 中修改的动作被准确注入
    """
    # 🎯 基础 prompt - 优先级获取
    base_prompt = (
        remixed_shot.get("I2V_VideoGen", "") or  # Storyboard Chat 修改后的 prompt
        remixed_shot.get("visualDescription", "") or  # 视觉描述
        remixed_shot.get("remixedI2VPrompt", "") or  # 旧版 remix prompt
        remixed_shot.get("subject", "")  # 最后回退
    )

    # 如果有完整的 i2v prompt 结构
    if remixed_shot.get("i2vPrompt"):
        i2v_data = remixed_shot.get("i2vPrompt", {})
        if isinstance(i2v_data, dict):
            base_prompt = i2v_data.get("prompt", base_prompt)
        elif isinstance(i2v_data, str):
            base_prompt = i2v_data

    # 🎬 提取动作描述（用户可能在 Chat 中修改了动作）
    action_description = remixed_shot.get("action", "") or remixed_shot.get("motionDescription", "")
    camera_movement = remixed_shot.get("cameraPreserved", {}).get("cameraMovement", "")

    # 构建 identity 描述
    identity_parts = []

    # 添加角色锚点
    characters = identity_anchors.get("characters", [])
    for char in characters:
        anchor_id = char.get("anchorId", "")
        # 检查这个 shot 是否使用了这个角色
        applied_anchors = remixed_shot.get("appliedAnchors", {}).get("characters", [])
        if anchor_id in applied_anchors or not applied_anchors:
            desc = char.get("detailedDescription", "")
            if desc:
                identity_parts.append(f"Character: {desc}")

    # 添加环境锚点
    environments = identity_anchors.get("environments", [])
    for env in environments:
        anchor_id = env.get("anchorId", "")
        applied_anchors = remixed_shot.get("appliedAnchors", {}).get("environments", [])
        if anchor_id in applied_anchors or not applied_anchors:
            desc = env.get("detailedDescription", "")
            if desc:
                identity_parts.append(f"Environment: {desc}")

    # 构建 visual style 描述
    style_parts = []
    if visual_style.get("artStyle"):
        style_parts.append(f"Art Style: {visual_style['artStyle']}")
    if visual_style.get("colorPalette"):
        style_parts.append(f"Color: {visual_style['colorPalette']}")
    if visual_style.get("lightingMood"):
        style_parts.append(f"Lighting: {visual_style['lightingMood']}")
    if visual_style.get("cameraStyle"):
        style_parts.append(f"Camera: {visual_style['cameraStyle']}")

    # 🔗 组合最终 prompt - 带语义桥梁
    final_parts = []

    # 1. 基础场景描述
    if base_prompt:
        final_parts.append(base_prompt)

    # 2. 🎬 动作对位（如果有用户修改的动作）
    if action_description:
        final_parts.append(f"[SPECIFIC ACTION]: {action_description}")

    # 3. 摄影机运动
    if camera_movement and camera_movement.lower() != "static":
        final_parts.append(f"[CAMERA MOVEMENT]: {camera_movement}")

    # 4. Identity anchors
    if identity_parts:
        final_parts.append("[CHARACTER/ENVIRONMENT DETAILS]")
        final_parts.extend(identity_parts)

    # 5. Visual style
    if style_parts:
        final_parts.append(f"[VISUAL STYLE]: {', '.join(style_parts)}")

    # 6. 🔗 语义桥梁 - Google 生态技巧，确保 Veo 参考第0帧
    semantic_bridge = (
        "CRITICAL: Maintaining consistent lighting, character appearance, and fine details "
        "from the provided reference image. The first frame must match the reference exactly, "
        "with natural motion flowing from that starting point."
    )
    final_parts.append(f"[CONSISTENCY]: {semantic_bridge}")

    return "\n\n".join(final_parts)


def get_effective_shot_data(job_dir: Path, wf: dict, shot: dict) -> Tuple[str, dict]:
    """
    🎯 获取有效的分镜数据（优先使用 Remix 数据）

    逻辑：
    1. 先检查是否有 remixed 层
    2. 如果有，使用 remixed prompt + identity anchors + visual style
    3. 如果没有，使用原始 workflow 的 description

    Returns:
        Tuple of (effective_prompt, effective_cinematography)
    """
    shot_id = shot.get("shot_id")

    # 尝试获取 remix 数据
    remixed_shot, identity_anchors, visual_style = get_remix_shot_data(job_dir, shot_id)

    if remixed_shot:
        # 使用 remix 数据
        effective_prompt = build_remix_prompt(remixed_shot, identity_anchors, visual_style)

        # 获取摄影参数 - 优先使用 remixed 的 camera 数据
        camera_data = remixed_shot.get("camera", {})
        if not camera_data:
            camera_data = remixed_shot.get("cameraPreserved", {})

        effective_cinema = {
            "shot_scale": camera_data.get("shotSize", shot.get("cinematography", {}).get("shot_scale", "")),
            "subject_frame_position": shot.get("cinematography", {}).get("subject_frame_position", ""),
            "subject_orientation": camera_data.get("cameraAngle", shot.get("cinematography", {}).get("subject_orientation", "")),
            "gaze_direction": shot.get("cinematography", {}).get("gaze_direction", ""),
            "motion_vector": camera_data.get("cameraMovement", shot.get("cinematography", {}).get("motion_vector", "static")),
            "camera_type": shot.get("cinematography", {}).get("camera_type", "")
        }

        print(f"✅ [Effective Data] Using REMIXED data for {shot_id}")
        return effective_prompt, effective_cinema
    else:
        # 使用原始数据
        effective_prompt = shot.get("description", "")
        effective_cinema = shot.get("cinematography", {})
        print(f"📋 [Effective Data] Using ORIGINAL workflow data for {shot_id}")
        return effective_prompt, effective_cinema


def ai_stylize_frame(job_dir: Path, wf: dict, shot: dict) -> str:
    """
    💡 使用 Imagen 4.0 或 Gemini 2.0 Image Gen 确保定妆图生成成功
    🎬 Cinematography Fidelity: Hard-coded enforcement of source shot parameters
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
    if api_key:
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})

    src = job_dir / shot["assets"]["first_frame"]
    dst = job_dir / "stylized_frames" / f"{shot['shot_id']}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists(): os.remove(dst)

    global_style = wf.get("global", {}).get("style_prompt", "Cinematic")

    # 🎬 获取有效数据（优先使用 Remix 数据）
    description, cinema = get_effective_shot_data(job_dir, wf, shot)

    # 🎬 Extract cinematography parameters for fidelity enforcement
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

    print(f"🎨 AI 正在生成定妆图: {shot['shot_id']}")

    try:
        # 使用 Gemini 3 Pro Image Preview (与三视图生成一致)
        print(f"📡 调用 Gemini 3 Pro Image (gemini-3-pro-image-preview)...")
        response = client.models.generate_images(
            model="gemini-3-pro-image-preview",
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
            print(f"✅ Gemini 3 Pro Image 生成成功！")
            return f"stylized_frames/{dst.name}"
    except Exception as e:
        print(f"❌ Gemini 3 Pro Image 调用失败: {str(e)[:100]}...")

    print("⚠️ 执行原图占位。")
    shutil.copyfile(src, dst)
    return f"stylized_frames/{dst.name}"


def mock_generate_video(job_dir: Path, shot: dict) -> str:
    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"
    if out_path.exists(): os.remove(out_path)
    src_video = job_dir / "input.mp4"
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg, "-y", "-i", str(src_video), "-t", "1.0", "-c", "copy", str(out_path)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"videos/{out_path.name}"


def veo_generate_video(job_dir: Path, wf: dict, shot: dict) -> str:
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
    if api_key:
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
    # 使用与 video_generator.py 相同的客户端初始化方式
    client = genai.Client(api_key=api_key)

    videos_dir = ensure_videos_dir(job_dir)
    out_path = videos_dir / f"{shot['shot_id']}.mp4"
    if out_path.exists(): os.remove(out_path)

    # 🎯 图片来源优先级：storyboard_frames > stylized_frames > original frames
    # storyboard_frames 是经过 Identity Anchor 加持的'定妆图'，Veo 必须以此为第0帧
    shot_id = shot['shot_id']
    img_path = None

    # 优先级 1: storyboard_frames (Remix 流程生成的定妆图)
    storyboard_frame = job_dir / "storyboard_frames" / f"{shot_id}.png"
    if storyboard_frame.exists():
        img_path = storyboard_frame
        print(f"📸 [Image Source] Using storyboard_frame for {shot_id}")

    # 优先级 2: stylized_frames (旧流程生成的风格化图)
    if not img_path:
        stylized_frame = job_dir / "stylized_frames" / f"{shot_id}.png"
        if stylized_frame.exists():
            img_path = stylized_frame
            print(f"📸 [Image Source] Using stylized_frame for {shot_id}")

    # 优先级 3: 从 assets 字段获取
    if not img_path:
        img_rel = shot.get("assets", {}).get("storyboard_frame") or shot.get("assets", {}).get("stylized_frame")
        if img_rel:
            img_path = job_dir / img_rel
            if img_path.exists():
                print(f"📸 [Image Source] Using asset path for {shot_id}: {img_rel}")
            else:
                img_path = None

    # 优先级 4: 回退到 AI 生成 stylized_frame
    if not img_path or not img_path.exists():
        print(f"⚠️ [Image Source] No pre-generated frame found for {shot_id}, generating stylized frame...")
        ai_stylize_frame(job_dir, wf, shot)
        img_path = job_dir / "stylized_frames" / f"{shot_id}.png"

    print(f"🚀 [Veo 3.1] 正在渲染分镜视频: {shot['shot_id']}")

    image_bytes = img_path.read_bytes()
    style = wf.get('global', {}).get('style_prompt', '')

    # 🎬 获取有效数据（优先使用 Remix 数据）
    description, cinema = get_effective_shot_data(job_dir, wf, shot)

    # 🎬 Extract cinematography parameters for video fidelity
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
                import random
                # 🎲 随机抖动：基础等待 + 5-15秒随机延迟，打破同步节奏
                base_wait = retry_wait_seconds * (attempt + 1)
                jitter = random.uniform(5, 15)
                wait_time = base_wait + jitter
                print(f"⚠️ 触发 RPM 限制 (429)，等待 {wait_time:.1f} 秒后重试 (基础 {base_wait}s + 抖动 {jitter:.1f}s) ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ Veo 失败: {str(e)}")
                raise e

    # 如果所有重试都失败
    raise RuntimeError(f"Veo 生成失败：已重试 {max_retries} 次")


def seedance_generate_video(job_dir: Path, wf: dict, shot: dict) -> str:
    """
    使用 Seedance 1.5 Pro API 生成视频

    文档: https://seedanceapi.org/docs
    - 支持 text-to-video 和 image-to-video
    - image_urls 必须是公网可访问的 URL（不支持 Base64）
    - 时长: 4/8/12 秒
    - 分辨率: 480p/720p
    - generate_audio: 启用 AI 音频生成（voiceover/音效/背景音乐）
    """
    api_key = os.getenv("SEEDANCE_API_KEY")
    if not api_key:
        raise RuntimeError("SEEDANCE_API_KEY 环境变量未设置")

    # 🔧 清理 API Key：移除不可见 Unicode 字符和空白
    # 这些字符可能在复制粘贴时被意外引入，导致 'latin-1' 编码错误
    api_key = api_key.strip()
    api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
    if not api_key:
        raise RuntimeError("SEEDANCE_API_KEY 清理后为空，请检查是否包含有效字符")

    # 获取公网 BASE_URL（Railway 部署时必须设置）
    base_url = os.getenv("BASE_URL", "").rstrip("/")
    if not base_url:
        print("⚠️ [Seedance] BASE_URL 未设置，将使用 text-to-video 模式")

    videos_dir = ensure_videos_dir(job_dir)
    shot_id = shot['shot_id']
    job_id = job_dir.name
    out_path = videos_dir / f"{shot_id}.mp4"
    if out_path.exists():
        os.remove(out_path)

    # 🔊 读取 Sound Design 配置（从 film_ir.json）
    sound_design = {}
    enable_audio = True  # 默认启用音频生成
    try:
        film_ir_path = job_dir / "film_ir.json"
        if film_ir_path.exists():
            import json
            with open(film_ir_path, 'r', encoding='utf-8') as f:
                film_ir = json.load(f)
            render_strategy = film_ir.get("pillars", {}).get("IV_renderStrategy", {})
            sound_design = render_strategy.get("soundDesignConfig", {})
            enable_audio = sound_design.get("enableAudioGeneration", True)
            print(f"🔊 [Seedance] Sound Design loaded: voice={sound_design.get('voiceStyle', 'N/A')}, tone={sound_design.get('voiceTone', 'N/A')}")
    except Exception as e:
        print(f"⚠️ [Seedance] Failed to load Sound Design config: {e}")

    # 🎯 图片来源优先级：storyboard_frames > stylized_frames > frames
    img_rel_path = None

    storyboard_frame = job_dir / "storyboard_frames" / f"{shot_id}.png"
    if storyboard_frame.exists():
        img_rel_path = f"storyboard_frames/{shot_id}.png"
        print(f"📸 [Seedance] Using storyboard_frame for {shot_id}")

    if not img_rel_path:
        stylized_frame = job_dir / "stylized_frames" / f"{shot_id}.png"
        if stylized_frame.exists():
            img_rel_path = f"stylized_frames/{shot_id}.png"
            print(f"📸 [Seedance] Using stylized_frame for {shot_id}")

    if not img_rel_path:
        original_frame = job_dir / "frames" / f"{shot_id}.png"
        if original_frame.exists():
            img_rel_path = f"frames/{shot_id}.png"
            print(f"📸 [Seedance] Using original frame for {shot_id}")

    # 构建公网图片 URL（如果有 BASE_URL）
    image_url = None
    if img_rel_path and base_url:
        image_url = f"{base_url}/assets/{job_id}/{img_rel_path}"
        print(f"🌐 [Seedance] Image URL: {image_url}")

    # 获取 prompt
    description, cinema = get_effective_shot_data(job_dir, wf, shot)
    style = wf.get('global', {}).get('style_prompt', '')

    # 🎤 获取该镜头的对白文本
    dialogue_text = shot.get('dialogue_text', '') or shot.get('dialogueText', '') or shot.get('dialogue', '')

    # 🎤 构建包含语音的 prompt
    voice_style = sound_design.get('voiceStyle', 'natural')
    voice_tone = sound_design.get('voiceTone', 'warm and friendly')

    # 构建 Seedance prompt
    prompt_parts = [description]

    # 🌐 强制英语语音指令
    prompt_parts.append("[IMPORTANT: All spoken dialogue and voiceover must be in English only. Do not use any other language.]")

    # 如果有对白，添加语音描述
    if dialogue_text and dialogue_text.strip():
        voice_desc = f'[The character naturally delivers the line: "{dialogue_text}" in a {voice_tone}, {voice_style} English voice.]'
        prompt_parts.append(voice_desc)
        print(f"🎤 [Seedance] Adding voiceover (English): {dialogue_text[:50]}...")

    prompt_parts.append(f"Style: {style}. Cinematic, high quality, smooth motion.")
    prompt = " ".join(prompt_parts)

    if len(prompt) > 2000:
        prompt = prompt[:2000]

    print(f"🚀 [Seedance 1.5 Pro] 正在生成视频: {shot_id}")
    print(f"   📝 Prompt: {prompt[:150]}...")
    print(f"   🔊 Audio generation: {'enabled' if enable_audio else 'disabled'}")

    # API 配置
    SEEDANCE_API_BASE = "https://seedanceapi.org/v1"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 🎬 Step 1: 构建请求参数（严格按照 seedanceapi.org 文档）
    generate_payload = {
        "prompt": prompt,
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "duration": "4",  # "4", "8", or "12"
        "generate_audio": enable_audio  # 启用 AI 音频生成
    }

    # 如果有公网图片 URL，使用 image-to-video 模式
    if image_url:
        generate_payload["image_urls"] = [image_url]  # 必须是数组，最多1张图
        print(f"🎬 [Seedance] Mode: image-to-video")
    else:
        print(f"🎬 [Seedance] Mode: text-to-video (no BASE_URL or image)")

    max_retries = 3
    retry_wait = 30

    for attempt in range(max_retries):
        try:
            # 提交任务
            print(f"📤 [Seedance] Sending request to {SEEDANCE_API_BASE}/generate")
            print(f"   📋 Payload keys: {list(generate_payload.keys())}")
            print(f"   🔑 Auth header: Bearer sk-***{api_key[-4:] if len(api_key) > 4 else '****'}")
            print(f"   🔑 API key length: {len(api_key)}, all ASCII: {api_key.isascii()}")

            # 🔧 验证 headers 可以被 latin-1 编码（HTTP/1.1 要求）
            try:
                for key, value in headers.items():
                    value.encode('latin-1')
            except UnicodeEncodeError as e:
                print(f"❌ [Encoding] Header encoding error in '{key}': {e}")
                # 尝试清理 header 值
                headers[key] = value.encode('ascii', 'ignore').decode('ascii')
                print(f"   🔧 Cleaned header: {key}={headers[key][:50]}...")

            response = requests.post(
                f"{SEEDANCE_API_BASE}/generate",
                headers=headers,
                json=generate_payload,
                timeout=60
            )

            print(f"📥 [Seedance] Response status: {response.status_code}")
            print(f"   📄 Response body: {response.text[:500]}")

            if response.status_code == 402:
                raise RuntimeError("Seedance 余额不足，请充值")

            if response.status_code == 401:
                raise RuntimeError(f"Seedance 认证失败，请检查 API Key: {response.text[:200]}")

            if response.status_code != 200:
                error_msg = response.text[:500]
                print(f"❌ [Seedance] API Error: {error_msg}")
                raise RuntimeError(f"Seedance API 错误 ({response.status_code}): {error_msg}")

            result = response.json()
            if result.get("code") != 200:
                raise RuntimeError(f"Seedance 返回错误: {result.get('message')}")

            task_id = result["data"]["task_id"]
            print(f"⏳ [Seedance] 任务已提交 (Task ID: {task_id})")

            # 🎬 Step 2: 轮询状态
            max_polls = 120  # 最多等待 10 分钟 (120 * 5s)
            for poll in range(max_polls):
                time.sleep(5)

                status_response = requests.get(
                    f"{SEEDANCE_API_BASE}/status",
                    headers=headers,
                    params={"task_id": task_id},
                    timeout=30
                )

                if status_response.status_code != 200:
                    print(f"   ⚠️ 状态查询失败: {status_response.status_code}")
                    continue

                status_data = status_response.json()
                task_status = status_data.get("data", {}).get("status", "")

                if task_status == "SUCCESS":
                    video_urls = status_data["data"].get("response", [])
                    if not video_urls:
                        raise RuntimeError("Seedance 返回成功但无视频 URL")

                    video_url = video_urls[0]
                    print(f"✅ [Seedance] 生成成功，正在下载...")

                    # 下载视频
                    video_response = requests.get(video_url, stream=True, timeout=120)
                    if video_response.status_code == 200:
                        with open(out_path, 'wb') as f:
                            for chunk in video_response.iter_content(chunk_size=1024*1024):
                                f.write(chunk)
                        print(f"💾 [Seedance] 视频已保存: {out_path}")
                        return f"videos/{out_path.name}"
                    else:
                        raise RuntimeError(f"视频下载失败: {video_response.status_code}")

                elif task_status == "FAILED":
                    error_msg = status_data["data"].get("error_message", "未知错误")
                    raise RuntimeError(f"Seedance 生成失败: {error_msg}")

                else:
                    # IN_PROGRESS 或其他状态，继续轮询
                    if poll % 6 == 0:  # 每 30 秒打印一次
                        print(f"   ⏳ 生成中... (轮询 {poll + 1})")

            raise RuntimeError("Seedance 生成超时 (10分钟)")

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "rate" in error_str or "too many" in error_str

            if is_rate_limit and attempt < max_retries - 1:
                import random
                jitter = random.uniform(5, 15)
                wait_time = retry_wait * (attempt + 1) + jitter
                print(f"⚠️ [Seedance] 触发限流，等待 {wait_time:.1f}s 后重试 ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ [Seedance] 失败: {str(e)}")
                raise e

    raise RuntimeError(f"Seedance 生成失败：已重试 {max_retries} 次")


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
            video_model = wf.get("global", {}).get("video_model", "seedance")  # 默认使用 Seedance
            if video_model == "veo":
                rel_video_path = veo_generate_video(job_dir, wf, shot)
            elif video_model == "seedance":
                rel_video_path = seedance_generate_video(job_dir, wf, shot)
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






