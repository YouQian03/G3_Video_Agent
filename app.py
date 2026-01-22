# app.py
import os
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union

from core.workflow_manager import WorkflowManager
from core.agent_engine import AgentEngine

app = FastAPI(title="AI 导演工作台 API")

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
app.mount("/assets", StaticFiles(directory="jobs"), name="assets")

if __name__ == "__main__":
    import uvicorn
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000)