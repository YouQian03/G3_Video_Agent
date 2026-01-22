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
        """全自动初始化管线：完成拆解与原始素材提取"""
        new_id = f"job_{uuid.uuid4().hex[:8]}"
        self.job_id = new_id
        self.job_dir = self.project_dir / "jobs" / new_id
        
        self.job_dir.mkdir(parents=True, exist_ok=True)
        (self.job_dir / "frames").mkdir(exist_ok=True)
        (self.job_dir / "videos").mkdir(exist_ok=True)
        (self.job_dir / "source_segments").mkdir(exist_ok=True)
        (self.job_dir / "stylized_frames").mkdir(exist_ok=True)
        
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
                    "stylized_frame": None, # 💡 PM逻辑：初始化为空，强制触发 AI 生图流程
                    "video": None
                },
                "status": {
                    "stylize": "NOT_STARTED",
                    "video_generate": "NOT_STARTED"
                }
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
        raw_shots = extract_json_array(response.text)

        # 语义化合并：减少过度分镜
        merged_shots = self._merge_semantic_shots(raw_shots, client)
        return merged_shots

    def _merge_semantic_shots(self, shots: List[Dict], client) -> List[Dict]:
        """
        语义化合并：将连续的、背景/角度/主体相似的分镜合并为一个完整分镜。
        使用 AI 判断哪些连续分镜应该合并。
        """
        if len(shots) <= 1:
            return shots

        # 构建合并判断提示
        shots_summary = []
        for i, s in enumerate(shots):
            shots_summary.append({
                "index": i,
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "description": s.get("frame_description") or s.get("content_analysis"),
                "shot_type": s.get("shot_type"),
                "camera_angle": s.get("camera_angle"),
                "camera_movement": s.get("camera_movement")
            })

        merge_prompt = f"""你是一位专业的影视剪辑师。请分析以下分镜列表，判断哪些**连续的**分镜应该合并。

合并条件（必须同时满足）：
1. 分镜是**连续的**（index 相邻）
2. 场景/背景没有显著变化
3. 主体/角色没有切换
4. 机位角度没有明显变化
5. 属于同一个完整动作或事件

分镜列表：
{json.dumps(shots_summary, ensure_ascii=False, indent=2)}

请输出需要合并的分镜组，格式为纯JSON数组，每个元素是一个需要合并的index数组。
例如：[[0,1,2], [5,6]] 表示将0-1-2合并为一个分镜，5-6合并为一个分镜。
如果没有需要合并的，输出空数组 []。
仅输出纯JSON，不要任何解释。"""

        try:
            merge_response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[merge_prompt],
            )
            merge_text = merge_response.text.strip()

            # 提取JSON数组
            if merge_text.startswith("["):
                merge_groups = json.loads(merge_text)
            else:
                l = merge_text.find("[")
                r = merge_text.rfind("]")
                if l != -1 and r != -1:
                    merge_groups = json.loads(merge_text[l:r+1])
                else:
                    merge_groups = []

            if not merge_groups:
                print(f"📊 语义分析：无需合并，保留 {len(shots)} 个分镜")
                return shots

            # 执行合并
            merged_indices = set()
            for group in merge_groups:
                if isinstance(group, list) and len(group) > 1:
                    merged_indices.update(group[1:])  # 除了第一个，其余标记为被合并

            result = []
            i = 0
            new_shot_num = 1
            while i < len(shots):
                shot = shots[i].copy()

                # 检查是否是合并组的起始
                merge_group = None
                for group in merge_groups:
                    if isinstance(group, list) and len(group) > 1 and group[0] == i:
                        merge_group = group
                        break

                if merge_group:
                    # 合并该组的所有分镜
                    last_idx = merge_group[-1]
                    shot["end_time"] = shots[last_idx].get("end_time")

                    # 合并描述
                    descriptions = []
                    for idx in merge_group:
                        if idx < len(shots):
                            desc = shots[idx].get("frame_description") or shots[idx].get("content_analysis")
                            if desc and desc not in descriptions:
                                descriptions.append(desc)
                    shot["frame_description"] = " → ".join(descriptions[:3])  # 最多保留3段描述
                    shot["content_analysis"] = shot["frame_description"]

                    print(f"🔗 合并分镜 {[s+1 for s in merge_group]} -> shot_{new_shot_num:02d}")
                    i = last_idx + 1
                else:
                    if i not in merged_indices:
                        i += 1
                    else:
                        i += 1
                        continue

                shot["shot_number"] = new_shot_num
                result.append(shot)
                new_shot_num += 1

            print(f"📊 语义合并完成：{len(shots)} 个分镜 -> {len(result)} 个分镜")
            return result

        except Exception as e:
            print(f"⚠️ 语义合并分析失败 ({e})，保留原始分镜")
            return shots

    def _run_ffmpeg_extraction(self, video_path: Path, storyboard: List):
        """
        毫秒级精准提取：
        - 关键帧提取：从分镜中点提取，确保画面与描述一致
        - 视频片段：使用精准切割模式
        """
        ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
        for s in storyboard:
            ts = to_seconds(s.get("start_time"))
            end_ts = to_seconds(s.get("end_time"))
            duration = end_ts - ts
            sid = f"shot_{int(s['shot_number']):02d}"

            # 🎯 关键帧提取：从分镜的**中点**提取，而非起始点
            # 原因：起始点可能是转场瞬间，中点才是该分镜的代表性画面
            mid_ts = ts + (duration / 2.0)
            img_out = self.job_dir / "frames" / f"{sid}.png"
            subprocess.run([
                ffmpeg_path, "-y",
                "-i", str(video_path),
                "-ss", str(mid_ts),       # 从中点提取，确保画面与描述一致
                "-frames:v", "1",
                "-q:v", "2",
                str(img_out)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 🎯 精准视频片段切割
            video_segment_out = self.job_dir / "source_segments" / f"{sid}.mp4"
            subprocess.run([
                ffmpeg_path, "-y",
                "-i", str(video_path),
                "-ss", str(ts),           # 视频片段从起始点开始
                "-t", str(duration),
                "-c:v", "libx264",        # 重新编码以确保精准切割
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                str(video_segment_out)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def load(self):
        """加载状态并对齐物理文件状态"""
        self.workflow = load_workflow(self.job_dir)
        if "global_stages" not in self.workflow:
            self.workflow["global_stages"] = {"analyze": "SUCCESS", "extract": "SUCCESS", "stylize": "NOT_STARTED", "video_gen": "NOT_STARTED", "merge": "NOT_STARTED"}

        updated = False
        shots = self.workflow.get("shots", [])
        for shot in shots:
            sid = shot.get("shot_id")
            status_node = shot.get("status", {})
            
            # 1. 风格化参考图物理对齐
            stylized_path = self.job_dir / "stylized_frames" / f"{sid}.png"
            if stylized_path.exists() and status_node.get("stylize") != "SUCCESS":
                status_node["stylize"] = "SUCCESS"
                shot["assets"]["stylized_frame"] = f"stylized_frames/{sid}.png"
                updated = True

            # 2. 视频产物物理对齐
            video_output_path = self.job_dir / "videos" / f"{sid}.mp4"
            current_video_status = status_node.get("video_generate")
            if video_output_path.exists() and current_video_status != "SUCCESS":
                status_node["video_generate"] = "SUCCESS"
                shot.setdefault("assets", {})["video"] = f"videos/{sid}.mp4"
                updated = True
            elif not video_output_path.exists() and current_video_status == "SUCCESS":
                status_node["video_generate"] = "NOT_STARTED"
                shot.setdefault("assets", {})["video"] = None
                updated = True
        
        # 💡 核心新增：计算合并就绪状态统计
        failed_count = sum(1 for s in shots if s["status"].get("video_generate") == "FAILED")
        pending_count = sum(1 for s in shots if s["status"].get("video_generate") in ["NOT_STARTED", "RUNNING"])
        
        self.workflow["merge_info"] = {
            "can_merge": failed_count == 0 and pending_count == 0 and len(shots) > 0,
            "failed_count": failed_count,
            "pending_count": pending_count,
            "message": ""
        }
        
        if failed_count > 0:
            self.workflow["merge_info"]["message"] = f"⚠️ {failed_count} shots failed and cannot be assembled."
        elif pending_count > 0:
            self.workflow["merge_info"]["message"] = "⏳ Waiting for the shot list to be generated..."
        elif len(shots) > 0:
            self.workflow["merge_info"]["message"] = "✅ All shots are ready and can be assembled into the final film."
        
        if updated: self.save()
        return self.workflow

    def save(self):
        self.workflow.setdefault("meta", {})["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_workflow(self.job_dir, self.workflow)

    def apply_agent_action(self, action: Union[Dict, List]) -> Dict[str, Any]:
        """处理修改意图：强制重置后续所有依赖节点"""
        actions = action if isinstance(action, list) else [action]
        total_affected = 0
        for act in actions:
            op = act.get("op")
            
            if op == "set_global_style":
                affected = apply_global_style(self.workflow, act.get("value"), cascade=True)
                if affected > 0:
                    for s in self.workflow.get("shots", []):
                        v_path = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                        if v_path.exists(): os.remove(v_path)
                        i_path = self.job_dir / "stylized_frames" / f"{s['shot_id']}.png"
                        if i_path.exists(): os.remove(i_path)
                        s["status"]["stylize"] = "NOT_STARTED"
                        s["status"]["video_generate"] = "NOT_STARTED"
                        s["assets"]["video"] = None
                        s["assets"]["stylized_frame"] = None
                total_affected += affected
                
            elif op == "global_subject_swap":
                old_subject = act.get("old_subject", "").lower()
                new_subject = act.get("new_subject", "").lower()
                if old_subject and new_subject:
                    for s in self.workflow.get("shots", []):
                        if old_subject in s["description"].lower():
                            s["description"] = re.sub(old_subject, new_subject, s["description"], flags=re.IGNORECASE)
                            s["status"]["stylize"] = "NOT_STARTED"
                            s["status"]["video_generate"] = "NOT_STARTED"
                            v_path = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                            if v_path.exists(): os.remove(v_path)
                            i_path = self.job_dir / "stylized_frames" / f"{s['shot_id']}.png"
                            if i_path.exists(): os.remove(i_path)
                            s["assets"]["video"] = None
                            s["assets"]["stylized_frame"] = None
                            total_affected += 1
                            
            elif op == "update_shot_params":
                sid = act.get("shot_id")
                for s in self.workflow.get("shots", []):
                    if s["shot_id"] == sid:
                        if "description" in act: s["description"] = act["description"]
                        s["status"]["stylize"] = "NOT_STARTED"
                        s["status"]["video_generate"] = "NOT_STARTED"
                        v_path = self.job_dir / "videos" / f"{sid}.mp4"
                        if v_path.exists(): os.remove(v_path)
                        i_path = self.job_dir / "stylized_frames" / f"{sid}.png"
                        if i_path.exists(): os.remove(i_path)
                        s["assets"]["video"] = None
                        s["assets"]["stylized_frame"] = None
                        total_affected += 1
                        break

            elif op == "enhance_shot_description":
                # 📐 空间感知 + 🎬 风格强化：增强分镜描述
                sid = act.get("shot_id")
                spatial_info = act.get("spatial_info", "")
                style_boost = act.get("style_boost", "")
                for s in self.workflow.get("shots", []):
                    if s["shot_id"] == sid:
                        original_desc = s.get("description", "")
                        enhanced_parts = [original_desc]
                        if spatial_info:
                            enhanced_parts.append(f"[Spatial: {spatial_info}]")
                        if style_boost:
                            enhanced_parts.append(f"[Style: {style_boost}]")
                        s["description"] = " ".join(enhanced_parts)
                        s["status"]["stylize"] = "NOT_STARTED"
                        s["status"]["video_generate"] = "NOT_STARTED"
                        v_path = self.job_dir / "videos" / f"{sid}.mp4"
                        if v_path.exists(): os.remove(v_path)
                        i_path = self.job_dir / "stylized_frames" / f"{sid}.png"
                        if i_path.exists(): os.remove(i_path)
                        s["assets"]["video"] = None
                        s["assets"]["stylized_frame"] = None
                        total_affected += 1
                        print(f"📐 增强分镜描述: {sid} -> {s['description'][:80]}...")
                        break

        if total_affected > 0: self.save()
        return {"status": "success", "affected_shots": total_affected}

    def run_node(self, node_type: str, shot_id: Optional[str] = None):
        """逻辑编排引擎。确保‘先有图，后有视频’且无死锁"""
        self.workflow.setdefault("meta", {}).setdefault("attempts", 0)
        self.workflow["meta"]["attempts"] += 1
        
        target_shots = [s for s in self.workflow.get("shots", []) if not shot_id or s["shot_id"] == shot_id]

        if node_type == "video_generate":
            for s in target_shots:
                if s["status"].get("stylize") != "SUCCESS":
                    print(f"🔗 [Dependency] 分镜 {s['shot_id']} 缺少定妆图，正在前置生成...")
                    run_stylize(self.job_dir, self.workflow, target_shot=s["shot_id"])
                    i_file = self.job_dir / "stylized_frames" / f"{s['shot_id']}.png"
                    if i_file.exists(): 
                        s["status"]["stylize"] = "SUCCESS"
                        s["assets"]["stylized_frame"] = f"stylized_frames/{s['shot_id']}.png"

        stage_key = "video_gen" if node_type == "video_generate" else "stylize"
        self.workflow["global_stages"][stage_key] = "RUNNING"

        for s in target_shots:
            if node_type == "video_generate":
                v_file = self.job_dir / "videos" / f"{s['shot_id']}.mp4"
                if v_file.exists(): os.remove(v_file)
                s["status"]["video_generate"] = "NOT_STARTED" 
                s["assets"]["video"] = None
            elif node_type == "stylize":
                i_file = self.job_dir / "stylized_frames" / f"{s['shot_id']}.png"
                if i_file.exists(): os.remove(i_file)
                s["status"]["stylize"] = "NOT_STARTED" 
                s["assets"]["stylized_frame"] = None

        self.save()

        if node_type == "stylize": 
            run_stylize(self.job_dir, self.workflow, target_shot=shot_id)
        elif node_type == "video_generate": 
            run_video_generate(self.job_dir, self.workflow, target_shot=shot_id)
        
        self.load() 

    def _get_shot_by_id(self, shot_id: str) -> Optional[Dict]:
        for s in self.workflow.get("shots", []):
            if s.get("shot_id") == shot_id: return s
        return None

    def merge_videos(self) -> str:
        """执行无损合并"""
        ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
        success_shots = [s for s in self.workflow.get("shots", []) if s["status"].get("video_generate") == "SUCCESS"]
        if not success_shots: raise RuntimeError("没有可合并的分镜视频。")
        success_shots.sort(key=lambda x: x["shot_id"])
        concat_list_path = self.job_dir / "concat_list.txt"
        output_video_path = self.job_dir / "final_output.mp4"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for s in success_shots:
                v_rel_path = s["assets"].get("video")
                if v_rel_path:
                    abs_v_path = (self.job_dir / v_rel_path).absolute()
                    f.write(f"file '{abs_v_path}'\n")
        cmd = [ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list_path), "-c", "copy", str(output_video_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0: raise RuntimeError(f"合并失败: {result.stderr}")
        if "global_stages" in self.workflow:
            self.workflow["global_stages"]["merge"] = "SUCCESS"
        self.save()
        return "final_output.mp4"