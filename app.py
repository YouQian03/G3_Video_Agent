# app.py
import os
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import re
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union

from core.workflow_manager import WorkflowManager
from core.agent_engine import AgentEngine

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
        
        print(f"🧠 [AI 启动] 正在调用 Gemini 1.5 Pro 拆解分镜，请耐心等待...")
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
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    manager.job_id = job_id
    manager.job_dir = job_dir
    workflow = manager.load()

    # 构建 base_url（用于资源路径）
    # 注意：在生产环境中应该从请求头或配置获取
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