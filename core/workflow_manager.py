# core/workflow_manager.py
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# 注意：这些导入直接指向你已经写好的 core 文件夹下的文件
from core.workflow_io import load_workflow, save_workflow
from core.changes import apply_global_style, replace_entity_reference
from core.runner import run_pipeline, run_stylize, run_video_generate

class WorkflowManager:
    def __init__(self, job_id: str, project_root: Optional[Path] = None):
        self.job_id = job_id
        # 自动定位项目根目录
        self.project_dir = project_root or Path(__file__).parent.parent
        self.job_dir = self.project_dir / "jobs" / job_id
        self.workflow: Dict[str, Any] = {}
        
        if (self.job_dir / "workflow.json").exists():
            self.load()
        else:
            print(f"⚠️ 警告：找不到 job 目录或 workflow.json：{self.job_dir}")

    def load(self):
        """从磁盘加载状态，并根据【文件新鲜度】自动修复状态"""
        self.workflow = load_workflow(self.job_dir)
        
        # 获取工作流最后一次被修改的时间（即你输入"黑客帝国"指令的时间）
        # 如果没有这个时间，我们取一个很旧的时间
        last_update_str = self.workflow.get("meta", {}).get("updated_at", "2000-01-01T00:00:00Z")
        
        # 将 ISO 时间字符串转为 Python 的时间戳
        try:
            from datetime import datetime
            last_update_ts = datetime.strptime(last_update_str, "%Y-%m-%dT%H:%M:%SZ").timestamp()
        except:
            last_update_ts = 0

        updated = False
        for shot in self.workflow.get("shots", []):
            sid = shot.get("shot_id")
            video_output_path = self.job_dir / "videos" / f"{sid}.mp4"
            
            # 核心逻辑：
            if video_output_path.exists():
                # 获取这个视频文件的最后修改时间
                file_mtime = os.path.getmtime(video_output_path)
                
                current_status = shot.get("status", {}).get("video_generate")
                
                # 判断标准：
                # 1. 视频文件必须比工作流更新（说明是针对新风格刚生成的）
                # 2. 或者当前状态确实卡在 RUNNING
                if file_mtime > last_update_ts and current_status != "SUCCESS":
                    shot.setdefault("status", {})["video_generate"] = "SUCCESS"
                    shot.setdefault("assets", {})["video"] = f"videos/{sid}.mp4"
                    updated = True
                    print(f"✨ 智能同步：检测到 {sid} 产生了新视频（早于指令时间），已更新状态。")
                
        if updated:
            self.save()
            
        return self.workflow

    def save(self):
        """将当前内存中的状态保存到磁盘，并更新更新时间"""
        # 记录最后更新时间，方便前端展示
        self.workflow.setdefault("meta", {})["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_workflow(self.job_dir, self.workflow)

    # --- 形态 3 的底座：参数化修改 ---
    def apply_agent_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收修改指令（来自 UI 表单或 Agent），执行修改并标记受影响节点。
        """
        op = action.get("op")
        affected_count = 0
        
        if op == "set_global_style":
            new_style = action.get("value")
            # 调用你 core/changes.py 里的逻辑
            affected_count = apply_global_style(self.workflow, new_style, cascade=True)
            
        elif op == "replace_entity_ref":
            ent_id = action.get("entity_id")
            new_ref = action.get("new_ref")
            # 调用你 core/changes.py 里的逻辑
            affected_count = replace_entity_reference(self.workflow, ent_id, new_ref)

        if affected_count > 0:
            self.save() # 修改完立即持久化
            
        return {"status": "success", "affected_shots": affected_count}

    # --- 形态 1 的底座：状态驱动执行 ---
    def run_node(self, node_type: str, shot_id: Optional[str] = None):
        """
        运行特定的工作流节点 (stylize 或 video_generate)
        """
        # 更新尝试次数
        self.workflow.setdefault("meta", {}).setdefault("attempts", 0)
        self.workflow["meta"]["attempts"] += 1
        
        if node_type == "stylize":
            # 调用你 core/runner.py 里的逻辑
            run_stylize(self.job_dir, self.workflow, target_shot=shot_id)
        elif node_type == "video_generate":
            # 调用你 core/runner.py 里的逻辑
            run_video_generate(self.job_dir, self.workflow, target_shot=shot_id)
        
        # 执行完后保存最新状态（比如 SUCCESS 或 FAILED）
        self.save()

    def _get_shot_by_id(self, shot_id: str) -> Optional[Dict]:
        for s in self.workflow.get("shots", []):
            if s.get("shot_id") == shot_id:
                return s
        return None