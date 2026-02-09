# app.py
import os

# 🔑 加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env")
except ImportError:
    print("⚠️ python-dotenv not installed, using system environment variables")

import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import re
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union

from core.workflow_manager import WorkflowManager
from core.agent_engine import AgentEngine
from core.film_ir_manager import FilmIRManager
from core.film_ir_io import load_film_ir, film_ir_exists

# Base URL for asset links - use environment variable in production
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

app = FastAPI(title="AI 导演工作台 API / SocialSaver Backend")


# ============================================================
# SocialSaver 数据格式转换函数
# ============================================================

def parse_time_to_seconds(time_value) -> float:
    """将时间值转换为秒数，支持 'MM:SS', 'HH:MM:SS' 格式或数字"""
    if time_value is None:
        return 0.0
    if isinstance(time_value, (int, float)):
        return float(time_value)
    if isinstance(time_value, str):
        time_value = time_value.strip()
        if not time_value:
            return 0.0
        # 尝试解析 MM:SS 或 HH:MM:SS 格式
        if ':' in time_value:
            parts = time_value.split(':')
            try:
                if len(parts) == 2:  # MM:SS
                    return float(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:  # HH:MM:SS
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            except ValueError:
                return 0.0
        # 尝试直接转换为数字
        try:
            return float(time_value)
        except ValueError:
            return 0.0
    return 0.0

def convert_shot_to_socialsaver(shot: Dict[str, Any], job_id: str, base_url: str = "") -> Dict[str, Any]:
    """
    将 ReTake 的 shot 格式转换为 SocialSaver 的 StoryboardShot 格式
    """
    # 提取 shot_number (shot_01 -> 1)
    shot_id = shot.get("shot_id", "shot_01")
    shot_number = int(re.search(r'\d+', shot_id).group()) if re.search(r'\d+', shot_id) else 1

    # 提取描述（去除摄影参数标签）
    description = shot.get("description", "")
    # 去除 [SCALE: ...] [POSITION: ...] 等标签，保留纯叙事
    visual_description = re.sub(r'\[(?:SCALE|POSITION|ORIENTATION|GAZE|MOTION):[^\]]*\]', '', description).strip()

    # 获取摄影参数
    cinematography = shot.get("cinematography", {})

    # 获取资源路径
    assets = shot.get("assets", {})
    first_frame = assets.get("first_frame", "")
    if first_frame and base_url:
        first_frame = f"{base_url}/assets/{job_id}/{first_frame}"

    # 获取扩展字段（新增的 lighting, music, dialogue）
    # 这些可能在 storyboard.json 原始数据中

    # 计算时间
    start_seconds = parse_time_to_seconds(shot.get("start_time", 0))
    end_seconds = parse_time_to_seconds(shot.get("end_time", 0))
    duration_seconds = end_seconds - start_seconds

    return {
        "shotNumber": shot_number,
        "shotId": shot_id,  # 添加 shotId 用于角色/场景匹配
        "firstFrameImage": first_frame,
        # 🎬 frame_description -> visualDescription (首帧描述)
        "visualDescription": shot.get("frame_description", "") or visual_description,
        # 🎬 content_analysis -> contentDescription (内容分析)
        "contentDescription": shot.get("content_analysis", visual_description),
        # 🎬 时间信息
        "startSeconds": start_seconds,
        "endSeconds": end_seconds,
        "durationSeconds": duration_seconds,
        # 🎬 shot_type -> shotType (镜头类型/景别)
        "shotType": cinematography.get("shot_type", "") or cinematography.get("shot_scale", ""),
        "shotSize": cinematography.get("shot_type", "") or cinematography.get("shot_scale", "MEDIUM"),
        # 🎬 camera_angle (摄影机角度)
        "cameraAngle": cinematography.get("camera_angle", "") or cinematography.get("subject_orientation", ""),
        # 🎬 camera_movement (摄影机运动)
        "cameraMovement": cinematography.get("camera_movement", "") or cinematography.get("camera_type", "") or cinematography.get("motion_vector", ""),
        # 🎬 focus_and_depth (焦距与景深)
        "focusAndDepth": cinematography.get("focus_and_depth", "") or cinematography.get("focal_depth", ""),
        "focalLengthDepth": cinematography.get("focus_and_depth", "") or cinematography.get("focal_depth", ""),
        # 🎬 lighting (光线)
        "lighting": shot.get("lighting", "") or cinematography.get("lighting", ""),
        # 🎬 music_and_sound (音乐与音效)
        "musicAndSound": shot.get("music_and_sound", ""),
        "soundDesign": shot.get("sound_design", ""),
        "music": shot.get("music_mood", ""),
        # 🎬 voiceover (对白/旁白)
        "voiceover": shot.get("voiceover", ""),
        "dialogueVoiceover": shot.get("dialogue_voiceover", ""),
        "dialogueText": shot.get("dialogue_text", "")
    }


def convert_workflow_to_socialsaver(workflow: Dict[str, Any], base_url: str = "") -> Dict[str, Any]:
    """
    将完整的 ReTake workflow 转换为 SocialSaver 格式
    """
    job_id = workflow.get("job_id", "")
    shots = workflow.get("shots", [])

    storyboard = [
        convert_shot_to_socialsaver(shot, job_id, base_url)
        for shot in shots
    ]

    return {
        "jobId": job_id,
        "sourceVideo": workflow.get("source_video", ""),
        "globalStyle": workflow.get("global", {}).get("style_prompt", ""),
        "storyboard": storyboard,
        "status": {
            "analyze": workflow.get("global_stages", {}).get("analyze", "NOT_STARTED"),
            "stylize": workflow.get("global_stages", {}).get("stylize", "NOT_STARTED"),
            "videoGen": workflow.get("global_stages", {}).get("video_gen", "NOT_STARTED"),
            "merge": workflow.get("global_stages", {}).get("merge", "NOT_STARTED")
        }
    }


Path("jobs").mkdir(parents=True, exist_ok=True)
Path("temp_uploads").mkdir(parents=True, exist_ok=True)

# 1. 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 初始化核心引擎
# 创建全局 manager 实例
manager = WorkflowManager() 
agent = AgentEngine()

# --- 数据模型 ---
class ChatRequest(BaseModel):
    message: str
    job_id: Optional[str] = None 

class ShotUpdateRequest(BaseModel):
    shot_id: str
    description: Optional[str] = None
    video_model: Optional[str] = None
    job_id: Optional[str] = None

# --- 路由接口 ---

@app.get("/")
async def read_index():
    return FileResponse('index.html')

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    print(f"📥 [收到文件] 正在接收上传: {file.filename}") 
    try:
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        temp_file_path = temp_dir / f"{uuid.uuid4()}_{file.filename}"
        
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"🧠 [AI 启动] 正在调用 Gemini 2.0 Flash 拆解分镜，请耐心等待...")
        new_job_id = manager.initialize_from_file(temp_file_path)
        
        if temp_file_path.exists():
            os.remove(temp_file_path)
            
        print(f"✅ [全部完成] 新项目已就绪: {new_job_id}")
        return {"status": "success", "job_id": new_job_id}
    except Exception as e:
        print(f"❌ [报错] 上传拆解环节出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/workflow")
async def get_workflow(job_id: Optional[str] = None):
    """获取最新全局状态"""
    target_id = job_id or manager.job_id
    if not target_id:
        jobs_dir = Path("jobs")
        if jobs_dir.exists():
            existing_jobs = sorted([d.name for d in jobs_dir.iterdir() if d.is_dir()], reverse=True)
            if existing_jobs: target_id = existing_jobs[0]
    
    if not target_id:
        return {"error": "No jobs found"}
        
    # 动态同步状态
    manager.job_id = target_id
    manager.job_dir = Path("jobs") / target_id
    return manager.load()

@app.post("/api/agent/chat")
async def agent_chat(req: ChatRequest):
    """Agent 全局指挥"""
    if req.job_id: 
        manager.job_id = req.job_id
        manager.job_dir = Path("jobs") / req.job_id
        
    # 先同步磁盘数据到内存
    wf = manager.load()
    
    # 💡 必须包含所有分镜描述，Agent 才能找到所有主体进行替换
    all_descriptions = []
    for i, shot in enumerate(wf.get("shots", [])):
        desc = shot.get("description", "")
        if desc:
            all_descriptions.append(f"Shot {i+1}: {desc}")
    descriptions_text = "\n".join(all_descriptions) if all_descriptions else "No shots"
    summary = f"Job ID: {manager.job_id}\nGlobal Style: {wf.get('global', {}).get('style_prompt')}\n\n[All Shot Descriptions]\n{descriptions_text}"
    
    action = agent.get_action_from_text(req.message, summary)
    if isinstance(action, list) or (isinstance(action, dict) and action.get("op") != "error"):
        res = manager.apply_agent_action(action)
        return {"action": action, "result": res}
    return {"action": action, "result": {"status": "error"}}

@app.post("/api/shot/update")
async def update_shot_params(req: ShotUpdateRequest):
    """形态 3：手动微调单个分镜 - 修复保存逻辑"""
    if req.job_id:
        manager.job_id = req.job_id
        manager.job_dir = Path("jobs") / req.job_id
    
    # 💡 核心修复：修改前必须强制加载该 job 的最新磁盘数据，防止版本覆盖
    manager.load()
    
    action = {
        "op": "update_shot_params",
        "shot_id": req.shot_id,
        "description": req.description
    }
    
    res = manager.apply_agent_action(action)
    return res

# ============================================================
# SocialSaver 专用 API 端点
# ============================================================

@app.get("/api/job/{job_id}/storyboard")
async def get_storyboard_socialsaver(job_id: str):
    """
    获取 SocialSaver 格式的分镜表
    返回格式与 SocialSaver 前端的 StoryboardShot[] 类型兼容

    优先使用 Film IR 数据（两阶段分析更准确），回退到 workflow 数据
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    manager.job_id = job_id
    manager.job_dir = job_dir
    workflow = manager.load()

    # 🎬 优先使用 Film IR 的镜头数据（更准确的两阶段分析）
    film_ir_path = job_dir / "film_ir.json"
    if film_ir_path.exists():
        try:
            film_ir = json.loads(film_ir_path.read_text(encoding="utf-8"))
            ir_shots = film_ir.get("pillars", {}).get("III_shotRecipe", {}).get("concrete", {}).get("shots", [])
            workflow_shots = workflow.get("shots", [])

            # 🎬 始终优先使用 Film IR 数据（更准确的两阶段分析和时间戳）
            if len(ir_shots) >= len(workflow_shots) and len(ir_shots) > 0:
                print(f"📊 Using Film IR shots ({len(ir_shots)}) instead of workflow ({len(workflow_shots)})")

                # 🎬 获取视频时长用于估算时间戳
                video_path = job_dir / "input.mp4"
                video_duration = 10.0  # 默认10秒
                if video_path.exists():
                    import subprocess
                    try:
                        result = subprocess.run(
                            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                            capture_output=True, text=True
                        )
                        video_duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0
                    except:
                        pass

                # 解析时间戳（Film IR 使用 startTime/endTime 字符串格式）
                def parse_film_ir_time(time_str):
                    """解析 Film IR 时间格式 (HH:MM:SS.mmm 或 MM:SS.mmm 或数字)"""
                    if time_str is None:
                        return None
                    if isinstance(time_str, (int, float)):
                        return float(time_str)
                    try:
                        return float(time_str)
                    except (ValueError, TypeError):
                        pass
                    # 解析 HH:MM:SS.mmm 或 MM:SS.mmm 格式
                    parts = str(time_str).split(":")
                    try:
                        if len(parts) == 3:
                            h, m, s = parts
                            return float(h) * 3600 + float(m) * 60 + float(s)
                        elif len(parts) == 2:
                            m, s = parts
                            return float(m) * 60 + float(s)
                        elif len(parts) == 1:
                            return float(parts[0])
                    except (ValueError, TypeError):
                        pass
                    return None

                for ir_shot in ir_shots:
                    # 尝试从 startTime/endTime 解析
                    start = parse_film_ir_time(ir_shot.get("startTime")) or ir_shot.get("startSeconds")
                    end = parse_film_ir_time(ir_shot.get("endTime")) or ir_shot.get("endSeconds")
                    if start is not None:
                        ir_shot["startSeconds"] = start
                    if end is not None:
                        ir_shot["endSeconds"] = end

                # 如果仍然没有时间戳，使用估算
                shot_duration = video_duration / len(ir_shots)
                for i, ir_shot in enumerate(ir_shots):
                    if ir_shot.get("startSeconds") is None:
                        ir_shot["startSeconds"] = i * shot_duration
                        ir_shot["endSeconds"] = (i + 1) * shot_duration

                # 🎬 检查并补充缺失的帧文件
                frames_dir = job_dir / "frames"
                if video_path.exists() and frames_dir.exists():
                    from core.utils import get_ffmpeg_path
                    ffmpeg_path = get_ffmpeg_path()

                    for ir_shot in ir_shots:
                        shot_id = ir_shot.get("shotId", "shot_01")
                        frame_path = frames_dir / f"{shot_id}.png"
                        if not frame_path.exists():
                            # 🎯 物理对位法：短镜头规则 + 偏差保护
                            start_sec = ir_shot.get("startSeconds", 0) or 0
                            end_sec = ir_shot.get("endSeconds", 0) or start_sec + 1
                            duration = end_sec - start_sec

                            extract_point = None

                            # 规则 1：短镜头强制规则（duration < 2s）
                            if duration < 2.0:
                                extract_point = end_sec - 0.2
                                print(f"⚡ Extracting {shot_id} at {extract_point:.2f}s (short shot rule, duration={duration:.2f}s)")

                            # 规则 2：正常镜头 - AI 锚点 + 偏差保护
                            elif ir_shot.get("representativeTimestamp") is not None:
                                rep_ts = ir_shot.get("representativeTimestamp")
                                safe_ts = max(rep_ts, start_sec + 1.2)
                                extract_point = min(safe_ts, end_sec - 0.1)
                                if safe_ts != rep_ts:
                                    print(f"🛡️ Extracting {shot_id} at {extract_point:.2f}s (bias protection, AI gave {rep_ts:.2f}s)")
                                else:
                                    print(f"🎯 Extracting {shot_id} at {extract_point:.2f}s (AI anchor)")

                            # 规则 3：保底逻辑
                            if extract_point is None:
                                extract_point = start_sec + (duration * 0.8)
                                print(f"📐 Extracting {shot_id} at {extract_point:.2f}s (80% fallback)")

                            subprocess.run([
                                ffmpeg_path, "-y",
                                "-ss", str(extract_point),
                                "-i", str(video_path),
                                "-frames:v", "1",
                                "-q:v", "2",
                                str(frame_path)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # 转换 Film IR 格式到 workflow 格式
                converted_shots = []
                for ir_shot in ir_shots:
                    shot_id = ir_shot.get("shotId", "shot_01")
                    camera = ir_shot.get("camera", {}) if isinstance(ir_shot.get("camera"), dict) else {}
                    audio = ir_shot.get("audio", {}) if isinstance(ir_shot.get("audio"), dict) else {}

                    converted_shots.append({
                        "shot_id": shot_id,
                        # 🎬 首帧描述 (Visual Description)
                        "frame_description": ir_shot.get("firstFrameDescription", ""),
                        # 🎬 内容分析 (Content Description)
                        "content_analysis": ir_shot.get("subject", ""),
                        # 🎬 场景描述
                        "scene_description": ir_shot.get("scene", ""),
                        "description": ir_shot.get("subject", "") + " " + ir_shot.get("scene", ""),
                        "start_time": ir_shot.get("startSeconds", 0),
                        "end_time": ir_shot.get("endSeconds", 0),
                        "assets": {
                            "first_frame": f"frames/{shot_id}.png",
                            "source_video_segment": f"source_segments/{shot_id}.mp4",
                            "stylized_frame": None,
                            "video": None
                        },
                        "status": {
                            "stylize": "NOT_STARTED",
                            "video_generate": "NOT_STARTED"
                        },
                        "cinematography": {
                            # 🎬 镜头类型/景别 (shot_type)
                            "shot_type": camera.get("shotSize", ""),
                            "shot_scale": camera.get("shotSize", ""),
                            # 🎬 摄影机角度
                            "camera_angle": camera.get("cameraAngle", ""),
                            # 🎬 摄影机运动
                            "camera_movement": camera.get("cameraMovement", ""),
                            "camera_type": camera.get("cameraMovement", ""),
                            # 🎬 焦距与景深
                            "focus_and_depth": camera.get("focalLengthDepth", ""),
                            "focal_depth": camera.get("focalLengthDepth", ""),
                        },
                        # 🎬 光线
                        "lighting": ir_shot.get("lighting", ""),
                        # 🎬 从 audio 对象中提取音频相关字段
                        "sound_design": audio.get("soundDesign", ""),
                        "music_mood": audio.get("music", ""),
                        # 🎬 合并为 music_and_sound
                        "music_and_sound": ((audio.get("soundDesign") or "") + " | " + (audio.get("music") or "")).strip(" |"),
                        # 🎬 对白/旁白
                        "dialogue_voiceover": audio.get("dialogue") or "",
                        "dialogue_text": audio.get("dialogueText") or "",
                        # 🎬 合并为 voiceover
                        "voiceover": ((audio.get("dialogue") or "") + (" - " + (audio.get("dialogueText") or "") if audio.get("dialogueText") else "")).strip(),
                    })
                workflow["shots"] = converted_shots
        except Exception as e:
            print(f"⚠️ Failed to load Film IR shots: {e}")

    # 构建 base_url（用于资源路径）
    base_url = ""

    result = convert_workflow_to_socialsaver(workflow, base_url)
    return result


@app.get("/api/job/{job_id}/shots/{shot_id}")
async def get_single_shot_socialsaver(job_id: str, shot_id: str):
    """
    获取单个分镜的 SocialSaver 格式数据
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    manager.job_id = job_id
    manager.job_dir = job_dir
    workflow = manager.load()

    for shot in workflow.get("shots", []):
        if shot.get("shot_id") == shot_id:
            return convert_shot_to_socialsaver(shot, job_id, "")

    raise HTTPException(status_code=404, detail=f"Shot not found: {shot_id}")


@app.get("/api/job/{job_id}/status")
async def get_job_status(job_id: str):
    """
    获取作业状态摘要（用于前端轮询）
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    manager.job_id = job_id
    manager.job_dir = job_dir
    workflow = manager.load()

    shots = workflow.get("shots", [])
    total = len(shots)
    stylized = sum(1 for s in shots if s.get("status", {}).get("stylize") == "SUCCESS")
    video_done = sum(1 for s in shots if s.get("status", {}).get("video_generate") == "SUCCESS")
    running = sum(1 for s in shots if s.get("status", {}).get("stylize") == "RUNNING" or s.get("status", {}).get("video_generate") == "RUNNING")

    return {
        "jobId": job_id,
        "totalShots": total,
        "stylizedCount": stylized,
        "videoGeneratedCount": video_done,
        "runningCount": running,
        "canMerge": video_done == total and total > 0,
        "globalStages": workflow.get("global_stages", {}),
        "globalStyle": workflow.get("global", {}).get("style_prompt", "")
    }


@app.post("/api/run/{node_type}")
async def run_task(node_type: str, background_tasks: BackgroundTasks, shot_id: Optional[str] = None, job_id: Optional[str] = None):
    if job_id:
        manager.job_id = job_id
        manager.job_dir = Path("jobs") / job_id

    # 处理合并导出逻辑
    if node_type == "merge":
        manager.load()
        try:
            result_file = manager.merge_videos()
            return {"status": "success", "file": result_file, "job_id": manager.job_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    if node_type not in ["stylize", "video_generate"]:
        raise HTTPException(status_code=400, detail="Invalid node type")

    background_tasks.add_task(manager.run_node, node_type, shot_id)
    return {"status": "started", "job_id": manager.job_id}


# ============================================================
# 串行批量视频生成 API (防止 Veo RPM 限流)
# ============================================================

def _run_batch_video_generation_serial(job_id: str):
    """
    串行执行所有 shot 的视频生成，带冷却间隔和随机抖动

    策略：
    1. 彻底串行化 - 一个接一个执行
    2. 冷却时间 - 每个 shot 之间等待 30 秒
    3. 随机抖动重试 - 429 错误时增加 5-15 秒随机延迟
    4. 失败熔断 - 连续 3 次失败后暂停整个任务链
    """
    import time
    import random
    from core.runner import veo_generate_video, seedance_generate_video, save_workflow, load_workflow

    job_dir = Path("jobs") / job_id
    wf = load_workflow(job_dir)

    shots = wf.get("shots", [])
    total_shots = len(shots)
    success_count = 0
    consecutive_failures = 0
    max_consecutive_failures = 3

    # 冷却时间配置
    INTER_SHOT_BUFFER = 30  # 每个 shot 之间等待 30 秒
    JITTER_MIN = 5  # 随机抖动最小值
    JITTER_MAX = 15  # 随机抖动最大值

    print(f"🎬 [Batch Video Gen] 开始串行生成 {total_shots} 个分镜视频...")
    print(f"⚙️ [Config] 冷却间隔: {INTER_SHOT_BUFFER}s, 抖动范围: {JITTER_MIN}-{JITTER_MAX}s")

    # 更新全局状态
    if "global_stages" not in wf:
        wf["global_stages"] = {
            "analyze": "SUCCESS", "extract": "SUCCESS",
            "stylize": "NOT_STARTED", "video_gen": "NOT_STARTED", "merge": "NOT_STARTED"
        }
    wf["global_stages"]["video_gen"] = "RUNNING"
    save_workflow(job_dir, wf)

    for idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id")

        # 🔄 冷却间隔（第一个 shot 除外）
        if idx > 0:
            jitter = random.uniform(JITTER_MIN, JITTER_MAX)
            wait_time = INTER_SHOT_BUFFER + jitter
            print(f"⏳ [Cooling] 等待 {wait_time:.1f}s 后处理 {shot_id} (冷却 {INTER_SHOT_BUFFER}s + 抖动 {jitter:.1f}s)")
            time.sleep(wait_time)

        print(f"\n{'='*60}")
        print(f"🎬 [Shot {idx + 1}/{total_shots}] 开始处理: {shot_id}")
        print(f"{'='*60}")

        # 更新 shot 状态
        shot.setdefault("status", {})["video_generate"] = "RUNNING"
        save_workflow(job_dir, wf)

        try:
            video_model = wf.get("global", {}).get("video_model", "seedance")  # 默认使用 Seedance

            if video_model == "veo":
                rel_video_path = veo_generate_video(job_dir, wf, shot)
            elif video_model == "seedance":
                rel_video_path = seedance_generate_video(job_dir, wf, shot)
            else:
                # Mock 模式快速测试
                from core.runner import mock_generate_video
                rel_video_path = mock_generate_video(job_dir, shot)

            shot.setdefault("assets", {})["video"] = rel_video_path
            shot["status"]["video_generate"] = "SUCCESS"
            success_count += 1
            consecutive_failures = 0  # 重置连续失败计数
            print(f"✅ [Shot {idx + 1}/{total_shots}] {shot_id} 视频生成成功！")

        except Exception as e:
            error_str = str(e)
            shot["status"]["video_generate"] = "FAILED"
            shot.setdefault("errors", {})["video_generate"] = error_str
            consecutive_failures += 1

            print(f"❌ [Shot {idx + 1}/{total_shots}] {shot_id} 失败: {error_str[:100]}")

            # 🛑 熔断机制：连续失败 3 次后暂停
            if consecutive_failures >= max_consecutive_failures:
                print(f"\n🛑 [Circuit Breaker] 连续 {max_consecutive_failures} 次失败，暂停任务链")
                print(f"💡 建议：检查 API Quota 或稍后再试")
                wf["global_stages"]["video_gen"] = "PAUSED"
                save_workflow(job_dir, wf)
                break

        save_workflow(job_dir, wf)

    # 最终状态更新
    wf = load_workflow(job_dir)  # 重新加载确保最新
    if wf["global_stages"].get("video_gen") != "PAUSED":
        if success_count == total_shots:
            wf["global_stages"]["video_gen"] = "SUCCESS"
        elif success_count > 0:
            wf["global_stages"]["video_gen"] = "PARTIAL"
        else:
            wf["global_stages"]["video_gen"] = "FAILED"

    save_workflow(job_dir, wf)

    print(f"\n{'='*60}")
    print(f"🏁 [Batch Complete] 总计: {total_shots}, 成功: {success_count}, 失败: {total_shots - success_count}")
    print(f"{'='*60}")


@app.post("/api/job/{job_id}/generate-videos-batch")
async def generate_videos_batch(job_id: str, background_tasks: BackgroundTasks):
    """
    批量串行生成所有分镜视频

    特性：
    - 串行执行：一个接一个，避免并发轰炸
    - 冷却间隔：每个 shot 之间等待 30 秒
    - 随机抖动：重试时增加 5-15 秒随机延迟
    - 熔断机制：连续 3 次失败后暂停
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # 在后台串行执行
    background_tasks.add_task(_run_batch_video_generation_serial, job_id)

    return {
        "status": "started",
        "message": "Video generation started in serial mode (30s cooling between shots)",
        "job_id": job_id
    }


# ============================================================
# Film IR API 端点 (电影逻辑中间层)
# ============================================================

@app.get("/api/job/{job_id}/film_ir")
async def get_film_ir(job_id: str):
    """
    获取完整 Film IR 数据
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if not film_ir_exists(job_dir):
        raise HTTPException(status_code=404, detail=f"Film IR not found for job: {job_id}")

    ir = load_film_ir(job_dir)
    return ir


@app.get("/api/job/{job_id}/film_ir/story_theme")
async def get_film_ir_story_theme(job_id: str):
    """
    获取支柱 I: Story Theme (对应前端九维表格)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)
    data = ir_manager.get_story_theme_for_frontend()

    if not data:
        raise HTTPException(status_code=404, detail="Story theme data not available")

    return data


@app.get("/api/job/{job_id}/film_ir/narrative")
async def get_film_ir_narrative(job_id: str):
    """
    获取支柱 II: Narrative Template (对应前端 Script Analysis)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)
    data = ir_manager.get_script_analysis_for_frontend()

    if not data:
        raise HTTPException(status_code=404, detail="Narrative template data not available")

    return data


@app.get("/api/job/{job_id}/film_ir/shots")
async def get_film_ir_shots(job_id: str, request: Request):
    """
    获取支柱 III: Shot Recipe (分镜列表)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    base_url = str(request.base_url).rstrip("/")
    ir_manager = FilmIRManager(job_id)
    shots = ir_manager.get_storyboard_for_frontend(base_url)

    return {"shots": shots}


@app.get("/api/job/{job_id}/film_ir/render_strategy")
async def get_film_ir_render_strategy(job_id: str):
    """
    获取支柱 IV: Render Strategy (执行层)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)
    data = ir_manager.get_active_layer("IV_renderStrategy")

    return data


@app.get("/api/job/{job_id}/film_ir/stages")
async def get_film_ir_stages(job_id: str):
    """
    获取 Film IR 阶段状态
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    return {
        "jobId": job_id,
        "stages": ir_manager.stages
    }


class RemixRequest(BaseModel):
    prompt: str
    reference_images: Optional[List[str]] = None  # 参考图片路径列表


@app.post("/api/job/{job_id}/remix")
async def trigger_remix(job_id: str, request: RemixRequest, background_tasks: BackgroundTasks):
    """
    触发意图注入 (Remix) - M4 核心接口
    用户提交二创意图，触发 Stage 3-6 的执行

    Request Body:
        prompt: 用户的二创意图描述
        reference_images: 参考图片路径列表 (可选)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 检查前置条件 - 需要 specificAnalysis 完成 (M3 已完成分析)
    if ir_manager.stages.get("specificAnalysis") != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail="Video analysis not completed. Please wait for video analysis to finish."
        )

    # 保存用户意图 (包括参考图片)
    ir_manager.set_user_intent(
        raw_prompt=request.prompt,
        reference_images=request.reference_images or []
    )

    # 后台执行意图注入管线
    async def run_remix_pipeline():
        try:
            # Stage 3: Intent Injection (M4 核心)
            result = ir_manager.run_stage("intentInjection")
            if result.get("status") != "success":
                print(f"❌ Intent injection failed: {result.get('reason')}")
                return

            # Stage 4-5 暂时跳过，等待后续实现
            # ir_manager.run_stage("assetGeneration")
            # ir_manager.run_stage("shotRefinement")

            print(f"✅ Remix pipeline completed for {job_id}")
        except Exception as e:
            print(f"❌ Remix pipeline failed: {e}")

    background_tasks.add_task(run_remix_pipeline)

    return {
        "status": "started",
        "jobId": job_id,
        "message": "Intent injection started",
        "userPrompt": request.prompt,
        "referenceImages": request.reference_images or []
    }


@app.get("/api/job/{job_id}/remix/status")
async def get_remix_status(job_id: str):
    """
    获取 Remix 状态
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    intent_status = ir_manager.stages.get("intentInjection", "NOT_STARTED")

    # 转换为前端期望的 status 格式
    if intent_status == "SUCCESS":
        status = "completed"
    elif intent_status == "RUNNING":
        status = "running"
    elif intent_status == "FAILED":
        status = "failed"
    else:
        status = "not_started"

    # 获取意图历史信息
    intent_with_history = ir_manager.get_current_intent_with_history()

    return {
        "jobId": job_id,
        "status": status,
        "intentInjectionStatus": intent_status,
        "assetGenerationStatus": ir_manager.stages.get("assetGeneration", "NOT_STARTED"),
        "hasParsedIntent": ir_manager.user_intent.get("parsedIntent") is not None,
        "hasRemixedLayer": ir_manager.user_intent.get("remixedLayer") is not None,
        "isRemixed": ir_manager.user_intent.get("remixedLayer") is not None,  # 明确标记是否已 remix
        "currentIntent": {
            "rawPrompt": intent_with_history["current"]["rawPrompt"],
            "injectedAt": intent_with_history["current"]["injectedAt"]
        },
        "intentHistory": {
            "totalModifications": intent_with_history["totalModifications"],
            "history": [
                {
                    "index": h["historyIndex"],
                    "rawPrompt": h["rawPrompt"][:100] + "..." if len(h.get("rawPrompt", "")) > 100 else h.get("rawPrompt", ""),
                    "injectedAt": h["injectedAt"],
                    "archivedAt": h["archivedAt"]
                }
                for h in intent_with_history["history"]
            ]
        }
    }


@app.get("/api/job/{job_id}/remix/diff")
async def get_remix_diff(job_id: str):
    """
    获取 concrete vs remixed 的差异对比 (用于前端 Diff View)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    remixed_layer = ir_manager.get_remixed_layer()
    if not remixed_layer:
        return {
            "jobId": job_id,
            "hasDiff": False,
            "diff": [],
            "summary": None
        }

    diff = ir_manager.get_remix_diff_for_frontend()

    return {
        "jobId": job_id,
        "hasDiff": True,
        "diff": diff,
        "summary": remixed_layer.get("summary", {})
    }


@app.get("/api/job/{job_id}/remix/prompts")
async def get_remix_prompts(job_id: str):
    """
    获取所有 remixed 的 T2I/I2V prompts (用于执行生成)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    remixed_layer = ir_manager.get_remixed_layer()
    if not remixed_layer:
        raise HTTPException(
            status_code=400,
            detail="No remixed layer available. Run remix first."
        )

    from core.meta_prompts import extract_t2i_prompts, extract_i2v_prompts

    # 构造完整的 fusion output 格式
    fusion_output = {
        "remixedShots": remixed_layer.get("shots", []),
        "remixedIdentityAnchors": remixed_layer.get("identityAnchors", {})
    }

    return {
        "jobId": job_id,
        "t2iPrompts": extract_t2i_prompts(fusion_output),
        "i2vPrompts": extract_i2v_prompts(fusion_output),
        "identityAnchors": remixed_layer.get("identityAnchors", {})
    }


# ============================================================
# M6: Remix Storyboard Generation API
# ============================================================

def generate_storyboard_frame(
    job_dir: Path,
    job_id: str,
    shot_id: str,
    t2i_prompt: str,
    applied_anchors: dict,
    identity_anchors: dict,
    visual_style: dict
) -> str:
    """
    使用 Gemini 生成分镜首帧图片（基于原始帧进行编辑，保持构图一致性）

    Args:
        job_dir: Job 目录
        job_id: Job ID
        shot_id: Shot ID (e.g., "shot_01")
        t2i_prompt: T2I_FirstFrame prompt
        applied_anchors: 该镜头应用的锚点 {"characters": [...], "environments": [...]}
        identity_anchors: 完整的身份锚点数据
        visual_style: 视觉风格配置

    Returns:
        生成图片的 URL 路径
    """
    import io
    import base64
    from PIL import Image
    from google import genai
    from google.genai import types

    # 创建 storyboard_frames 目录
    storyboard_dir = job_dir / "storyboard_frames"
    storyboard_dir.mkdir(exist_ok=True)

    # 🎯 查找原始帧作为参考（保持构图一致性的关键）
    original_frame_path = job_dir / "frames" / f"{shot_id}.png"
    has_reference = original_frame_path.exists()

    # 构建修改指令（而不是完整描述）
    modification_parts = []

    # 1. 收集角色修改描述 + 三视图参考图片
    char_ids = applied_anchors.get("characters", [])
    char_descs = []
    char_reference_images = []  # 存储角色参考图片的字节数据
    if char_ids and identity_anchors.get("characters"):
        for char in identity_anchors["characters"]:
            if char.get("anchorId") in char_ids:
                anchor_id = char.get("anchorId", "unknown")
                desc = char.get("detailedDescription", "")
                if desc:
                    char_descs.append(f"[{anchor_id}]: {desc[:300]}")
                    print(f"   🔗 [Anchor] Applied character: {anchor_id} -> {desc[:50]}...")

                # 读取三视图参考图片
                three_views = char.get("threeViews", {})
                for view_type in ["front", "side", "back"]:
                    view_path = three_views.get(view_type)
                    if view_path:
                        # 路径可能是:
                        # 1. 绝对路径: /Users/.../jobs/job_xxx/assets/...
                        # 2. 相对路径: jobs/job_xxx/assets/... (相对于工作目录)
                        # 3. 仅文件名: anchor_front.png (相对于 job_dir/assets)
                        if not os.path.isabs(view_path):
                            if view_path.startswith("jobs/"):
                                # 已经是从工作目录开始的路径
                                pass
                            elif "/" not in view_path:
                                # 仅文件名，需要补全路径
                                view_path = str(job_dir / "assets" / view_path)
                            # 否则保持原样
                        if os.path.exists(view_path):
                            try:
                                with open(view_path, "rb") as f:
                                    img_bytes = f.read()
                                    char_reference_images.append({
                                        "anchor_id": anchor_id,
                                        "view": view_type,
                                        "bytes": img_bytes
                                    })
                                    print(f"   🖼️ [Reference] Loaded character {anchor_id} {view_type} view from {view_path}")
                            except Exception as e:
                                print(f"   ⚠️ Failed to load {view_path}: {e}")
                        else:
                            print(f"   ⚠️ Reference image not found: {view_path}")

    # 2. 收集环境修改描述 + 三视图参考图片
    env_ids = applied_anchors.get("environments", [])
    env_descs = []
    env_reference_images = []  # 存储环境参考图片的字节数据
    if env_ids and identity_anchors.get("environments"):
        for env in identity_anchors["environments"]:
            if env.get("anchorId") in env_ids:
                anchor_id = env.get("anchorId", "unknown")
                desc = env.get("detailedDescription", "")
                if desc:
                    env_descs.append(f"[{anchor_id}]: {desc[:300]}")
                    print(f"   🔗 [Anchor] Applied environment: {anchor_id} -> {desc[:50]}...")

                # 读取三视图参考图片
                three_views = env.get("threeViews", {})
                for view_type in ["wide", "detail", "alt"]:
                    view_path = three_views.get(view_type)
                    if view_path:
                        # 路径处理逻辑同上
                        if not os.path.isabs(view_path):
                            if view_path.startswith("jobs/"):
                                pass
                            elif "/" not in view_path:
                                view_path = str(job_dir / "assets" / view_path)
                        if os.path.exists(view_path):
                            try:
                                with open(view_path, "rb") as f:
                                    img_bytes = f.read()
                                    env_reference_images.append({
                                        "anchor_id": anchor_id,
                                        "view": view_type,
                                        "bytes": img_bytes
                                    })
                                    print(f"   🖼️ [Reference] Loaded environment {anchor_id} {view_type} view from {view_path}")
                            except Exception as e:
                                print(f"   ⚠️ Failed to load {view_path}: {e}")
                        else:
                            print(f"   ⚠️ Reference image not found: {view_path}")

    # 合并所有参考图片
    all_reference_images = char_reference_images + env_reference_images
    print(f"   📸 Total reference images loaded: {len(all_reference_images)}")

    # 3. 收集视觉风格
    style_parts = []
    if visual_style.get("artStyle"):
        style_parts.append(visual_style['artStyle'])
    if visual_style.get("colorPalette"):
        style_parts.append(visual_style['colorPalette'])
    if visual_style.get("lightingMood"):
        style_parts.append(visual_style['lightingMood'])

    try:
        import concurrent.futures

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"   ❌ GEMINI_API_KEY not set")
            return ""
        # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())

        client = genai.Client(api_key=api_key)

        if has_reference:
            # ✅ 有参考图：使用图片编辑模式，保持构图一致性
            print(f"🎨 [Storyboard] Editing {shot_id} with reference image + {len(all_reference_images)} character refs...")

            # 读取原始帧
            with open(original_frame_path, "rb") as f:
                original_image_bytes = f.read()

            # 构建叙述性 prompt（按照 Gemini 文档建议，使用描述性段落而非指令列表）
            prompt_parts = []

            # 🎯 核心指令：明确这是一个图片编辑任务
            prompt_parts.append("TASK: Edit the provided reference image to match this description.")
            prompt_parts.append("IMPORTANT: You MUST modify the image. Do NOT return the original unchanged.")

            # 场景描述（这里包含了用户的修改请求）
            if t2i_prompt:
                prompt_parts.append(f"TARGET SCENE: {t2i_prompt}")

            # 参考图说明（告诉 Gemini 每张图的用途）
            if all_reference_images:
                char_refs = [r for r in all_reference_images if 'char' in r['anchor_id'].lower()]
                env_refs = [r for r in all_reference_images if 'env' in r['anchor_id'].lower()]

                if char_refs:
                    prompt_parts.append(f"CHARACTER REFERENCES: I have provided {len(char_refs)} character reference images:")
                    for ref in char_refs:
                        prompt_parts.append(f"  - {ref['anchor_id']} ({ref['view']} view)")
                    prompt_parts.append("Match character appearances to these references.")

                if env_refs:
                    prompt_parts.append(f"ENVIRONMENT REFERENCES: I have provided {len(env_refs)} environment reference images:")
                    for ref in env_refs:
                        prompt_parts.append(f"  - {ref['anchor_id']} ({ref['view']} view)")

            # 角色详细描述
            if char_descs:
                prompt_parts.append("CHARACTER DETAILS:")
                for desc in char_descs:
                    prompt_parts.append(f"  {desc}")

            # 环境详细描述
            if env_descs:
                prompt_parts.append("ENVIRONMENT DETAILS:")
                for desc in env_descs:
                    prompt_parts.append(f"  {desc}")

            # 视觉风格
            if style_parts:
                prompt_parts.append(f"VISUAL STYLE: {', '.join(style_parts)}")

            # 编辑规则
            prompt_parts.append("EDITING RULES:")
            prompt_parts.append("1. Preserve the camera angle, framing, and overall composition from the reference image.")
            prompt_parts.append("2. Apply the described changes (colors, objects, characters, etc.) as specified in TARGET SCENE.")
            prompt_parts.append("3. Generate a high-quality cinematic frame with the requested modifications.")

            final_prompt = " ".join(prompt_parts)
            print(f"   📝 Edit prompt: {final_prompt[:300]}...")

            def call_gemini_edit():
                # 按照 Gemini 文档：prompt 在前，图片在后
                # 角色参考图放在最前面（用于角色一致性），原始帧放在最后（用于构图参考）
                contents = [final_prompt]

                # 1. 先添加角色/环境参考图（最多5张人物 + 6张物体）
                for ref in all_reference_images[:6]:
                    contents.append(types.Part.from_bytes(data=ref["bytes"], mime_type="image/png"))

                # 2. 最后添加原始帧作为构图参考
                contents.append(types.Part.from_bytes(data=original_image_bytes, mime_type="image/png"))

                return client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE'],
                        image_config=types.ImageConfig(
                            aspect_ratio="16:9",
                        ),
                    ),
                )

            TIMEOUT_SECONDS = 180  # 增加超时时间，因为 Pro 模型可能需要更长时间
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_gemini_edit)
                try:
                    response = future.result(timeout=TIMEOUT_SECONDS)
                except concurrent.futures.TimeoutError:
                    print(f"   ⏱️ Timeout after {TIMEOUT_SECONDS}s for {shot_id}, skipping...")
                    return ""

        else:
            # ⚠️ 无原始帧参考：使用三视图参考图 + 文本生成
            print(f"🎨 [Storyboard] Generating {shot_id} {'with ' + str(len(all_reference_images)) + ' reference images' if all_reference_images else 'from text only'}...")

            # 构建叙述性 prompt
            prompt_parts = []

            prompt_parts.append("Generate a cinematic scene based on the provided reference images and description.")

            # 参考图说明
            if all_reference_images:
                char_refs = [r for r in all_reference_images if 'char' in r['anchor_id'].lower()]
                env_refs = [r for r in all_reference_images if 'env' in r['anchor_id'].lower()]

                if char_refs:
                    prompt_parts.append(f"I have provided {len(char_refs)} character reference images:")
                    for ref in char_refs:
                        prompt_parts.append(f"  - {ref['anchor_id']} ({ref['view']} view)")
                    prompt_parts.append("The characters should look exactly like those in the reference images.")

                if env_refs:
                    prompt_parts.append(f"I have provided {len(env_refs)} environment reference images:")
                    for ref in env_refs:
                        prompt_parts.append(f"  - {ref['anchor_id']} ({ref['view']} view)")

            # 场景描述
            if t2i_prompt:
                prompt_parts.append(f"Scene description: {t2i_prompt}")

            # 角色详细描述
            if char_descs:
                for desc in char_descs:
                    prompt_parts.append(f"Character details: {desc}")

            # 环境详细描述
            if env_descs:
                for desc in env_descs:
                    prompt_parts.append(f"Environment details: {desc}")

            # 视觉风格
            if style_parts:
                prompt_parts.append(f"Visual style: {', '.join(style_parts)}")

            prompt_parts.append("Create a high-quality, cinematic composition with detailed rendering.")

            final_prompt = " ".join(prompt_parts)
            print(f"   📝 Text prompt: {final_prompt[:300]}...")

            def call_gemini_text():
                # prompt 在前，参考图在后
                contents = [final_prompt]
                for ref in all_reference_images[:6]:
                    contents.append(types.Part.from_bytes(data=ref["bytes"], mime_type="image/png"))

                return client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE'],
                        image_config=types.ImageConfig(
                            aspect_ratio="16:9",
                        ),
                    ),
                )

            TIMEOUT_SECONDS = 120
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_gemini_text)
                try:
                    response = future.result(timeout=TIMEOUT_SECONDS)
                except concurrent.futures.TimeoutError:
                    print(f"   ⏱️ Timeout after {TIMEOUT_SECONDS}s for {shot_id}, skipping...")
                    return ""

        # 提取生成的图片和文字反馈
        text_response = None
        image_generated = False

        for part in response.candidates[0].content.parts:
            # 检查文字反馈（Gemini 可能解释为什么没做修改）
            if hasattr(part, 'text') and part.text:
                text_response = part.text
                print(f"   💬 Gemini response: {text_response[:200]}...")

            # 提取图片
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                image_data = part.inline_data.data
                new_image = Image.open(io.BytesIO(image_data))
                output_path = storyboard_dir / f"{shot_id}.png"

                # 🔍 调试：比较新旧图片大小，检测是否真的有变化
                new_size = len(image_data)
                old_size = 0
                if output_path.exists():
                    old_size = output_path.stat().st_size

                # 🔍 调试：计算简单的图片差异（比较像素）
                if has_reference and original_frame_path.exists():
                    try:
                        original_image = Image.open(original_frame_path)
                        # 比较图片尺寸
                        if original_image.size == new_image.size:
                            # 比较部分像素
                            import hashlib
                            orig_hash = hashlib.md5(original_image.tobytes()[:10000]).hexdigest()
                            new_hash = hashlib.md5(new_image.tobytes()[:10000]).hexdigest()
                            if orig_hash == new_hash:
                                print(f"   ⚠️ WARNING: Generated image appears IDENTICAL to original!")
                            else:
                                print(f"   ✓ Image modified (hash diff: {orig_hash[:8]} → {new_hash[:8]})")
                    except Exception as cmp_e:
                        print(f"   ⚠️ Could not compare images: {cmp_e}")

                new_image.save(output_path)
                print(f"   ✅ Generated: {output_path} (size: {old_size} → {new_size} bytes)")
                image_generated = True
                return f"/assets/{job_id}/storyboard_frames/{shot_id}.png"

        if not image_generated:
            print(f"   ⚠️ No image generated for {shot_id}")
            if text_response:
                print(f"   💬 Gemini only returned text: {text_response}")
        return ""

    except Exception as e:
        import traceback
        print(f"   ❌ Failed to generate {shot_id}: {e}")
        print(f"   📋 Traceback: {traceback.format_exc()}")
        return ""


@app.post("/api/job/{job_id}/generate-remix-storyboard")
async def generate_remix_storyboard(job_id: str, background_tasks: BackgroundTasks):
    """
    生成 Remix Storyboard

    使用 AI 生成每个分镜的首帧图片：
    - 从 T2I_FirstFrame prompt 获取基础描述
    - 结合 Identity Anchors 的详细描述
    - 应用 Visual Style 配置
    - 调用 gemini-3-pro-image-preview 生成图片
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 获取 visual style 配置
    render_strategy = ir_manager.ir.get("pillars", {}).get("IV_renderStrategy", {})
    visual_style = render_strategy.get("visualStyleConfig", {})

    # 获取原始 concrete shots（用于 fallback）
    concrete_shots = ir_manager.ir.get("pillars", {}).get("III_shotRecipe", {}).get("concrete", {}).get("shots", [])

    remixed_layer = ir_manager.get_remixed_layer()
    storyboard = []
    identity_anchors = {}
    is_using_original = False

    # 创建 concrete shots 查找字典（用于 fallback）
    concrete_shots_lookup = {}
    for shot in concrete_shots:
        shot_id = shot.get("shotId", "")
        if shot_id:
            concrete_shots_lookup[shot_id] = shot

    if remixed_layer and remixed_layer.get("shots"):
        # ===== 使用 remixedLayer 数据并生成新的分镜图 =====
        print(f"🎬 [Storyboard] Generating storyboard frames using remixed data...")

        # 从 pillars.IV_renderStrategy 读取 identity anchors（Asset Management 写入的位置）
        # 而不是从 remixedLayer 读取，确保 Asset Management 的修改能够正确应用
        identity_anchors = render_strategy.get("identityAnchors", {})

        # 🔍 详细调试日志：显示从 Asset Management 读取的角色信息
        print(f"🔗 [Storyboard] Loading identity anchors from pillars.IV_renderStrategy...")
        for char in identity_anchors.get("characters", []):
            anchor_id = char.get("anchorId", "unknown")
            desc = char.get("detailedDescription", "")[:80]
            print(f"   📍 Character [{anchor_id}]: {desc}...")
        remixed_shots = remixed_layer.get("shots", [])

        for idx, shot in enumerate(remixed_shots):
            shot_id = shot.get("shotId", f"shot_{idx + 1:02d}")

            # 获取 T2I_FirstFrame prompt
            t2i_prompt = shot.get("T2I_FirstFrame", "")

            # 获取该镜头应用的锚点
            applied_anchors = shot.get("appliedAnchors", {"characters": [], "environments": []})

            # 生成分镜图
            first_frame_image = generate_storyboard_frame(
                job_dir=job_dir,
                job_id=job_id,
                shot_id=shot_id,
                t2i_prompt=t2i_prompt,
                applied_anchors=applied_anchors,
                identity_anchors=identity_anchors,
                visual_style=visual_style
            )

            # 如果生成失败，回退到原始帧
            if not first_frame_image:
                frame_path = job_dir / "frames" / f"{shot_id}.png"
                if frame_path.exists():
                    first_frame_image = f"/assets/{job_id}/frames/{shot_id}.png"

            # 获取摄影参数
            camera = shot.get("cameraPreserved", {})

            # 获取对应的原始 concrete shot（用于 fallback）
            original_shot = concrete_shots_lookup.get(shot_id, {})
            original_camera = original_shot.get("camera", {})  # 注意：concrete shot 用 "camera" 而不是 "cinematography"
            original_audio = original_shot.get("audio", {})

            # 构建视觉描述
            visual_desc = shot.get("I2V_VideoGen", "") or t2i_prompt

            # 添加 visual style 信息
            style_notes = []
            if visual_style.get("artStyle"):
                style_notes.append(f"Style: {visual_style['artStyle']}")
            if visual_style.get("lightingMood"):
                style_notes.append(f"Lighting: {visual_style['lightingMood']}")
            if style_notes:
                visual_desc += f" [{', '.join(style_notes)}]"

            # 计算时长（优先 remix，fallback 到 original）
            duration = shot.get("durationSeconds") or original_shot.get("durationSeconds", 3.0)

            # 添加时间戳防止浏览器缓存
            import time
            cache_buster = int(time.time() * 1000)
            first_frame_with_cache = f"{first_frame_image}?t={cache_buster}" if first_frame_image else ""

            # 合并摄影参数：remix 优先，original 作为 fallback
            shot_size = camera.get("shotSize") or original_camera.get("shotSize", "MEDIUM")
            camera_angle = camera.get("cameraAngle") or original_camera.get("cameraAngle", "eye-level")
            camera_movement = camera.get("cameraMovement") or original_camera.get("cameraMovement", "static")
            focal_length_depth = camera.get("focalLengthDepth") or original_camera.get("focalLengthDepth", "")

            # 光影：remix 优先，original 作为 fallback
            lighting = camera.get("lighting") or original_shot.get("lighting", "")

            # 音频：remix 优先，original 作为 fallback
            music = original_audio.get("music", "") or original_audio.get("soundDesign", "")
            dialogue_voiceover = original_audio.get("dialogue", "") or original_audio.get("dialogueText", "")

            storyboard_shot = {
                "shotNumber": idx + 1,
                "shotId": shot_id,
                "firstFrameImage": first_frame_with_cache,
                "visualDescription": visual_desc,
                "contentDescription": shot.get("remixNotes", "") or shot.get("beatTag", "") or original_shot.get("beatTag", ""),
                "startSeconds": 0,
                "endSeconds": 0,
                "durationSeconds": duration,
                # 同时提供两种字段名，确保前端兼容
                "shotType": shot_size,
                "shotSize": shot_size,
                "cameraAngle": camera_angle,
                "cameraMovement": camera_movement,
                "focusAndDepth": focal_length_depth,
                "focalLengthDepth": focal_length_depth,
                "lighting": lighting,
                "music": music,
                "dialogueVoiceover": dialogue_voiceover,
                "i2vPrompt": shot.get("I2V_VideoGen", ""),
                "appliedAnchors": applied_anchors,
            }

            storyboard.append(storyboard_shot)

        print(f"✅ [Storyboard] Generated {len(storyboard)} storyboard frames")

    elif concrete_shots:
        # ===== Fallback: 使用原始视频分析数据并生成新的分镜图 =====
        is_using_original = True
        print(f"📋 [Storyboard] No remixedLayer, generating from original analysis ({len(concrete_shots)} shots)")

        for idx, shot in enumerate(concrete_shots):
            shot_id = shot.get("shotId", f"shot_{idx + 1:02d}")

            # 构建 prompt 从原始数据
            t2i_prompt = shot.get("firstFrameDescription", "") or shot.get("visualDescription", "")

            # 生成分镜图
            first_frame_image = generate_storyboard_frame(
                job_dir=job_dir,
                job_id=job_id,
                shot_id=shot_id,
                t2i_prompt=t2i_prompt,
                applied_anchors={"characters": [], "environments": []},
                identity_anchors={},
                visual_style=visual_style
            )

            # 如果生成失败，回退到原始帧
            if not first_frame_image:
                frame_path = job_dir / "frames" / f"{shot_id}.png"
                if frame_path.exists():
                    first_frame_image = f"/assets/{job_id}/frames/{shot_id}.png"

            # 从原始数据构建视觉描述
            visual_desc = shot.get("visualDescription", "") or shot.get("firstFrameDescription", "")
            if not visual_desc:
                visual_desc = f"Shot {idx + 1}"

            # 添加 visual style
            style_notes = []
            if visual_style.get("artStyle"):
                style_notes.append(f"Style: {visual_style['artStyle']}")
            if visual_style.get("lightingMood"):
                style_notes.append(f"Lighting: {visual_style['lightingMood']}")
            if style_notes:
                visual_desc += f" [{', '.join(style_notes)}]"

            # 计算时长
            start_time = shot.get("startTime", 0)
            end_time = shot.get("endTime", 0)
            if isinstance(start_time, str):
                start_time = parse_time_to_seconds(start_time)
            if isinstance(end_time, str):
                end_time = parse_time_to_seconds(end_time)
            duration = end_time - start_time if end_time > start_time else 3

            # 添加时间戳防止浏览器缓存
            import time
            cache_buster = int(time.time() * 1000)
            first_frame_with_cache = f"{first_frame_image}?t={cache_buster}" if first_frame_image else ""

            # 从 concrete shot 的 camera 对象中获取摄影参数
            camera = shot.get("camera", {})
            audio = shot.get("audio", {})

            shot_size = camera.get("shotSize", "") or shot.get("shotSize", "MEDIUM")
            camera_angle = camera.get("cameraAngle", "") or shot.get("cameraAngle", "eye-level")
            camera_movement = camera.get("cameraMovement", "") or shot.get("cameraMovement", "static")
            focal_length_depth = camera.get("focalLengthDepth", "") or shot.get("focalLengthDepth", "")
            lighting = shot.get("lighting", "")
            music = audio.get("music", "") or audio.get("soundDesign", "") or shot.get("music", "")
            dialogue = audio.get("dialogue", "") or audio.get("dialogueText", "") or shot.get("dialogueVoiceover", "")

            storyboard_shot = {
                "shotNumber": idx + 1,
                "shotId": shot_id,
                "firstFrameImage": first_frame_with_cache,
                "visualDescription": visual_desc,
                "contentDescription": shot.get("subject", "") or shot.get("contentDescription", "") or shot.get("action", ""),
                "startSeconds": float(start_time),
                "endSeconds": float(end_time),
                "durationSeconds": float(duration),
                # 同时提供两种字段名，确保前端兼容
                "shotType": shot_size,
                "shotSize": shot_size,
                "cameraAngle": camera_angle,
                "cameraMovement": camera_movement,
                "focusAndDepth": focal_length_depth,
                "focalLengthDepth": focal_length_depth,
                "lighting": lighting,
                "music": music,
                "dialogueVoiceover": dialogue,
                "i2vPrompt": visual_desc,
                "appliedAnchors": {"characters": [], "environments": []},
            }

            storyboard.append(storyboard_shot)

    else:
        raise HTTPException(
            status_code=400,
            detail="No shot data available. Please complete video analysis first."
        )

    # 重新计算时间轴（仅对 remixed 数据需要）
    if not is_using_original:
        current_time = 0
        for shot in storyboard:
            shot["startSeconds"] = current_time
            shot["endSeconds"] = current_time + shot["durationSeconds"]
            current_time = shot["endSeconds"]

    total_duration = storyboard[-1]["endSeconds"] if storyboard else 0

    return {
        "jobId": job_id,
        "storyboard": storyboard,
        "totalDuration": total_duration,
        "isUsingOriginal": is_using_original,
        "remixContext": {
            "identityAnchors": identity_anchors,
            "visualStyle": visual_style,
            "shotCount": len(storyboard)
        }
    }


class StoryboardChatRequest(BaseModel):
    message: str
    currentStoryboard: Optional[List[Dict[str, Any]]] = None


@app.post("/api/job/{job_id}/storyboard/chat")
async def storyboard_chat(job_id: str, request: StoryboardChatRequest):
    """
    Storyboard AI Chat

    解析用户自然语言修改请求，更新分镜。
    支持：
    1. 参数修改（时长、镜头类型等）
    2. AI 重新生成特定镜头的 prompt
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
    if api_key:
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
    client = genai.Client(api_key=api_key)

    ir_manager = FilmIRManager(job_id)
    remixed_layer = ir_manager.get_remixed_layer()

    if not remixed_layer:
        raise HTTPException(
            status_code=400,
            detail="No remixed layer available. Run remix first."
        )

    # 获取当前 storyboard 状态
    current_storyboard = request.currentStoryboard or []
    storyboard_summary = "\n".join([
        f"Shot {s.get('shotNumber', i+1)}: {s.get('visualDescription', '')[:100]}... (duration: {s.get('durationSeconds', 3)}s)"
        for i, s in enumerate(current_storyboard)
    ])

    # 获取 visual style 配置
    render_strategy = ir_manager.ir.get("pillars", {}).get("IV_renderStrategy", {})
    visual_style = render_strategy.get("visualStyleConfig", {})
    style_context = f"Art Style: {visual_style.get('artStyle', 'Cinematic')}, Lighting: {visual_style.get('lightingMood', 'Natural')}"

    # 构建解析 prompt
    parse_prompt = f"""You are a professional film editor assistant. Analyze the user's request and determine what changes to make to the storyboard.

CURRENT STORYBOARD:
{storyboard_summary}

VISUAL STYLE: {style_context}

USER REQUEST: {request.message}

Analyze the request and return a JSON object with:
{{
  "action": "parameter_change" | "regenerate_prompt" | "info_query",
  "affectedShots": [list of shot numbers to modify],
  "changes": {{
    "durationSeconds": number or null,
    "shotSize": string or null,
    "cameraMovement": string or null,
    "lighting": string or null,
    "promptModification": string or null (description of what to change in the prompt)
  }},
  "response": "Natural language response to user explaining what will be done"
}}

Rules:
1. If user says "时长加倍" or "make it longer", set durationSeconds to 2x current
2. If user mentions specific shot numbers, only affect those
3. If user wants visual changes (like "更暗" or "add sunglasses"), set action to "regenerate_prompt"
4. Keep camera parameters from original unless explicitly requested to change

Return ONLY the JSON object, no other text."""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[parse_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 解析 AI 响应
        import json
        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result = json.loads(result_text)

        action = result.get("action", "info_query")
        affected_shots = result.get("affectedShots", [])
        changes = result.get("changes", {})
        ai_response = result.get("response", "I understand your request.")

        # 应用修改
        updated_storyboard = []
        remixed_shots = remixed_layer.get("shots", [])

        for shot in current_storyboard:
            shot_num = shot.get("shotNumber", 0)
            new_shot = shot.copy()

            if shot_num in affected_shots:
                # 应用参数修改
                if changes.get("durationSeconds"):
                    if changes["durationSeconds"] == "2x":
                        new_shot["durationSeconds"] = shot.get("durationSeconds", 3) * 2
                    else:
                        new_shot["durationSeconds"] = changes["durationSeconds"]

                if changes.get("shotSize"):
                    new_shot["shotSize"] = changes["shotSize"]

                if changes.get("cameraMovement"):
                    new_shot["cameraMovement"] = changes["cameraMovement"]

                if changes.get("lighting"):
                    new_shot["lighting"] = changes["lighting"]

                # 如果需要重新生成 prompt
                if action == "regenerate_prompt" and changes.get("promptModification"):
                    # 调用 AI 重新生成该镜头的 prompt
                    shot_id = shot.get("shotId", f"shot_{shot_num:02d}")
                    original_prompt = shot.get("i2vPrompt", shot.get("visualDescription", ""))

                    regen_prompt = f"""You are a professional cinematographer. Modify this shot description based on the user's request.

ORIGINAL PROMPT: {original_prompt}
VISUAL STYLE: {style_context}
MODIFICATION REQUEST: {changes['promptModification']}

Generate an updated cinematic prompt that incorporates the requested changes while maintaining:
1. The same camera parameters (shot size, angle, movement)
2. The same character identities
3. Professional cinematic quality

Return ONLY the new prompt text, no other explanation."""

                    regen_response = client.models.generate_content(
                        model="gemini-3-flash-preview",
                        contents=[regen_prompt]
                    )
                    new_prompt = regen_response.text.strip()
                    new_shot["i2vPrompt"] = new_prompt
                    new_shot["visualDescription"] = new_prompt

                    # 更新 Film IR 中的 remixed shot
                    for rs in remixed_shots:
                        if rs.get("shotId") == shot_id:
                            rs["subject"] = new_prompt
                            rs["remixedI2VPrompt"] = new_prompt
                            break

            updated_storyboard.append(new_shot)

        # 重新计算时间轴
        current_time = 0
        for shot in updated_storyboard:
            shot["startSeconds"] = current_time
            shot["endSeconds"] = current_time + shot["durationSeconds"]
            current_time = shot["endSeconds"]

        # 如果有 prompt 修改，保存更新后的 Film IR
        if action == "regenerate_prompt":
            # remixedLayer 在 userIntent 下，不在 pillars 下
            if ir_manager.ir.get("userIntent", {}).get("remixedLayer"):
                ir_manager.ir["userIntent"]["remixedLayer"]["shots"] = remixed_shots
                ir_manager.save()

        return {
            "updatedStoryboard": updated_storyboard,
            "affectedShots": affected_shots,
            "response": ai_response,
            "action": action,
            "totalDuration": current_time
        }

    except Exception as e:
        print(f"❌ Storyboard chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


class RegenerateFramesRequest(BaseModel):
    shots: List[Dict[str, Any]]  # 要重新生成的分镜数据


@app.post("/api/job/{job_id}/storyboard/regenerate-frames")
async def regenerate_storyboard_frames(job_id: str, request: RegenerateFramesRequest):
    """
    重新生成指定分镜的首帧图片

    根据更新后的 prompt 重新生成分镜图，让用户在生成视频前预览效果。
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 获取 visual style 配置
    render_strategy = ir_manager.ir.get("pillars", {}).get("IV_renderStrategy", {})
    visual_style = render_strategy.get("visualStyleConfig", {})

    # 从 pillars.IV_renderStrategy 读取 identity anchors（Asset Management 写入的位置）
    identity_anchors = render_strategy.get("identityAnchors", {})
    char_ids = [c.get("anchorId") for c in identity_anchors.get("characters", [])]
    print(f"🔗 [Regenerate] Loaded identity anchors from pillars.IV_renderStrategy: {char_ids}")

    regenerated_shots = []

    print(f"🎨 [Regenerate] Starting to regenerate {len(request.shots)} frames...")

    for shot in request.shots:
        shot_id = shot.get("shotId", "")
        shot_number = shot.get("shotNumber", 0)

        # 使用更新后的 prompt
        t2i_prompt = shot.get("i2vPrompt", "") or shot.get("visualDescription", "")

        # 获取该镜头应用的锚点
        applied_anchors = shot.get("appliedAnchors", {"characters": [], "environments": []})

        print(f"   🖼️ Regenerating {shot_id}...")

        # 调用图像生成函数
        new_image_path = generate_storyboard_frame(
            job_dir=job_dir,
            job_id=job_id,
            shot_id=shot_id,
            t2i_prompt=t2i_prompt,
            applied_anchors=applied_anchors,
            identity_anchors=identity_anchors,
            visual_style=visual_style
        )

        # 如果生成失败，回退到原始帧
        if not new_image_path:
            frame_path = job_dir / "frames" / f"{shot_id}.png"
            if frame_path.exists():
                new_image_path = f"/assets/{job_id}/frames/{shot_id}.png"
                print(f"   ⚠️ Fallback to original frame for {shot_id}")

        # 更新 shot 数据，添加时间戳防止浏览器缓存
        import time
        cache_buster = int(time.time() * 1000)
        updated_shot = shot.copy()
        updated_shot["firstFrameImage"] = f"{new_image_path}?t={cache_buster}" if new_image_path else ""
        regenerated_shots.append(updated_shot)

    print(f"✅ [Regenerate] Completed {len(regenerated_shots)} frames")

    return {
        "jobId": job_id,
        "regeneratedShots": regenerated_shots,
        "count": len(regenerated_shots)
    }


# ============================================================
# Storyboard Finalize API - 视频生成前的最终确认
# ============================================================

class FinalizeStoryboardRequest(BaseModel):
    storyboard: List[Dict[str, Any]]  # 最终确认的分镜数据


@app.post("/api/job/{job_id}/storyboard/finalize")
async def finalize_storyboard(job_id: str, request: FinalizeStoryboardRequest):
    """
    🎬 视频生成前的最终数据同步

    确保 Film IR 的 remixedLayer 包含所有 Storyboard Chat 的修改：
    1. 将前端传来的最终 storyboard 数据写入 Film IR
    2. 验证所有必要的 storyboard_frames 已生成
    3. 返回准备状态，前端确认后才启动视频生成

    这是数据唯一事实来源的最后一道防线。
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    print(f"🔒 [Finalize] Syncing storyboard data to Film IR for {job_id}")

    try:
        # 1. 获取当前 remixedLayer
        remixed_layer = ir_manager.get_remixed_layer() or {}

        # 2. 更新 shots 数据
        updated_shots = []
        for shot_data in request.storyboard:
            shot_id = shot_data.get("shotId", f"shot_{str(shot_data.get('shotNumber', 0)).zfill(2)}")

            # 构建更新后的 shot
            updated_shot = {
                "shotId": shot_id,
                "shotNumber": shot_data.get("shotNumber", 0),
                "I2V_VideoGen": shot_data.get("i2vPrompt", "") or shot_data.get("visualDescription", ""),
                "visualDescription": shot_data.get("visualDescription", ""),
                "contentDescription": shot_data.get("contentDescription", ""),
                "action": shot_data.get("action", ""),
                "motionDescription": shot_data.get("motionDescription", ""),
                "startTime": shot_data.get("startSeconds", 0),
                "endTime": shot_data.get("endSeconds", 0),
                "durationSeconds": shot_data.get("durationSeconds", 3),
                "cameraPreserved": {
                    "shotSize": shot_data.get("shotSize", "MEDIUM"),
                    "cameraAngle": shot_data.get("cameraAngle", "eye-level"),
                    "cameraMovement": shot_data.get("cameraMovement", "static"),
                },
                "appliedAnchors": shot_data.get("appliedAnchors", {"characters": [], "environments": []}),
            }
            updated_shots.append(updated_shot)

        # 3. 更新 remixedLayer
        remixed_layer["shots"] = updated_shots

        # 4. 保存回 Film IR
        ir_manager.ir["userIntent"] = ir_manager.ir.get("userIntent", {})
        ir_manager.ir["userIntent"]["remixedLayer"] = remixed_layer
        ir_manager.save()

        print(f"✅ [Finalize] Saved {len(updated_shots)} shots to Film IR")

        # 4.5 同步到 workflow.json (解决数据源不一致问题)
        from core.workflow_io import load_workflow, save_workflow
        wf = load_workflow(job_dir)

        # 转换 Film IR 格式到 workflow 格式
        workflow_shots = []
        for shot in updated_shots:
            shot_id = shot.get("shotId", "shot_01")
            camera = shot.get("cameraPreserved", {})

            workflow_shots.append({
                "shot_id": shot_id,
                "frame_description": shot.get("visualDescription", ""),
                "content_analysis": shot.get("contentDescription", ""),
                "description": shot.get("I2V_VideoGen", "") or shot.get("visualDescription", ""),
                "start_time": shot.get("startTime", 0),
                "end_time": shot.get("endTime", 0),
                "assets": {
                    "first_frame": f"frames/{shot_id}.png",
                    "storyboard_frame": f"storyboard_frames/{shot_id}.png",
                    "video": None
                },
                "status": {
                    "stylize": "SUCCESS",  # storyboard frame 已生成
                    "video_generate": "NOT_STARTED"
                },
                "cinematography": {
                    "shot_type": camera.get("shotSize", ""),
                    "camera_angle": camera.get("cameraAngle", ""),
                    "camera_movement": camera.get("cameraMovement", ""),
                },
                "dialogue_text": shot.get("action", ""),
            })

        wf["shots"] = workflow_shots
        save_workflow(job_dir, wf)
        print(f"✅ [Finalize] Synced {len(workflow_shots)} shots to workflow.json")

        # 5. 验证 storyboard_frames 是否存在
        storyboard_frames_dir = job_dir / "storyboard_frames"
        frames_status = []
        missing_frames = []

        for shot in updated_shots:
            shot_id = shot["shotId"]
            frame_path = storyboard_frames_dir / f"{shot_id}.png"
            frame_exists = frame_path.exists()
            frames_status.append({
                "shotId": shot_id,
                "frameExists": frame_exists,
                "framePath": str(frame_path) if frame_exists else None
            })
            if not frame_exists:
                missing_frames.append(shot_id)

        # 6. 返回准备状态
        ready_for_video = len(missing_frames) == 0

        return {
            "jobId": job_id,
            "status": "finalized",
            "shotCount": len(updated_shots),
            "framesStatus": frames_status,
            "missingFrames": missing_frames,
            "readyForVideo": ready_for_video,
            "message": "All data synced to Film IR. Ready for video generation." if ready_for_video
                else f"Warning: {len(missing_frames)} frames are missing. Video generation may use fallback images."
        }

    except Exception as e:
        print(f"❌ [Finalize] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to finalize storyboard: {str(e)}")


# ============================================================
# M5: Asset Generation API
# ============================================================

# 资产生成状态追踪
asset_generation_tasks: Dict[str, Dict[str, Any]] = {}


def run_asset_generation_background(job_id: str):
    """后台运行资产生成"""
    try:
        asset_generation_tasks[job_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "progress": {"generated": 0, "failed": 0, "total": 0}
        }

        ir_manager = FilmIRManager(job_id)
        result = ir_manager._run_asset_generation()

        asset_generation_tasks[job_id] = {
            "status": "completed" if result.get("status") == "success" else result.get("status", "failed"),
            "completed_at": datetime.now().isoformat(),
            "result": result
        }

    except Exception as e:
        asset_generation_tasks[job_id] = {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        }


@app.post("/api/job/{job_id}/generate-assets")
async def trigger_asset_generation(job_id: str, background_tasks: BackgroundTasks):
    """
    触发资产生成 (M5)

    生成角色三视图和环境参考图，使用 Gemini 3 Pro Image。
    由于生成需要 20-40 秒，以后台任务方式运行。
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # 检查是否有 identity anchors
    ir_manager = FilmIRManager(job_id)
    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]

    characters = identity_anchors.get("characters", [])
    environments = identity_anchors.get("environments", [])

    if not characters and not environments:
        raise HTTPException(
            status_code=400,
            detail="No identity anchors found. Run intent injection (M4 remix) first."
        )

    # 检查是否已在运行
    if job_id in asset_generation_tasks:
        task = asset_generation_tasks[job_id]
        if task.get("status") == "running":
            return {
                "status": "already_running",
                "jobId": job_id,
                "message": "Asset generation is already in progress"
            }

    # 启动后台任务
    background_tasks.add_task(run_asset_generation_background, job_id)

    return {
        "status": "started",
        "jobId": job_id,
        "message": "Asset generation started",
        "assetsToGenerate": {
            "characters": len(characters),
            "characterViews": len(characters) * 3,
            "environments": len(environments),
            "total": len(characters) * 3 + len(environments)
        }
    }


@app.get("/api/job/{job_id}/assets/status")
async def get_asset_generation_status(job_id: str):
    """
    获取资产生成状态

    Returns:
        status: running / completed / failed / not_started
        progress: 生成进度
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job_id not in asset_generation_tasks:
        return {
            "jobId": job_id,
            "status": "not_started",
            "message": "Asset generation has not been started"
        }

    task = asset_generation_tasks[job_id]
    return {
        "jobId": job_id,
        **task
    }


@app.get("/api/job/{job_id}/assets")
async def get_generated_assets(job_id: str):
    """
    获取已生成的资产列表

    Returns:
        characters: 角色三视图路径
        environments: 环境参考图路径
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    assets_dir = job_dir / "assets"
    if not assets_dir.exists():
        return {
            "jobId": job_id,
            "assets": {
                "characters": [],
                "environments": []
            },
            "message": "No assets generated yet"
        }

    # 从 film_ir.json 获取资产信息
    ir_manager = FilmIRManager(job_id)
    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]

    characters = []
    for char in identity_anchors.get("characters", []):
        three_views = char.get("threeViews", {})
        characters.append({
            "anchorId": char.get("anchorId"),
            "name": char.get("name"),
            "status": char.get("status", "NOT_STARTED"),
            "threeViews": {
                "front": _to_asset_url(job_id, three_views.get("front")),
                "side": _to_asset_url(job_id, three_views.get("side")),
                "back": _to_asset_url(job_id, three_views.get("back"))
            }
        })

    environments = []
    for env in identity_anchors.get("environments", []):
        environments.append({
            "anchorId": env.get("anchorId"),
            "name": env.get("name"),
            "status": env.get("status", "NOT_STARTED"),
            "referenceImage": _to_asset_url(job_id, env.get("referenceImage"))
        })

    return {
        "jobId": job_id,
        "assets": {
            "characters": characters,
            "environments": environments
        },
        "assetsDir": f"/assets/{job_id}/assets"
    }


def _to_asset_url(job_id: str, file_path: Optional[str]) -> Optional[str]:
    """将本地文件路径转换为可访问的 URL"""
    if not file_path:
        return None

    # 从完整路径提取文件名
    file_name = Path(file_path).name
    # 返回完整的后端 URL，让前端可以跨域访问
    return f"{BASE_URL}/assets/{job_id}/assets/{file_name}"


# ============================================================
# M5.1: Single Entity Asset Management API (槽位级别操作)
# ============================================================

class UpdateDescriptionRequest(BaseModel):
    description: str


def _find_entity_by_id(ir_manager: FilmIRManager, entity_id: str):
    """
    查找实体：优先从 identityAnchors 查找（anchorId），
    如果找不到，再从 characterLedger/environmentLedger 查找（entityId）

    Returns:
        (entity_dict, entity_type, source) or (None, None, None)
        source: "anchor" or "ledger"
    """
    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]

    # 1. 先从 identityAnchors 中按 anchorId 查找
    for char in identity_anchors.get("characters", []):
        if char.get("anchorId") == entity_id:
            return char, "character", "anchor"

    for env in identity_anchors.get("environments", []):
        if env.get("anchorId") == entity_id:
            return env, "environment", "anchor"

    # 2. 再从 characterLedger/environmentLedger 中按 entityId 查找
    # 注意：characterLedger 在 II_narrativeTemplate 下
    narrative_template = ir_manager.ir["pillars"].get("II_narrativeTemplate", {})

    for char in narrative_template.get("characterLedger", []):
        if char.get("entityId") == entity_id:
            # 转换为 anchor 格式以便统一处理
            anchor_format = {
                "anchorId": char.get("entityId"),
                "anchorName": char.get("displayName"),
                "name": char.get("displayName"),
                "detailedDescription": char.get("detailedDescription") or char.get("visualSignature", ""),
                "threeViews": char.get("threeViews", {}),
                "_source": "ledger"  # 标记来源
            }
            return anchor_format, "character", "ledger"

    for env in narrative_template.get("environmentLedger", []):
        if env.get("entityId") == entity_id:
            # 转换为 anchor 格式以便统一处理
            anchor_format = {
                "anchorId": env.get("entityId"),
                "anchorName": env.get("displayName"),
                "name": env.get("displayName"),
                "detailedDescription": env.get("detailedDescription") or env.get("visualSignature", ""),
                "threeViews": env.get("threeViews", {}),
                "_source": "ledger"
            }
            return anchor_format, "environment", "ledger"

    return None, None, None


def _save_entity_three_views(ir_manager: FilmIRManager, entity_id: str, entity_type: str, source: str, three_views: dict):
    """
    保存实体的三视图数据到正确的位置
    """
    if source == "anchor":
        # 保存到 identityAnchors
        identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]
        entity_list = identity_anchors.get("characters" if entity_type == "character" else "environments", [])
        for entity in entity_list:
            if entity.get("anchorId") == entity_id:
                entity["threeViews"] = three_views
                ir_manager.save()
                return True
    else:
        # 保存到 characterLedger/environmentLedger (在 II_narrativeTemplate 下)
        narrative_template = ir_manager.ir["pillars"].get("II_narrativeTemplate", {})
        entity_list = narrative_template.get("characterLedger" if entity_type == "character" else "environmentLedger", [])
        for entity in entity_list:
            if entity.get("entityId") == entity_id:
                entity["threeViews"] = three_views
                ir_manager.save()
                return True
    return False


@app.get("/api/job/{job_id}/entity/{anchor_id}")
async def get_entity_state(job_id: str, anchor_id: str):
    """
    获取单个实体的完整状态（描述 + 三槽位）
    支持通过 anchorId（identityAnchors）或 entityId（characterLedger）查找

    Returns:
        anchorId, name, description, entityType, threeViews (with status per slot)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 使用辅助函数查找实体（支持 anchorId 和 entityId）
    entity, entity_type, source = _find_entity_by_id(ir_manager, anchor_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {anchor_id}")

    # 构建三视图状态
    if entity_type == "character":
        three_views = entity.get("threeViews", {})
        views = {
            "front": {
                "url": _to_asset_url(job_id, three_views.get("front")),
                "status": "uploaded" if three_views.get("front") else "empty"
            },
            "side": {
                "url": _to_asset_url(job_id, three_views.get("side")),
                "status": "uploaded" if three_views.get("side") else "empty"
            },
            "back": {
                "url": _to_asset_url(job_id, three_views.get("back")),
                "status": "uploaded" if three_views.get("back") else "empty"
            }
        }
    else:
        three_views = entity.get("threeViews", {})
        # 兼容旧的单图模式
        if not three_views and entity.get("referenceImage"):
            three_views = {"wide": entity.get("referenceImage")}
        views = {
            "wide": {
                "url": _to_asset_url(job_id, three_views.get("wide")),
                "status": "uploaded" if three_views.get("wide") else "empty"
            },
            "detail": {
                "url": _to_asset_url(job_id, three_views.get("detail")),
                "status": "uploaded" if three_views.get("detail") else "empty"
            },
            "alt": {
                "url": _to_asset_url(job_id, three_views.get("alt")),
                "status": "uploaded" if three_views.get("alt") else "empty"
            }
        }

    return {
        "jobId": job_id,
        "anchorId": anchor_id,
        "name": entity.get("name") or entity.get("anchorName", ""),
        "description": entity.get("detailedDescription", ""),
        "entityType": entity_type,
        "threeViews": views
    }


@app.put("/api/job/{job_id}/entity/{anchor_id}/description")
async def update_entity_description(job_id: str, anchor_id: str, request: UpdateDescriptionRequest):
    """
    更新实体的描述（用于 AI 生成时使用）
    支持通过 anchorId（identityAnchors）或 entityId（characterLedger）查找
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 使用辅助函数查找实体
    entity, entity_type, source = _find_entity_by_id(ir_manager, anchor_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {anchor_id}")

    # 根据来源更新描述
    updated = False
    if source == "anchor":
        identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]
        entity_list = identity_anchors.get("characters" if entity_type == "character" else "environments", [])
        for e in entity_list:
            if e.get("anchorId") == anchor_id:
                e["detailedDescription"] = request.description
                updated = True
                break
    else:
        # 更新 characterLedger/environmentLedger (在 II_narrativeTemplate 下)
        narrative_template = ir_manager.ir["pillars"].get("II_narrativeTemplate", {})
        entity_list = narrative_template.get("characterLedger" if entity_type == "character" else "environmentLedger", [])
        for e in entity_list:
            if e.get("entityId") == anchor_id:
                e["detailedDescription"] = request.description
                updated = True
                break

    if updated:
        ir_manager.save()

    return {
        "status": "success",
        "anchorId": anchor_id,
        "description": request.description
    }


@app.post("/api/job/{job_id}/upload-view/{anchor_id}/{view}")
async def upload_entity_view(job_id: str, anchor_id: str, view: str, file: UploadFile = File(...)):
    """
    上传图片到特定槽位
    支持通过 anchorId（identityAnchors）或 entityId（characterLedger）查找

    Args:
        view: 视图类型
            - 角色: front, side, back
            - 场景: wide, detail, alt
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # 验证视图类型
    valid_character_views = ["front", "side", "back"]
    valid_environment_views = ["wide", "detail", "alt"]
    all_valid_views = valid_character_views + valid_environment_views

    if view not in all_valid_views:
        raise HTTPException(status_code=400, detail=f"Invalid view type: {view}. Must be one of {all_valid_views}")

    # 保存文件
    assets_dir = job_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix or ".png"
    file_name = f"{anchor_id}_{view}{file_ext}"
    file_path = assets_dir / file_name

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 更新 film_ir.json - 使用辅助函数查找实体
    ir_manager = FilmIRManager(job_id)
    entity, entity_type, source = _find_entity_by_id(ir_manager, anchor_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {anchor_id}")

    # 获取或创建 threeViews
    three_views = entity.get("threeViews", {})
    three_views[view] = str(file_path)

    # 保存到正确的位置
    _save_entity_three_views(ir_manager, anchor_id, entity_type, source, three_views)

    return {
        "status": "success",
        "anchorId": anchor_id,
        "view": view,
        "filePath": str(file_path),
        "url": _to_asset_url(job_id, str(file_path))
    }


# 单实体生成任务追踪
entity_generation_tasks: Dict[str, Dict[str, Any]] = {}


class GenerateViewsRequest(BaseModel):
    force: bool = False  # 强制重新生成所有视图


@app.post("/api/job/{job_id}/generate-views/{anchor_id}")
async def generate_entity_views(
    job_id: str,
    anchor_id: str,
    background_tasks: BackgroundTasks,
    request: GenerateViewsRequest = None
):
    """
    AI 生成缺失的槽位（跳过已上传的）
    支持通过 anchorId（identityAnchors）或 entityId（characterLedger）查找

    Args:
        force: 如果为 True，则强制重新生成所有视图（忽略已存在的）

    会检查三个槽位的状态，只生成空槽位的图片。
    已上传的图片会作为 AI 生成的参考。
    """
    force = request.force if request else False
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 使用辅助函数查找实体（支持 anchorId 和 entityId）
    entity, entity_type, source = _find_entity_by_id(ir_manager, anchor_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {anchor_id}")

    # 检查哪些槽位需要生成
    three_views = entity.get("threeViews", {})

    if entity_type == "character":
        all_views = ["front", "side", "back"]
    else:
        all_views = ["wide", "detail", "alt"]

    # 如果 force=True，重新生成所有视图
    if force:
        missing_views = all_views
        three_views = {}  # 清空现有视图，全部重新生成
    else:
        missing_views = [v for v in all_views if not three_views.get(v)]

    if not missing_views:
        return {
            "status": "already_complete",
            "anchorId": anchor_id,
            "message": "All views already exist. Use force=true to regenerate."
        }

    # 检查是否已在生成
    task_key = f"{job_id}_{anchor_id}"
    if task_key in entity_generation_tasks:
        task = entity_generation_tasks[task_key]
        if task.get("status") == "running":
            return {
                "status": "already_running",
                "anchorId": anchor_id,
                "message": "Generation already in progress"
            }

    # 启动后台生成任务（传递 source 以便正确保存结果）
    background_tasks.add_task(
        run_entity_generation_background,
        job_id, anchor_id, entity_type, entity, missing_views, three_views, source
    )

    entity_generation_tasks[task_key] = {
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "missing_views": missing_views
    }

    return {
        "status": "started",
        "anchorId": anchor_id,
        "entityType": entity_type,
        "missingViews": missing_views,
        "existingViews": [v for v in all_views if v not in missing_views]
    }


def run_entity_generation_background(
    job_id: str,
    anchor_id: str,
    entity_type: str,
    entity: dict,
    missing_views: list,
    existing_views: dict,
    source: str = "anchor"
):
    """
    后台运行单实体资产生成

    Args:
        source: "anchor" 或 "ledger"，决定结果保存到哪里
    """
    task_key = f"{job_id}_{anchor_id}"

    try:
        from core.asset_generator import AssetGenerator

        generator = AssetGenerator(job_id, ".")

        # 重新从 film_ir.json 读取最新的实体信息（确保使用最新的描述）
        ir_manager = FilmIRManager(job_id)
        fresh_entity, _, _ = _find_entity_by_id(ir_manager, anchor_id)
        if fresh_entity:
            entity = fresh_entity  # 使用最新数据

        # 读取 Visual Style 配置
        render_strategy = ir_manager.ir["pillars"]["IV_renderStrategy"]
        visual_style_config = render_strategy.get("visualStyleConfig", {})
        visual_style = {
            "artStyle": visual_style_config.get("artStyle", ""),
            "colorPalette": visual_style_config.get("colorPalette", ""),
            "lightingMood": visual_style_config.get("lightingMood", ""),
            "cameraStyle": visual_style_config.get("cameraStyle", ""),
        }
        print(f"   🎨 Visual Style: {visual_style}")

        # 获取实体信息
        anchor_name = entity.get("name") or entity.get("anchorName", anchor_id)
        detailed_description = entity.get("detailedDescription", "")
        style_adaptation = entity.get("styleAdaptation", "")

        results = {}

        if entity_type == "character":
            # 收集已存在的图片作为参考
            reference_path = None
            if existing_views.get("front"):
                reference_path = existing_views["front"]
            elif existing_views.get("side"):
                reference_path = existing_views["side"]
            elif existing_views.get("back"):
                reference_path = existing_views["back"]

            # 生成缺失的角色视图
            results = generator.generate_character_views_selective(
                anchor_id=anchor_id,
                anchor_name=anchor_name,
                detailed_description=detailed_description,
                style_adaptation=style_adaptation,
                visual_style=visual_style,
                views_to_generate=missing_views,
                existing_views=existing_views,
                user_reference_path=reference_path
            )
        else:
            # 收集已存在的图片作为参考
            reference_path = None
            if existing_views.get("wide"):
                reference_path = existing_views["wide"]
            elif existing_views.get("detail"):
                reference_path = existing_views["detail"]
            elif existing_views.get("alt"):
                reference_path = existing_views["alt"]

            atmospheric_conditions = entity.get("atmosphericConditions", "")

            # 生成缺失的场景视图
            results = generator.generate_environment_views_selective(
                anchor_id=anchor_id,
                anchor_name=anchor_name,
                detailed_description=detailed_description,
                atmospheric_conditions=atmospheric_conditions,
                style_adaptation=style_adaptation,
                visual_style=visual_style,
                views_to_generate=missing_views,
                existing_views=existing_views,
                user_reference_path=reference_path
            )

        # 更新 film_ir.json - 根据 source 保存到正确的位置
        ir_manager = FilmIRManager(job_id)

        # 构建新的 threeViews
        new_three_views = dict(existing_views)  # 保留已有的
        for view_name, asset in results.items():
            if asset.file_path:
                new_three_views[view_name] = asset.file_path

        # 使用辅助函数保存
        _save_entity_three_views(ir_manager, anchor_id, entity_type, source, new_three_views)

        # 🔗 关键：同步到 identityAnchors（供 storyboard 生成使用）
        # 无论 source 是 "anchor" 还是 "ledger"，都要确保 identityAnchors 中有该角色
        if entity_type == "character":
            identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {
                "characters": [], "environments": []
            })
            if "characters" not in identity_anchors:
                identity_anchors["characters"] = []

            # 检查是否已存在
            existing_idx = next(
                (i for i, a in enumerate(identity_anchors["characters"]) if a.get("anchorId") == anchor_id),
                None
            )

            # 构建/更新角色锚点
            char_anchor = {
                "anchorId": anchor_id,
                "originalEntityId": anchor_id,
                "name": anchor_name,
                "detailedDescription": detailed_description,
                "styleAdaptation": style_adaptation,
                "threeViews": new_three_views,
                "status": "READY"
            }

            if existing_idx is not None:
                identity_anchors["characters"][existing_idx] = char_anchor
                print(f"   🔄 Updated character in identityAnchors: {anchor_id}")
            else:
                identity_anchors["characters"].append(char_anchor)
                print(f"   ➕ Added character to identityAnchors: {anchor_id}")

            ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"] = identity_anchors

            # 🔗 关键：更新 remixedLayer.shots 的 appliedAnchors
            # 根据 characterLedger 的 appearsInShots 信息，将角色绑定到对应镜头
            char_ledger = ir_manager.ir.get("pillars", {}).get("II_narrativeTemplate", {}).get("characterLedger", [])
            appears_in_shots = []
            for char in char_ledger:
                if char.get("entityId") == anchor_id:
                    appears_in_shots = char.get("appearsInShots", [])
                    break

            if appears_in_shots:
                remixed_layer = ir_manager.ir.get("userIntent", {}).get("remixedLayer", {})
                remixed_shots = remixed_layer.get("shots", [])
                for shot in remixed_shots:
                    shot_id = shot.get("shotId", "")
                    if shot_id in appears_in_shots:
                        applied = shot.setdefault("appliedAnchors", {"characters": [], "environments": []})
                        if anchor_id not in applied.get("characters", []):
                            applied.setdefault("characters", []).append(anchor_id)
                            print(f"   🔗 Linked {anchor_id} to {shot_id}.appliedAnchors.characters")

            ir_manager.save()

        # 更新任务状态
        entity_generation_tasks[task_key] = {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "results": {k: {"status": v.status.value, "path": v.file_path} for k, v in results.items()}
        }

    except Exception as e:
        entity_generation_tasks[task_key] = {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        }


@app.get("/api/job/{job_id}/generate-views/{anchor_id}/status")
async def get_entity_generation_status(job_id: str, anchor_id: str):
    """获取单实体生成状态"""
    task_key = f"{job_id}_{anchor_id}"

    if task_key not in entity_generation_tasks:
        return {
            "status": "not_started",
            "anchorId": anchor_id
        }

    return {
        "anchorId": anchor_id,
        **entity_generation_tasks[task_key]
    }


class MetaPromptRequest(BaseModel):
    key: str
    prompt: str


@app.post("/api/job/{job_id}/film_ir/meta_prompt")
async def set_meta_prompt(job_id: str, request: MetaPromptRequest):
    """
    设置 Meta Prompt (热更新)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    try:
        ir_manager.set_meta_prompt(request.key, request.prompt)
        return {"status": "success", "key": request.key}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/job/{job_id}/film_ir/hidden_template")
async def get_hidden_template(job_id: str):
    """
    获取隐形模板 (抽象层数据)
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)
    template = ir_manager.get_hidden_template()

    return template


# ============================================================
# Character Ledger & Identity Mapping API
# ============================================================

@app.get("/api/job/{job_id}/character-ledger")
async def get_character_ledger(job_id: str):
    """
    获取角色清单 (Character Ledger)
    用于前端 Video Analysis 阶段展示已识别的角色/实体
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 从 Pillar II 获取 character ledger
    pillar_ii = ir_manager.pillars.get("II_narrativeTemplate", {})

    character_ledger = pillar_ii.get("characterLedger", [])
    environment_ledger = pillar_ii.get("environmentLedger", [])
    ledger_summary = pillar_ii.get("ledgerSummary", {})

    # 从 Pillar IV 获取 identity mapping 状态
    pillar_iv = ir_manager.pillars.get("IV_renderStrategy", {})
    identity_mapping = pillar_iv.get("identityMapping", {})

    # 合并绑定状态到 ledger 数据
    characters_with_binding = []
    for char in character_ledger:
        entity_id = char.get("entityId")
        mapping = identity_mapping.get(entity_id, {})
        characters_with_binding.append({
            **char,
            "bindingStatus": mapping.get("bindingStatus", "UNBOUND"),
            "boundAsset": mapping.get("boundAsset")
        })

    environments_with_binding = []
    for env in environment_ledger:
        entity_id = env.get("entityId")
        mapping = identity_mapping.get(entity_id, {})
        environments_with_binding.append({
            **env,
            "bindingStatus": mapping.get("bindingStatus", "UNBOUND"),
            "boundAsset": mapping.get("boundAsset")
        })

    return {
        "jobId": job_id,
        "characterLedger": characters_with_binding,
        "environmentLedger": environments_with_binding,
        "summary": ledger_summary,
        "hasLedger": len(character_ledger) > 0 or len(environment_ledger) > 0
    }


class BindAssetRequest(BaseModel):
    entityId: str  # 原片实体 ID (orig_char_01, orig_env_01)
    assetType: str  # "uploaded" | "generated"
    assetPath: Optional[str] = None  # 上传资产的路径
    anchorId: Optional[str] = None  # 生成资产的 anchor ID
    anchorName: Optional[str] = None  # 替换后的名称
    detailedDescription: Optional[str] = None  # 详细描述（用于生成）


@app.post("/api/job/{job_id}/bind-asset")
async def bind_asset_to_entity(job_id: str, request: BindAssetRequest):
    """
    将资产绑定到原片实体

    实现"定向换头"的核心逻辑：
    - 用户选择原片实体 (orig_char_01)
    - 上传或生成替换资产
    - 后端更新 identityMapping 矩阵
    - 后续生成时自动应用到所有引用该实体的镜头
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # 获取 identity mapping
    identity_mapping = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityMapping", {})

    if request.entityId not in identity_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Entity not found: {request.entityId}. Run video analysis first."
        )

    # 更新绑定信息
    from datetime import datetime

    bound_asset = {
        "assetType": request.assetType,
        "assetPath": request.assetPath,
        "anchorId": request.anchorId or f"remix_{request.entityId.replace('orig_', '')}",
        "anchorName": request.anchorName,
        "detailedDescription": request.detailedDescription
    }

    identity_mapping[request.entityId]["boundAsset"] = bound_asset
    identity_mapping[request.entityId]["bindingStatus"] = "BOUND"
    identity_mapping[request.entityId]["bindingTimestamp"] = datetime.utcnow().isoformat() + "Z"

    # 同时更新 identityAnchors（用于资产生成）
    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {
        "characters": [],
        "environments": []
    })

    # 根据实体类型添加到对应列表
    if request.entityId.startswith("orig_char_"):
        # 检查是否已存在
        existing_idx = next(
            (i for i, a in enumerate(identity_anchors["characters"]) if a.get("anchorId") == bound_asset["anchorId"]),
            None
        )
        new_anchor = {
            "anchorId": bound_asset["anchorId"],
            "originalEntityId": request.entityId,
            "name": request.anchorName,
            "description": request.detailedDescription,
            "status": "PENDING" if request.assetType == "generated" else "UPLOADED",
            "assetPath": request.assetPath
        }
        if existing_idx is not None:
            identity_anchors["characters"][existing_idx] = new_anchor
        else:
            identity_anchors["characters"].append(new_anchor)

    elif request.entityId.startswith("orig_env_"):
        existing_idx = next(
            (i for i, a in enumerate(identity_anchors["environments"]) if a.get("anchorId") == bound_asset["anchorId"]),
            None
        )
        new_anchor = {
            "anchorId": bound_asset["anchorId"],
            "originalEntityId": request.entityId,
            "name": request.anchorName,
            "description": request.detailedDescription,
            "status": "PENDING" if request.assetType == "generated" else "UPLOADED",
            "assetPath": request.assetPath
        }
        if existing_idx is not None:
            identity_anchors["environments"][existing_idx] = new_anchor
        else:
            identity_anchors["environments"].append(new_anchor)

    ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"] = identity_anchors
    ir_manager.save()

    # 返回受影响的镜头
    original_entity = identity_mapping[request.entityId].get("originalEntity", {})
    affected_shots = original_entity.get("appearsInShots", [])

    return {
        "status": "success",
        "entityId": request.entityId,
        "boundAsset": bound_asset,
        "affectedShots": affected_shots,
        "message": f"Asset bound to {request.entityId}. Will affect {len(affected_shots)} shots."
    }


@app.delete("/api/job/{job_id}/bind-asset/{entity_id}")
async def unbind_asset(job_id: str, entity_id: str):
    """
    解除资产绑定
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    identity_mapping = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityMapping", {})

    if entity_id not in identity_mapping:
        raise HTTPException(status_code=400, detail=f"Entity not found: {entity_id}")

    # 清除绑定
    identity_mapping[entity_id]["boundAsset"] = None
    identity_mapping[entity_id]["bindingStatus"] = "UNBOUND"
    identity_mapping[entity_id]["bindingTimestamp"] = None

    ir_manager.save()

    return {
        "status": "success",
        "entityId": entity_id,
        "message": f"Asset unbound from {entity_id}"
    }


# ============================================================
# Sound Design API
# ============================================================

class SoundDesignRequest(BaseModel):
    voiceStyle: str = "Natural"
    voiceTone: str = "Warm and friendly"
    backgroundMusic: str = "Upbeat, modern electronic"
    soundEffects: str = "Subtle, ambient"
    enableAudioGeneration: bool = True  # 是否启用 Seed Dance 音频生成
    confirmed: bool = False


@app.get("/api/job/{job_id}/sound-design")
async def get_sound_design(job_id: str):
    """
    获取 Sound Design 配置
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # Get sound design config from Pillar IV
    render_strategy = ir_manager.ir["pillars"]["IV_renderStrategy"]
    sound_design = render_strategy.get("soundDesignConfig", {
        "voiceStyle": "Natural",
        "voiceTone": "Warm and friendly",
        "backgroundMusic": "Upbeat, modern electronic",
        "soundEffects": "Subtle, ambient",
        "enableAudioGeneration": True,
        "confirmed": False
    })

    return sound_design


@app.put("/api/job/{job_id}/sound-design")
async def save_sound_design(job_id: str, request: SoundDesignRequest):
    """
    保存 Sound Design 配置
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # Update config
    sound_design_config = {
        "voiceStyle": request.voiceStyle,
        "voiceTone": request.voiceTone,
        "backgroundMusic": request.backgroundMusic,
        "soundEffects": request.soundEffects,
        "enableAudioGeneration": request.enableAudioGeneration,
        "confirmed": request.confirmed
    }

    ir_manager.ir["pillars"]["IV_renderStrategy"]["soundDesignConfig"] = sound_design_config
    ir_manager.save()

    return {
        "status": "success",
        "soundDesignConfig": sound_design_config
    }


# ============================================================
# Visual Style API
# ============================================================

class VisualStyleRequest(BaseModel):
    artStyle: str = "Realistic"
    colorPalette: str = "Warm tones with high contrast"
    lightingMood: str = "Natural daylight"
    cameraStyle: str = "Dynamic with smooth transitions"
    confirmed: bool = False


@app.get("/api/job/{job_id}/visual-style")
async def get_visual_style(job_id: str):
    """
    获取 Visual Style 配置
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # Get visual style config from Pillar IV
    render_strategy = ir_manager.ir["pillars"]["IV_renderStrategy"]
    visual_style = render_strategy.get("visualStyleConfig", {
        "artStyle": "Realistic",
        "colorPalette": "Warm tones with high contrast",
        "lightingMood": "Natural daylight",
        "cameraStyle": "Dynamic with smooth transitions",
        "referenceImages": [],
        "confirmed": False
    })

    return visual_style


@app.put("/api/job/{job_id}/visual-style")
async def save_visual_style(job_id: str, request: VisualStyleRequest):
    """
    保存 Visual Style 配置
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # Get existing config to preserve reference images
    render_strategy = ir_manager.ir["pillars"]["IV_renderStrategy"]
    existing_config = render_strategy.get("visualStyleConfig", {})
    existing_images = existing_config.get("referenceImages", [])

    # Update config
    visual_style_config = {
        "artStyle": request.artStyle,
        "colorPalette": request.colorPalette,
        "lightingMood": request.lightingMood,
        "cameraStyle": request.cameraStyle,
        "referenceImages": existing_images,
        "confirmed": request.confirmed
    }

    ir_manager.ir["pillars"]["IV_renderStrategy"]["visualStyleConfig"] = visual_style_config
    ir_manager.save()

    return {
        "status": "success",
        "visualStyleConfig": visual_style_config
    }


@app.post("/api/job/{job_id}/visual-style/reference")
async def upload_visual_style_reference(job_id: str, file: UploadFile = File(...)):
    """
    上传 Visual Style 参考图片
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Create visual_style directory
    visual_style_dir = job_dir / "visual_style"
    visual_style_dir.mkdir(exist_ok=True)

    # Generate unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    ext = Path(file.filename).suffix or ".png"
    filename = f"reference_{timestamp}{ext}"
    file_path = visual_style_dir / filename

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Update film_ir.json
    ir_manager = FilmIRManager(job_id)
    render_strategy = ir_manager.ir["pillars"]["IV_renderStrategy"]

    if "visualStyleConfig" not in render_strategy:
        render_strategy["visualStyleConfig"] = {
            "artStyle": "Realistic",
            "colorPalette": "Warm tones with high contrast",
            "lightingMood": "Natural daylight",
            "cameraStyle": "Dynamic with smooth transitions",
            "referenceImages": [],
            "confirmed": False
        }

    # Add to reference images list (store relative path)
    relative_path = f"visual_style/{filename}"
    render_strategy["visualStyleConfig"]["referenceImages"].append(relative_path)
    ir_manager.save()

    return {
        "status": "success",
        "url": f"/assets/{job_id}/{relative_path}",
        "index": len(render_strategy["visualStyleConfig"]["referenceImages"]) - 1
    }


@app.delete("/api/job/{job_id}/visual-style/reference/{index}")
async def delete_visual_style_reference(job_id: str, index: int):
    """
    删除 Visual Style 参考图片
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)
    render_strategy = ir_manager.ir["pillars"]["IV_renderStrategy"]
    visual_style = render_strategy.get("visualStyleConfig", {})
    reference_images = visual_style.get("referenceImages", [])

    if index < 0 or index >= len(reference_images):
        raise HTTPException(status_code=400, detail=f"Invalid index: {index}")

    # Get file path and delete
    relative_path = reference_images[index]
    file_path = job_dir / relative_path
    if file_path.exists():
        file_path.unlink()

    # Remove from list
    reference_images.pop(index)
    ir_manager.save()

    return {
        "status": "success",
        "message": f"Reference image at index {index} deleted"
    }


# ============================================================
# Product Three-Views API
# ============================================================

class CreateProductRequest(BaseModel):
    name: str = ""
    description: str = ""


class UpdateProductRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@app.get("/api/job/{job_id}/products")
async def get_products(job_id: str):
    """
    获取所有产品列表
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # Get products from identity anchors
    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
    products = identity_anchors.get("products", [])

    return {
        "products": products,
        "count": len(products)
    }


@app.post("/api/job/{job_id}/products")
async def create_product(job_id: str, request: CreateProductRequest):
    """
    创建新产品
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    # Ensure identity anchors structure exists
    if "identityAnchors" not in ir_manager.ir["pillars"]["IV_renderStrategy"]:
        ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"] = {
            "characters": [],
            "environments": [],
            "products": []
        }

    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]

    if "products" not in identity_anchors:
        identity_anchors["products"] = []

    # Generate product ID
    existing_ids = [p.get("anchorId", "") for p in identity_anchors["products"]]
    product_num = 1
    while f"product_{product_num:03d}" in existing_ids:
        product_num += 1
    product_id = f"product_{product_num:03d}"

    # Create product
    new_product = {
        "anchorId": product_id,
        "name": request.name or f"Product {product_num}",
        "description": request.description,
        "threeViews": {
            "front": None,
            "side": None,
            "back": None
        },
        "status": "NOT_STARTED"
    }

    identity_anchors["products"].append(new_product)
    ir_manager.save()

    return {
        "status": "success",
        "product": new_product
    }


@app.put("/api/job/{job_id}/products/{product_id}")
async def update_product(job_id: str, product_id: str, request: UpdateProductRequest):
    """
    更新产品信息
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
    products = identity_anchors.get("products", [])

    # Find product
    product_idx = next((i for i, p in enumerate(products) if p.get("anchorId") == product_id), None)
    if product_idx is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

    # Update fields
    if request.name is not None:
        products[product_idx]["name"] = request.name
    if request.description is not None:
        products[product_idx]["description"] = request.description

    ir_manager.save()

    return {
        "status": "success",
        "product": products[product_idx]
    }


@app.delete("/api/job/{job_id}/products/{product_id}")
async def delete_product(job_id: str, product_id: str):
    """
    删除产品
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
    products = identity_anchors.get("products", [])

    # Find and remove product
    product_idx = next((i for i, p in enumerate(products) if p.get("anchorId") == product_id), None)
    if product_idx is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

    # Delete associated files
    three_views_dir = job_dir / "three_views" / product_id
    if three_views_dir.exists():
        shutil.rmtree(three_views_dir)

    # Remove from list
    products.pop(product_idx)
    ir_manager.save()

    return {
        "status": "success",
        "message": f"Product {product_id} deleted"
    }


@app.post("/api/job/{job_id}/products/{product_id}/upload/{view}")
async def upload_product_view(job_id: str, product_id: str, view: str, file: UploadFile = File(...)):
    """
    上传产品三视图
    view: front | side | back
    """
    if view not in ["front", "side", "back"]:
        raise HTTPException(status_code=400, detail=f"Invalid view: {view}. Must be front, side, or back.")

    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
    products = identity_anchors.get("products", [])

    # Find product
    product_idx = next((i for i, p in enumerate(products) if p.get("anchorId") == product_id), None)
    if product_idx is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

    # Create directory
    three_views_dir = job_dir / "three_views" / product_id
    three_views_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    ext = Path(file.filename).suffix or ".png"
    filename = f"{view}{ext}"
    file_path = three_views_dir / filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Update product
    relative_path = f"three_views/{product_id}/{filename}"
    products[product_idx]["threeViews"][view] = relative_path

    # Update status
    three_views = products[product_idx]["threeViews"]
    if all([three_views.get("front"), three_views.get("side"), three_views.get("back")]):
        products[product_idx]["status"] = "SUCCESS"

    ir_manager.save()

    return {
        "status": "success",
        "url": f"/assets/{job_id}/{relative_path}",
        "view": view
    }


@app.get("/api/job/{job_id}/products/{product_id}/state")
async def get_product_state(job_id: str, product_id: str):
    """
    获取产品状态（用于轮询生成进度）
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
    products = identity_anchors.get("products", [])

    # Find product
    product = next((p for p in products if p.get("anchorId") == product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

    # Build URLs for three views
    three_views = product.get("threeViews", {})
    three_views_with_urls = {}
    for view_name in ["front", "side", "back"]:
        path = three_views.get(view_name)
        if path:
            three_views_with_urls[view_name] = {
                "path": path,
                "url": f"/assets/{job_id}/{path}"
            }
        else:
            three_views_with_urls[view_name] = None

    return {
        "anchorId": product_id,
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "status": product.get("status", "NOT_STARTED"),
        "threeViews": three_views_with_urls
    }


class GenerateProductViewsRequest(BaseModel):
    force: bool = False


@app.post("/api/job/{job_id}/products/{product_id}/generate-views")
async def generate_product_views(
    job_id: str,
    product_id: str,
    request: GenerateProductViewsRequest,
    background_tasks: BackgroundTasks
):
    """
    AI 生成产品三视图
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
    products = identity_anchors.get("products", [])

    # Find product
    product_idx = next((i for i, p in enumerate(products) if p.get("anchorId") == product_id), None)
    if product_idx is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

    product = products[product_idx]

    # Check if already complete
    if product.get("status") == "SUCCESS" and not request.force:
        return {
            "status": "already_complete",
            "message": "Product views already generated. Use force=true to regenerate."
        }

    # Check description
    if not product.get("description", "").strip():
        raise HTTPException(status_code=400, detail="Product description is required for AI generation")

    # Set status to generating
    products[product_idx]["status"] = "GENERATING"
    ir_manager.save()

    # Run generation in background
    background_tasks.add_task(
        run_product_generation_background,
        job_id,
        product_id,
        product.get("description", "")
    )

    return {
        "status": "processing",
        "message": "Product three-views generation started"
    }


def run_product_generation_background(job_id: str, product_id: str, description: str):
    """
    后台任务：生成产品三视图
    """
    from core.asset_generator import generate_product_views_with_imagen

    job_dir = Path("jobs") / job_id
    three_views_dir = job_dir / "three_views" / product_id
    three_views_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Generate three views using Imagen
        results = generate_product_views_with_imagen(
            description=description,
            output_dir=str(three_views_dir)
        )

        # Update film_ir.json
        ir_manager = FilmIRManager(job_id)
        identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
        products = identity_anchors.get("products", [])

        product_idx = next((i for i, p in enumerate(products) if p.get("anchorId") == product_id), None)
        if product_idx is not None:
            products[product_idx]["threeViews"] = {
                "front": f"three_views/{product_id}/front.png" if results.get("front") else None,
                "side": f"three_views/{product_id}/side.png" if results.get("side") else None,
                "back": f"three_views/{product_id}/back.png" if results.get("back") else None
            }
            products[product_idx]["status"] = "SUCCESS"
            ir_manager.save()

    except Exception as e:
        print(f"Product generation error: {e}")
        # Update status to failed
        try:
            ir_manager = FilmIRManager(job_id)
            identity_anchors = ir_manager.ir["pillars"]["IV_renderStrategy"].get("identityAnchors", {})
            products = identity_anchors.get("products", [])
            product_idx = next((i for i, p in enumerate(products) if p.get("anchorId") == product_id), None)
            if product_idx is not None:
                products[product_idx]["status"] = "FAILED"
                ir_manager.save()
        except:
            pass


@app.get("/api/job/{job_id}/shot-analysis-status")
async def get_shot_analysis_status(job_id: str):
    """
    获取 Shot Recipe 分析状态，包括降级批次信息
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    shot_recipe = ir_manager.ir["pillars"]["III_shotRecipe"]
    analysis_metadata = shot_recipe.get("_analysisMetadata", {})
    degraded_batches = analysis_metadata.get("degradedBatches", [])
    shots = shot_recipe.get("concrete", {}).get("shots", [])

    # 统计降级 shot
    degraded_shot_ids = []
    for batch in degraded_batches:
        degraded_shot_ids.extend(batch.get("shotIds", []))

    return {
        "totalShots": len(shots),
        "degradedShots": analysis_metadata.get("degradedShots", 0),
        "degradedBatches": degraded_batches,
        "degradedShotIds": degraded_shot_ids,
        "canRetry": len(degraded_batches) > 0,
        "twoPhaseAnalysis": analysis_metadata.get("twoPhaseAnalysis", False)
    }


class RetryBatchRequest(BaseModel):
    batchIndex: Optional[int] = None  # None = retry all degraded batches


@app.post("/api/job/{job_id}/retry-shot-analysis")
async def retry_shot_analysis(job_id: str, request: RetryBatchRequest = None):
    """
    重试失败的 Shot Recipe 批次分析

    可选指定 batchIndex 重试单个批次，否则重试所有降级批次
    """
    import os
    from google import genai
    from google.genai import types as genai_types

    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    ir_manager = FilmIRManager(job_id)

    shot_recipe = ir_manager.ir["pillars"]["III_shotRecipe"]
    analysis_metadata = shot_recipe.get("_analysisMetadata", {})
    degraded_batches = analysis_metadata.get("degradedBatches", [])

    if not degraded_batches:
        return {
            "status": "success",
            "message": "No degraded batches to retry",
            "retriedCount": 0
        }

    # 确定要重试的批次
    if request and request.batchIndex is not None:
        batches_to_retry = [b for b in degraded_batches if b["batchIndex"] == request.batchIndex]
        if not batches_to_retry:
            raise HTTPException(status_code=400, detail=f"Batch {request.batchIndex} not found in degraded batches")
    else:
        batches_to_retry = degraded_batches

    # 获取视频文件路径
    video_path = job_dir / "original.mp4"
    if not video_path.exists():
        # 尝试其他格式
        for ext in [".mov", ".avi", ".webm"]:
            alt_path = job_dir / f"original{ext}"
            if alt_path.exists():
                video_path = alt_path
                break

    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file not found for retry")

    # 初始化 Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")
    # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
    api_key = api_key.strip()
    api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())

    client = genai.Client(api_key=api_key)

    # 上传视频
    try:
        import time
        uploaded_file = client.files.upload(file=str(video_path))
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(3)
            uploaded_file = client.files.get(name=uploaded_file.name)
        if uploaded_file.state.name != "ACTIVE":
            raise HTTPException(status_code=500, detail="Video processing failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video upload failed: {e}")

    # 重试每个降级批次
    from core.meta_prompts import SHOT_DETAIL_BATCH_PROMPT, create_shot_boundaries_text

    # 需要获取 Phase 1 的 shots_basic 数据
    shots_concrete = shot_recipe.get("concrete", {}).get("shots", [])
    total_shots = len(shots_concrete)

    # 将 concrete shots 转换为 basic 格式 (用于 create_shot_boundaries_text)
    shots_basic = []
    for s in shots_concrete:
        shots_basic.append({
            "shotId": s.get("shotId"),
            "startTime": s.get("startTime"),
            "endTime": s.get("endTime"),
            "durationSeconds": s.get("durationSeconds"),
            "briefSubject": s.get("subject", "")[:50] if s.get("subject") else "",
            "briefScene": s.get("scene", "")[:50] if s.get("scene") else ""
        })

    retried_count = 0
    still_degraded = []
    successful_batches = []

    for batch in batches_to_retry:
        batch_idx = batch["batchIndex"]
        start_idx = batch["startIdx"]
        end_idx = batch["endIdx"]

        print(f"🔄 Retrying batch {batch_idx + 1} (shots {start_idx + 1}-{end_idx})...")

        shot_boundaries = create_shot_boundaries_text(shots_basic, start_idx, end_idx)
        batch_prompt = SHOT_DETAIL_BATCH_PROMPT.replace(
            "{batch_start}", str(start_idx + 1)
        ).replace(
            "{batch_end}", str(end_idx)
        ).replace(
            "{total_shots}", str(total_shots)
        ).replace(
            "{shot_boundaries}", shot_boundaries
        ).replace(
            "{input_content}",
            "[Video file attached - extract detailed parameters for specified shots]"
        )

        try:
            import json
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[batch_prompt, uploaded_file],
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            batch_result = json.loads(response.text)

            # 更新 shots 数据
            for detailed_shot in batch_result.get("shots", []):
                shot_id = detailed_shot.get("shotId")
                # 找到对应的 shot 并更新
                for i, s in enumerate(shots_concrete):
                    if s.get("shotId") == shot_id:
                        # 更新 concrete 字段
                        s["firstFrameDescription"] = detailed_shot.get("concrete", {}).get("firstFrameDescription", s.get("firstFrameDescription", ""))
                        s["subject"] = detailed_shot.get("concrete", {}).get("subject", s.get("subject", ""))
                        s["scene"] = detailed_shot.get("concrete", {}).get("scene", s.get("scene", ""))
                        s["camera"] = detailed_shot.get("concrete", {}).get("camera", s.get("camera", {}))
                        s["lighting"] = detailed_shot.get("concrete", {}).get("lighting", s.get("lighting", ""))
                        s["dynamics"] = detailed_shot.get("concrete", {}).get("dynamics", s.get("dynamics", ""))
                        s["audio"] = detailed_shot.get("concrete", {}).get("audio", s.get("audio", {}))
                        s["style"] = detailed_shot.get("concrete", {}).get("style", s.get("style", ""))
                        s["negative"] = detailed_shot.get("concrete", {}).get("negative", s.get("negative", ""))
                        # 移除降级标记
                        if "_degraded" in s:
                            del s["_degraded"]
                        break

            successful_batches.append(batch_idx)
            retried_count += 1
            print(f"✅ Batch {batch_idx + 1} retry successful")

        except Exception as e:
            print(f"❌ Batch {batch_idx + 1} retry failed: {e}")
            still_degraded.append(batch)

    # 更新 Film IR
    shot_recipe["concrete"]["shots"] = shots_concrete

    # 更新 degraded batches 列表
    remaining_degraded = [b for b in degraded_batches if b["batchIndex"] not in successful_batches]
    analysis_metadata["degradedBatches"] = remaining_degraded
    analysis_metadata["degradedShots"] = sum(
        b["endIdx"] - b["startIdx"] for b in remaining_degraded
    )
    shot_recipe["_analysisMetadata"] = analysis_metadata

    ir_manager.save()

    return {
        "status": "success",
        "retriedBatches": len(batches_to_retry),
        "successfulRetries": retried_count,
        "stillDegraded": len(remaining_degraded),
        "message": f"Retried {retried_count} batch(es). {len(remaining_degraded)} batch(es) still degraded."
    }


# --- 核心：防缓存中间件 ---
@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/assets"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# 挂载静态资源目录
app.mount("/assets", StaticFiles(directory="jobs", check_dir=False), name="assets")

if __name__ == "__main__":
    import uvicorn
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000)