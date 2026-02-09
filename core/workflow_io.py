import json
import time
import tempfile
import shutil
from pathlib import Path


def load_workflow(job_dir: Path, max_retries: int = 3) -> dict:
    """
    加载 workflow.json，带重试机制防止读写竞态

    Args:
        job_dir: job 目录
        max_retries: 最大重试次数

    Returns:
        workflow 字典
    """
    wf_path = job_dir / "workflow.json"

    for attempt in range(max_retries):
        try:
            if not wf_path.exists():
                return {}

            content = wf_path.read_text(encoding="utf-8")

            # 检查文件是否为空（可能正在写入）
            if not content or not content.strip():
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # 等待 0.1s, 0.2s, 0.3s
                    continue
                return {}

            return json.loads(content)

        except json.JSONDecodeError:
            # JSON 解析失败，可能文件正在写入中
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            # 最后一次重试也失败，返回空字典而不是抛出异常
            return {}

        except Exception:
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            return {}

    return {}


def save_workflow(job_dir: Path, wf: dict) -> None:
    """
    原子写入 workflow.json，防止读写竞态

    使用临时文件 + rename 确保写入原子性
    """
    wf_path = job_dir / "workflow.json"
    content = json.dumps(wf, ensure_ascii=False, indent=2)

    # 原子写入：先写临时文件，再 rename
    temp_path = wf_path.with_suffix(".json.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        # rename 是原子操作
        shutil.move(str(temp_path), str(wf_path))
    except Exception:
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        # fallback: 直接写入
        wf_path.write_text(content, encoding="utf-8")
