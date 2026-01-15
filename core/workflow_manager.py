# core/workflow_manager.py
import json
import time
import os
import re
import uuid
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from core.workflow_io import load_workflow, save_workflow
from core.changes import apply_global_style, replace_entity_reference
from core.runner import run_pipeline, run_stylize, run_video_generate

# 引入拆解所需的库和逻辑
from google import genai
from analyze_video import DIRECTOR_METAPROMPT, wait_until_file_active, extract_json_array
from extract_frames import to_seconds

class WorkflowManager:
    def __init__(self, job_id: Optional[str] = None, project_root: Optional[Path] = None):
        self.project_dir = project_root or Path(__file__).parent.parent
        self.job_id = job_id
        self.workflow: Dict[str, Any] = {}
        
        if job_id:
            self.job_dir = self.project_dir / "jobs" / job_id
            if (self.job_dir / "workflow.json").exists():
                self.load()

    def initialize_from_file(self, temp_video_path: Path) -> str:
        """全自动初始化管线"""
        new_id = f"job_{uuid.uuid4().hex[:8]}"
        self.job_id = new_id
        self.job_dir = self.project_dir / "jobs" / new_id
        
        self.job_dir.mkdir(parents=True, exist_ok=True)
        (self.job_dir / "frames").mkdir(exist_ok=True)
        (self.job_dir / "videos").mkdir(exist_ok=True)
        (self.job_dir / "source_segments").mkdir(exist_ok=True)
        
        final_video_path = self.job_dir / "input.mp4"
        shutil.move(str(temp_video_path), str(final_video_path))
        
        print(f"🚀 [Phase 1] 正在通过 Gemini 拆解视频: {new_id}...")
        storyboard = self._run_gemini_analysis(final_video_path)
        
        print(f"🚀 [Phase 2] 正在提取关键帧与原始分镜短片...")
        self._run_ffmpeg_extraction(final_video_path, storyboard)
        
        shots = []
        for s in storyboard:
            shot_num = int(s.get("shot_number", 1))
            sid = f"shot_{shot_num:02d}"
            shots.append({
                "shot_id": sid,
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "description": s.get("frame_description") or s.get("content_analysis"),
                "entities": [],
                "assets": {
                    "first_frame": f"frames/{sid}.png",
                    "source_video_segment": f"source_segments/{sid}.mp4",
                    "stylized_frame": f"frames/{sid}.png",
                    "video": None
                },
                "status": {"video_generate": "NOT_STARTED"}
            })
            
        self.workflow = {
            "job_id": new_id,
            "source_video": "input.mp4",
            "global": {"style_prompt": "Cinematic Realistic", "video_model": "veo"},
            "global_stages": {
                "analyze": "SUCCESS", "extract": "SUCCESS", 
                "stylize": "NOT_STARTED", "video_gen": "NOT_STARTED", "merge": "NOT_STARTED"
            },
            "shots": shots,
            "meta": {"attempts": 0, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        }
        
        self.save()
        print(f"✅ [Done] 视频拆解与切片完成，Job ID: {new_id}")
        return new_id

    def _run_gemini_analysis(self, video_path: Path):
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        uploaded = client.files.upload(file=str(video_path))
        video_file = wait_until_file_active(client, uploaded)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[DIRECTOR_METAPROMPT, video_file],
        )
        return extract_json_array(response.text)

    def _run_ffmpeg_extraction(self, video_path: Path, storyboard: List):
        ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
        for s in storyboard:
            ts = to_seconds(s.get("start_time"))
            duration = to_seconds(s.get("end_time")) - ts
            sid = f"shot_{int(s['shot_number']):02d}"
            img_out = self.job_dir / "frames" / f"{sid}.png"
            subprocess.run([ffmpeg_path, "-y", "-ss", str(ts), "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(img_out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            video_segment_out = self.job_dir / "source_segments" / f"{sid}.mp4"
            subprocess.run([ffmpeg_path, "-y", "-ss", str(ts), "-t", str(duration), "-i", str(video_path), "-c", "copy", str(video_segment_out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def load(self):
        """加载状态并对齐物理文件状态"""
        self.workflow = load_workflow(self.job_dir)
        if "global_stages" not in self.workflow:
            self.workflow["global_stages"] = {"analyze": "SUCCESS", "extract": "SUCCESS", "stylize": "NOT_STARTED", "video_gen": "NOT_STARTED", "merge": "NOT_STARTED"}

        updated = False
        for shot in self.workflow.get("shots", []):
            sid = shot.get("shot_id")
            video_output_path = self.job_dir / "videos" / f"{sid}.mp4"
            status_node = shot.get("status", {})
            current_status = status_node.get("video_generate")
            
            # 💡 只有在 RUNNING 状态下检测到新文件才变绿
            if current_status == "RUNNING" and video_output_path.exists():
                status_node["video_generate"] = "SUCCESS"
                shot.setdefault("assets", {})["video"] = f"videos/{sid}.mp4"
                updated = True
            # 如果标记为成功但文件丢失，重置状态
            elif current_status == "SUCCESS" and not video_output_path.exists():
                status_node["video_generate"] = "NOT_STARTED"
                shot.setdefault("assets", {})["video"] = None
                updated = True
        
        if updated: self.save()
        return self.workflow

    def save(self):
        self.workflow.setdefault("meta", {})["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_workflow(self.job_dir, self.workflow)

    def apply_agent_action(self, action: Union[Dict, List]) -> Dict[str, Any]:
        """处理 Agent 指令或手动精修指令"""
        actions = action if isinstance(action, list) else [action]
        total_affected = 0
        for act in actions:
            op = act.get("op")
            
            if op == "set_global_style":
                affected = apply_global_style(self.workflow, act.get("value"), cascade=True)
                if affected > 0:
                    for s in self.workflow.get("shots", []):
                        # 💡 风格变了，物理删除旧视频，防止 load() 误判
                        v_path = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                        if v_path.exists(): os.remove(v_path)
                        s.setdefault("assets", {})["video"] = None
                total_affected += affected
                
            elif op == "global_subject_swap":
                old_s = act.get("old_subject", "").lower()
                new_s = act.get("new_subject", "").lower()
                if old_s and new_s:
                    for s in self.workflow.get("shots", []):
                        if old_s in s["description"].lower():
                            s["description"] = re.sub(old_s, new_s, s["description"], flags=re.IGNORECASE)
                            s["status"]["video_generate"] = "NOT_STARTED"
                            # 💡 内容变了，物理删除旧视频
                            v_path = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                            if v_path.exists(): os.remove(v_path)
                            s["assets"]["video"] = None
                            total_affected += 1
                            
            elif op == "update_shot_params":
                sid = act.get("shot_id")
                for s in self.workflow.get("shots", []):
                    if s["shot_id"] == sid:
                        if "description" in act: s["description"] = act["description"]
                        s["status"]["video_generate"] = "NOT_STARTED"
                        # 💡 手动精修了，物理删除旧视频，确保保存生效
                        v_path = self.job_dir / "videos" / f"{sid}.mp4"
                        if v_path.exists(): os.remove(v_path)
                        s["assets"]["video"] = None
                        total_affected += 1
                        break
                        
        if total_affected > 0: self.save()
        return {"status": "success", "affected_shots": total_affected}

    def run_node(self, node_type: str, shot_id: Optional[str] = None):
        """执行工作流节点"""
        self.workflow["global_stages"]["video_gen"] = "RUNNING"
        self.workflow.setdefault("meta", {}).setdefault("attempts", 0)
        self.workflow["meta"]["attempts"] += 1
        
        if node_type == "video_generate":
            shots = [s for s in self.workflow.get("shots", []) if not shot_id or s["shot_id"] == shot_id]
            for s in shots:
                video_file = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                if video_file.exists(): os.remove(video_file)
                s["status"]["video_generate"] = "RUNNING"
                s["assets"]["video"] = None

        self.save()
        if node_type == "stylize": run_stylize(self.job_dir, self.workflow, target_shot=shot_id)
        elif node_type == "video_generate": run_video_generate(self.job_dir, self.workflow, target_shot=shot_id)
        self.load()

    def _get_shot_by_id(self, shot_id: str) -> Optional[Dict]:
        for s in self.workflow.get("shots", []):
            if s.get("shot_id") == shot_id: return s
        return None