from pathlib import Path
from core.workflow_io import load_workflow, save_workflow
from core.changes import replace_entity_reference
from core.runner import run_pipeline

JOB_DIR = Path("jobs/demo_job_001")

def main():
    wf = load_workflow(JOB_DIR)
    print("✅ load_workflow ok, shots =", len(wf.get("shots", [])))

    # 做一次无害的 entity reference 替换（换成自己已有的文件）
    if "entity_1" in wf.get("entities", {}):
        replace_entity_reference(wf, "entity_1", "stylized_frames/shot_03.png")
        save_workflow(JOB_DIR, wf)
        print("✅ replace_entity_reference ok")

    # 跑 pipeline（会按 NOT_STARTED 执行）
    run_pipeline(JOB_DIR)
    print("✅ run_pipeline ok")

if __name__ == "__main__":
    main()
