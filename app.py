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

app = FastAPI(title="AI 爆款二创系统 API")

# 1. 解决跨域问题（方便前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 初始化核心引擎
# 暂时硬编码 job_id 为 demo_job_001
JOB_ID = "demo_job_001"
manager = WorkflowManager(JOB_ID)
agent = AgentEngine()

# --- 数据模型 ---
class ChatRequest(BaseModel):
    message: str

class ActionRequest(BaseModel):
    op: str
    value: Optional[str] = None
    entity_id: Optional[str] = None
    new_ref: Optional[str] = None
    shot_id: Optional[str] = None

# --- 路由接口 ---

@app.get("/")
async def read_index():
    """主页：直接返回前端 HTML 文件"""
    return FileResponse('index.html')

@app.get("/api/workflow")
async def get_workflow():
    """获取当前完整的工作流状态"""
    manager.load()  # 强迫指挥官重新读一遍硬盘上的 workflow.json
    return manager.workflow

@app.post("/api/agent/chat")
async def agent_chat(req: ChatRequest):
    """形态 2：Agent 对话接口"""
    wf = manager.load()
    summary = f"Style: {wf.get('global', {}).get('style_prompt')}\n"
    summary += f"Entities: {list(wf.get('entities', {}).keys())}"
    
    action = agent.get_action_from_text(req.message, summary)
    
    if action.get("op") not in ["none", "error"]:
        res = manager.apply_agent_action(action)
        return {"action": action, "result": res}
    else:
        return {"action": action, "result": {"status": "ignored", "reason": action.get("reason")}}

@app.post("/api/action")
async def manual_action(req: ActionRequest):
    """形态 3：直接参数修改接口"""
    res = manager.apply_agent_action(req.dict())
    return res

@app.post("/api/run/{node_type}")
async def run_task(node_type: str, background_tasks: BackgroundTasks, shot_id: Optional[str] = None):
    """形态 1：执行任务（异步运行）"""
    if node_type not in ["stylize", "video_generate"]:
        raise HTTPException(status_code=400, detail="无效的节点类型")
    
    background_tasks.add_task(manager.run_node, node_type, shot_id)
    return {"status": "started", "node": node_type, "shot_id": shot_id}

# 3. 挂载静态文件（放在路由后面，确保不遮挡 API）
# 映射 jobs 目录，让前端可以访问到图片和视频
app.mount("/assets", StaticFiles(directory=f"jobs/{JOB_ID}"), name="assets")

if __name__ == "__main__":
    import uvicorn
    # 启动命令：python app.py
    uvicorn.run(app, host="0.0.0.0", port=8000)