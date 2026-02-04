# app.py
import os
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

    return {
        "shotNumber": shot_number,
        "firstFrameImage": first_frame,
        "visualDescription": visual_description,
        "contentDescription": shot.get("content_analysis", visual_description),
        "startSeconds": parse_time_to_seconds(shot.get("start_time", 0)),
        "endSeconds": parse_time_to_seconds(shot.get("end_time", 0)),
        "durationSeconds": parse_time_to_seconds(shot.get("end_time", 0)) - parse_time_to_seconds(shot.get("start_time", 0)),
        "shotSize": cinematography.get("shot_scale", "MEDIUM"),
        "cameraAngle": cinematography.get("subject_orientation", "facing-camera"),
        "cameraMovement": cinematography.get("motion_vector", "static"),
        "focalLengthDepth": cinematography.get("camera_type", "Static"),
        "lighting": shot.get("lighting") or cinematography.get("lighting", "Natural lighting"),
        "music": shot.get("music_mood", ""),
        "dialogueVoiceover": shot.get("dialogue_voiceover", "")
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
                    converted_shots.append({
                        "shot_id": shot_id,
                        "description": ir_shot.get("subject", "") + " " + ir_shot.get("scene", ""),
                        "start_time": ir_shot.get("startSeconds", 0),
                        "end_time": ir_shot.get("endSeconds", 0),
                        "assets": {
                            "first_frame": f"frames/{shot_id}.png",
                            "source_video_segment": f"source_segments/{shot_id}.mp4",
                            "stylized_frame": None,
                            "video": None
                        },
                        "cinematography": {
                            "shot_scale": ir_shot.get("shotScale", ""),
                            "camera_type": ir_shot.get("cameraMovement", ""),
                        },
                        "lighting": ir_shot.get("lighting", ""),
                        "music_mood": ir_shot.get("music", ""),
                        "dialogue_voiceover": ir_shot.get("dialogueVoiceover", ""),
                        "content_analysis": ir_shot.get("subject", ""),
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
    return f"http://localhost:8000/assets/{job_id}/assets/{file_name}"


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
                model="gemini-2.0-flash",
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