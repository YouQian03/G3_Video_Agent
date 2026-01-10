import argparse
from pathlib import Path

from core.workflow_io import load_workflow, save_workflow
from core.changes import apply_global_style, replace_entity_reference
from core.runner import run_pipeline

DEFAULT_JOB_ID = "demo_job_001"
PROJECT_DIR = Path(__file__).parent

def job_dir_from_id(job_id: str) -> Path:
    return PROJECT_DIR / "jobs" / job_id

def cmd_list(job_dir: Path) -> None:
    wf = load_workflow(job_dir)
    print(f"job_id: {wf.get('job_id')}")
    print(f"global.style_prompt: {wf.get('global', {}).get('style_prompt')}")
    print("-" * 60)
    for s in wf.get("shots", []):
        sid = s.get("shot_id")
        st = s.get("status", {})
        print(f"{sid:7}  stylize={st.get('stylize')}  video={st.get('video_generate')}")

def cmd_set_style(job_dir: Path, style: str, cascade: bool) -> None:
    wf = load_workflow(job_dir)
    affected = apply_global_style(wf, style, cascade=cascade)
    save_workflow(job_dir, wf)
    print(f"✅ style 已更新：{style}")
    print(f"✅ 受影响 shots：{affected}（cascade={cascade}）")

def cmd_replace_entity(job_dir: Path, entity_id: str, new_ref: str) -> None:
    wf = load_workflow(job_dir)
    affected = replace_entity_reference(wf, entity_id, new_ref)
    save_workflow(job_dir, wf)
    print(f"✅ 已替换 {entity_id}.reference_image -> {new_ref}")
    print(f"✅ 受影响 shots：{affected}")

def cmd_run(job_dir: Path, shot: str | None) -> None:
    run_pipeline(job_dir, target_shot=shot)
    print("✅ runner 执行完成")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_id", default=DEFAULT_JOB_ID)

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出 shots 状态")
    p_list.set_defaults(func="list")

    p_style = sub.add_parser("set-style", help="设置全局 style_prompt")
    p_style.add_argument("style")
    p_style.add_argument("--no-cascade", action="store_true", help="不级联重跑（默认会级联）")
    p_style.set_defaults(func="set-style")

    p_ent = sub.add_parser("replace-entity", help="替换 entity 的 reference_image，并标记受影响 shots")
    p_ent.add_argument("entity_id")
    p_ent.add_argument("new_ref")
    p_ent.set_defaults(func="replace-entity")

    p_run = sub.add_parser("run", help="运行 runner（按 NOT_STARTED 执行）")
    p_run.add_argument("--shot", default=None, help="只跑某个 shot，例如 shot_03")
    p_run.set_defaults(func="run")

    args = parser.parse_args()
    job_dir = job_dir_from_id(args.job_id)
    if not job_dir.exists():
        raise FileNotFoundError(f"找不到 job 目录：{job_dir}")

    if args.func == "list":
        cmd_list(job_dir)
    elif args.func == "set-style":
        cmd_set_style(job_dir, args.style, cascade=(not args.no_cascade))
    elif args.func == "replace-entity":
        cmd_replace_entity(job_dir, args.entity_id, args.new_ref)
    elif args.func == "run":
        cmd_run(job_dir, args.shot)

if __name__ == "__main__":
    main()
