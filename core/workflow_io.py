import json
from pathlib import Path

def load_workflow(job_dir: Path) -> dict:
    wf_path = job_dir / "workflow.json"
    return json.loads(wf_path.read_text(encoding="utf-8"))

def save_workflow(job_dir: Path, wf: dict) -> None:
    wf_path = job_dir / "workflow.json"
    wf_path.write_text(
        json.dumps(wf, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
