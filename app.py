# app.py
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

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
JOB_ID = "demo_job_001"
manager = WorkflowManager(JOB_ID)
agent = AgentEngine()

# --- 数据模型 ---
class ChatRequest(BaseModel):
    message: str

class ShotUpdateRequest(BaseModel):
    shot_id: str
    description: Optional[str] = None
    video_model: Optional[str] = None

# --- 路由接口 ---

@app.get("/")
async def read_index():
    """入口：返回主页"""
    return FileResponse('index.html')

@app.get("/api/workflow")
async def get_workflow():
    """形态 1 & 3 的数据源：获取最新全局状态"""
    return manager.load()

@app.post("/api/agent/chat")
async def agent_chat(req: ChatRequest):
    """形态 2：Agent 全局指挥"""
    wf = manager.load()
    summary = f"Style: {wf.get('global', {}).get('style_prompt')}\n"
    summary += f"Entities: {list(wf.get('entities', {}).keys())}"
    
    action = agent.get_action_from_text(req.message, summary)
    
    if action.get("op") not in ["none", "error"]:
        res = manager.apply_agent_action(action)
        return {"action": action, "result": res}
    return {"action": action, "result": {"status": "ignored"}}

@app.post("/api/shot/update")
async def update_shot_params(req: ShotUpdateRequest):
    """形态 3：手动微调单个分镜"""
    action = {
        "op": "update_shot_params",
        "shot_id": req.shot_id,
    }
    if req.description: action["description"] = req.description
    if req.video_model: action["video_model"] = req.video_model
    
    res = manager.apply_agent_action(action)
    return res

@app.post("/api/run/{node_type}")
async def run_task(node_type: str, background_tasks: BackgroundTasks, shot_id: Optional[str] = None):
    """形态 1 的执行引擎：支持异步运行任务"""
    if node_type not in ["stylize", "video_generate"]:
        raise HTTPException(status_code=400, detail="无效的节点类型")
    
    # 异步执行，不阻塞前端
    background_tasks.add_task(manager.run_node, node_type, shot_id)
    return {"status": "started", "node": node_type, "shot_id": shot_id}

# 3. 静态资源挂载
# ... 前面的代码保持不变 ...

# --- 核心修复：添加防缓存中间件 ---
@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    # 如果请求的是 assets 文件夹下的资源（视频/图片）
    if request.url.path.startswith("/assets"):
        # 强行注入“禁止缓存”头
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# 挂载静态文件
app.mount("/assets", StaticFiles(directory=f"jobs/{JOB_ID}"), name="assets")

if __name__ == "__main__":
    import uvicorn
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000)