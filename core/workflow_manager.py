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
        """加载状态：支持 5 阶段状态对齐"""
        self.workflow = load_workflow(self.job_dir)
        
        # 确保存在 global_stages 字段（形态 1 所需）
        if "global_stages" not in self.workflow:
            self.workflow["global_stages"] = {
                "analyze": "SUCCESS",   # 假设初始化时已完成
                "extract": "SUCCESS",   # 假设初始化时已完成
                "stylize": "NOT_STARTED",
                "video_gen": "NOT_STARTED",
                "merge": "NOT_STARTED"
            }

        updated = False
        shots = self.workflow.get("shots", [])
        
        # 检查所有分镜的状态，用于更新 global_stages
        all_gen_success = True if shots else False
        any_gen_running = False

        for shot in shots:
            sid = shot.get("shot_id")
            video_output_path = self.job_dir / "videos" / f"{sid}.mp4"
            status_node = shot.get("status", {})
            current_status = status_node.get("video_generate")
            
            if current_status == "RUNNING" and video_output_path.exists():
                status_node["video_generate"] = "SUCCESS"
                shot.setdefault("assets", {})["video"] = f"videos/{sid}.mp4"
                updated = True
            elif current_status == "SUCCESS" and not video_output_path.exists():
                status_node["video_generate"] = "NOT_STARTED"
                shot.setdefault("assets", {})["video"] = None
                updated = True

            # 统计全局进度
            if status_node.get("video_generate") != "SUCCESS": all_gen_success = False
            if status_node.get("video_generate") == "RUNNING": any_gen_running = True

        # 更新全局阶段状态（形态 1 UI 会读取这个）
        new_stage_status = "SUCCESS" if all_gen_success else ("RUNNING" if any_gen_running else "NOT_STARTED")
        if self.workflow["global_stages"]["video_gen"] != new_stage_status:
            self.workflow["global_stages"]["video_gen"] = new_stage_status
            updated = True
        
        if updated:
            self.save()
        return self.workflow

    def save(self):
        self.workflow.setdefault("meta", {})["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_workflow(self.job_dir, self.workflow)

    def apply_agent_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """支持形态 2 (Agent) 和形态 3 (Form) 的修改逻辑"""
        op = action.get("op")
        affected_count = 0
        
        # 形态 2：全局风格修改
        if op == "set_global_style":
            new_style = action.get("value")
            affected_count = apply_global_style(self.workflow, new_style, cascade=True)
            if affected_count > 0:
                for shot in self.workflow.get("shots", []):
                    shot.setdefault("assets", {})["video"] = None 

        # 形态 3：单个分镜参数微调 (Higgsfield 风格)
        elif op == "update_shot_params":
            shot_id = action.get("shot_id")
            for shot in self.workflow.get("shots", []):
                if shot["shot_id"] == shot_id:
                    # 修改具体字段：prompt, model, duration 等
                    if "description" in action: shot["description"] = action["description"]
                    if "video_model" in action: shot.setdefault("config", {})["video_model"] = action["video_model"]
                    # 只要改了参数，该分镜就得重跑
                    shot["status"]["video_generate"] = "NOT_STARTED"
                    shot["assets"]["video"] = None
                    affected_count = 1
                    break

        if affected_count > 0:
            self.save()
        return {"status": "success", "affected_shots": affected_count}

    def run_node(self, node_type: str, shot_id: Optional[str] = None):
        """执行逻辑：自动更新全局阶段状态"""
        self.workflow["global_stages"]["video_gen"] = "RUNNING"
        self.save()

        if node_type == "video_generate":
            shots_to_clear = [s for s in self.workflow.get("shots", [])] if not shot_id else [s for s in self.workflow.get("shots", []) if s["shot_id"] == shot_id]
            for s in shots_to_clear:
                video_file = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                if video_file.exists(): os.remove(video_file)
                s["status"]["video_generate"] = "RUNNING"
                s["assets"]["video"] = None

        self.save()
        if node_type == "stylize":
            run_stylize(self.job_dir, self.workflow, target_shot=shot_id)
        elif node_type == "video_generate":
            run_video_generate(self.job_dir, self.workflow, target_shot=shot_id)
        
        # 跑完后通过 load() 自动更新 global_stages 状态
        self.load()