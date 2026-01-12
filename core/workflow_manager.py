# core/workflow_manager.py
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from core.workflow_io import load_workflow, save_workflow
from core.changes import apply_global_style, replace_entity_reference
from core.runner import run_pipeline, run_stylize, run_video_generate

class WorkflowManager:
    def __init__(self, job_id: str, project_root: Optional[Path] = None):
        self.job_id = job_id
        self.project_dir = project_root or Path(__file__).parent.parent
        self.job_dir = self.project_dir / "jobs" / job_id
        self.workflow: Dict[str, Any] = {}
        
        if (self.job_dir / "workflow.json").exists():
            self.load()

    def load(self):
        """加载状态：只有当任务确实在跑，且新文件出现了，才算 SUCCESS"""
        self.workflow = load_workflow(self.job_dir)
        
        updated = False
        for shot in self.workflow.get("shots", []):
            sid = shot.get("shot_id")
            video_output_path = self.job_dir / "videos" / f"{sid}.mp4"
            
            status_node = shot.get("status", {})
            current_status = status_node.get("video_generate")
            
            # --- 严谨同步逻辑 ---
            # 只有在 RUNNING 状态下，检测到视频文件【重新生成】了，才变绿
            if current_status == "RUNNING" and video_output_path.exists():
                status_node["video_generate"] = "SUCCESS"
                shot.setdefault("assets", {})["video"] = f"videos/{sid}.mp4"
                updated = True
                print(f"✨ 物理确认：分镜 {sid} 已由 AI 生成新视频，状态更正为 SUCCESS")
            
            # 如果状态是 SUCCESS 但文件没了，打回 NOT_STARTED
            elif current_status == "SUCCESS" and not video_output_path.exists():
                status_node["video_generate"] = "NOT_STARTED"
                shot.setdefault("assets", {})["video"] = None
                updated = True
        
        if updated:
            self.save()
            
        return self.workflow

    def save(self):
        self.workflow.setdefault("meta", {})["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_workflow(self.job_dir, self.workflow)

    def apply_agent_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """修改指令：改风格的同时，清空所有视频引用路径"""
        op = action.get("op")
        affected_count = 0
        
        if op == "set_global_style":
            new_style = action.get("value")
            affected_count = apply_global_style(self.workflow, new_style, cascade=True)
            if affected_count > 0:
                for shot in self.workflow.get("shots", []):
                    # 风格变了，旧视频预览必须消失
                    shot.setdefault("assets", {})["video"] = None 

        elif op == "replace_entity_ref":
            ent_id = action.get("entity_id")
            new_ref = action.get("new_ref")
            affected_count = replace_entity_reference(self.workflow, ent_id, new_ref)
            if affected_count > 0:
                for shot in self.workflow.get("shots", []):
                    if ent_id in shot.get("entities", []):
                        shot.setdefault("assets", {})["video"] = None

        if affected_count > 0:
            self.save()
        return {"status": "success", "affected_shots": affected_count}

    def run_node(self, node_type: str, shot_id: Optional[str] = None):
        """执行任务：在发起后台任务前，【立即】删除旧文件"""
        self.workflow.setdefault("meta", {}).setdefault("attempts", 0)
        self.workflow["meta"]["attempts"] += 1
        
        # --- 核心修复：防止秒变 SUCCESS ---
        # 如果是视频生成节点，我们直接在主进程里先把文件删了
        if node_type == "video_generate":
            shots_to_clear = []
            if shot_id:
                shots_to_clear = [s for s in self.workflow.get("shots", []) if s["shot_id"] == shot_id]
            else:
                shots_to_clear = self.workflow.get("shots", [])
            
            for s in shots_to_clear:
                video_file = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                if video_file.exists():
                    print(f"🗑️ 发令瞬间清理旧视频: {video_file}")
                    os.remove(video_file)
                # 立即标记状态并清空引用，确保下一秒轮询拿不到 SUCCESS
                s.setdefault("status", {})["video_generate"] = "RUNNING"
                s.setdefault("assets", {})["video"] = None

        self.save() # 删完立刻存盘，让前端轮询看到 RUNNING 且没文件的状态

        # 启动后台任务
        if node_type == "stylize":
            run_stylize(self.job_dir, self.workflow, target_shot=shot_id)
        elif node_type == "video_generate":
            run_video_generate(self.job_dir, self.workflow, target_shot=shot_id)
        
        self.save()

    def _get_shot_by_id(self, shot_id: str) -> Optional[Dict]:
        for s in self.workflow.get("shots", []):
            if s.get("shot_id") == shot_id:
                return s
        return None