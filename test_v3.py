# test_v3.py
from core.workflow_manager import WorkflowManager

manager = WorkflowManager("demo_job_001")

# 测试形态 3：手动微调第 2 个镜头的描述
print("测试形态 3：手动微调分镜...")
manager.apply_agent_action({
    "op": "update_shot_params",
    "shot_id": "shot_02",
    "description": "一只正在戴着墨镜跳舞的酷狗"
})

manager.load()
shot2 = [s for s in manager.workflow["shots"] if s["shot_id"] == "shot_02"][0]
print(f"分镜 2 新描述: {shot2['description']}")
print(f"分镜 2 状态已重置: {shot2['status']['video_generate']}") # 应该是 NOT_STARTED
print(f"全局 Video Gen 阶段状态: {manager.workflow['global_stages']['video_gen']}")