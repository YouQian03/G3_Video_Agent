# core/film_ir_io.py
"""
Film IR 读写模块
================
负责 film_ir.json 的持久化读写操作。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from core.film_ir_schema import create_empty_film_ir


def get_film_ir_path(job_dir: Path) -> Path:
    """获取 film_ir.json 路径"""
    return job_dir / "film_ir.json"


def load_film_ir(job_dir: Path) -> Dict[str, Any]:
    """
    加载 Film IR

    Args:
        job_dir: 作业目录路径

    Returns:
        Film IR 字典，如果文件不存在则返回空结构
    """
    ir_path = get_film_ir_path(job_dir)

    if not ir_path.exists():
        # 尝试从 job_id 推断
        job_id = job_dir.name
        return create_empty_film_ir(job_id)

    try:
        with open(ir_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"⚠️ Film IR 解析失败: {e}")
        job_id = job_dir.name
        return create_empty_film_ir(job_id)


def save_film_ir(job_dir: Path, ir: Dict[str, Any]) -> None:
    """
    保存 Film IR

    Args:
        job_dir: 作业目录路径
        ir: Film IR 字典
    """
    ir_path = get_film_ir_path(job_dir)

    # 更新时间戳
    ir["updatedAt"] = datetime.utcnow().isoformat() + "Z"

    # 确保目录存在
    job_dir.mkdir(parents=True, exist_ok=True)

    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(ir, f, ensure_ascii=False, indent=2)


def film_ir_exists(job_dir: Path) -> bool:
    """检查 Film IR 是否存在"""
    return get_film_ir_path(job_dir).exists()


def update_film_ir_stage(job_dir: Path, stage: str, status: str) -> None:
    """
    更新 Film IR 阶段状态

    Args:
        job_dir: 作业目录
        stage: 阶段名 (specificAnalysis/abstraction/intentInjection/...)
        status: 状态 (NOT_STARTED/RUNNING/SUCCESS/FAILED)
    """
    ir = load_film_ir(job_dir)

    if stage in ir.get("stages", {}):
        ir["stages"][stage] = status
        save_film_ir(job_dir, ir)
    else:
        raise ValueError(f"Unknown stage: {stage}")


def update_film_ir_pillar(
    job_dir: Path,
    pillar: str,
    layer: str,
    data: Dict[str, Any]
) -> None:
    """
    更新 Film IR 支柱数据

    Args:
        job_dir: 作业目录
        pillar: 支柱名 (I_storyTheme/II_narrativeTemplate/III_shotRecipe/IV_renderStrategy)
        layer: 层级 (concrete/abstract/remixed)
        data: 数据
    """
    ir = load_film_ir(job_dir)

    if pillar not in ir.get("pillars", {}):
        raise ValueError(f"Unknown pillar: {pillar}")

    if pillar == "IV_renderStrategy":
        # 支柱 IV 结构不同，直接更新
        ir["pillars"][pillar].update(data)
    else:
        if layer not in ["concrete", "abstract", "remixed"]:
            raise ValueError(f"Unknown layer: {layer}")
        ir["pillars"][pillar][layer] = data

    save_film_ir(job_dir, ir)


def set_user_intent(job_dir: Path, raw_prompt: str) -> None:
    """设置用户意图"""
    ir = load_film_ir(job_dir)

    ir["userIntent"]["rawPrompt"] = raw_prompt
    ir["userIntent"]["injectedAt"] = datetime.utcnow().isoformat() + "Z"

    save_film_ir(job_dir, ir)


def get_hidden_template(job_dir: Path) -> Dict[str, Any]:
    """
    获取隐形模板 (所有支柱的 abstract 层)

    Returns:
        包含三个支柱抽象数据的字典
    """
    ir = load_film_ir(job_dir)

    return {
        "storyTheme": ir["pillars"]["I_storyTheme"].get("abstract"),
        "narrativeTemplate": ir["pillars"]["II_narrativeTemplate"].get("abstract"),
        "shotRecipe": ir["pillars"]["III_shotRecipe"].get("abstract")
    }


def get_active_layer(job_dir: Path, pillar: str) -> Dict[str, Any]:
    """
    获取支柱的活跃层数据
    优先级: remixed > concrete > None

    Args:
        job_dir: 作业目录
        pillar: 支柱名

    Returns:
        活跃层数据
    """
    ir = load_film_ir(job_dir)

    if pillar not in ir.get("pillars", {}):
        raise ValueError(f"Unknown pillar: {pillar}")

    pillar_data = ir["pillars"][pillar]

    # 支柱 IV 结构不同
    if pillar == "IV_renderStrategy":
        return pillar_data

    # 优先返回 remixed，其次 concrete
    if pillar_data.get("remixed"):
        return pillar_data["remixed"]
    return pillar_data.get("concrete")


# ============================================================
# 前端数据转换函数
# ============================================================

def convert_to_frontend_story_theme(ir: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    转换为前端 StoryThemeAnalysis 格式
    直接使用活跃层数据（字段名已对齐）
    """
    pillar = ir["pillars"]["I_storyTheme"]

    # 优先 remixed，其次 concrete
    data = pillar.get("remixed") or pillar.get("concrete")

    return data


def convert_to_frontend_script_analysis(ir: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    转换为前端 ScriptAnalysis 格式
    直接使用活跃层数据（字段名已对齐）
    """
    pillar = ir["pillars"]["II_narrativeTemplate"]

    # 优先 remixed，其次 concrete
    data = pillar.get("remixed") or pillar.get("concrete")

    return data


def convert_to_frontend_storyboard(ir: Dict[str, Any], base_url: str = "") -> list:
    """
    转换为前端 StoryboardShot[] 格式

    Args:
        ir: Film IR
        base_url: 资产 URL 前缀

    Returns:
        StoryboardShot 列表
    """
    pillar = ir["pillars"]["III_shotRecipe"]
    data = pillar.get("remixed") or pillar.get("concrete")

    if not data or "shots" not in data:
        return []

    job_id = ir.get("jobId", "")
    result = []

    for shot in data["shots"]:
        # 构建前端格式
        frontend_shot = {
            "shotNumber": int(shot["shotId"].replace("shot_", "")),
            "firstFrameImage": "",
            "visualDescription": shot.get("subject", ""),
            "contentDescription": shot.get("scene", ""),
            "startSeconds": _time_to_seconds(shot.get("startTime", "0")),
            "endSeconds": _time_to_seconds(shot.get("endTime", "0")),
            "durationSeconds": shot.get("durationSeconds", 0),
            "shotSize": shot.get("camera", {}).get("shotSize", ""),
            "cameraAngle": shot.get("camera", {}).get("cameraAngle", ""),
            "cameraMovement": shot.get("camera", {}).get("cameraMovement", ""),
            "focalLengthDepth": shot.get("camera", {}).get("focalLengthDepth", ""),
            "lighting": shot.get("lighting", ""),
            "music": shot.get("audio", {}).get("music", ""),
            "dialogueVoiceover": shot.get("audio", {}).get("dialogue", "")
        }

        # 处理资产路径
        assets = shot.get("assets", {})
        if assets.get("firstFrame") and base_url:
            frontend_shot["firstFrameImage"] = f"{base_url}/assets/{job_id}/{assets['firstFrame']}"

        result.append(frontend_shot)

    return result


def _time_to_seconds(time_str: str) -> float:
    """将时间字符串转换为秒数"""
    if not time_str:
        return 0.0

    if isinstance(time_str, (int, float)):
        return float(time_str)

    time_str = str(time_str).strip()

    if ':' in time_str:
        parts = time_str.split(':')
        try:
            if len(parts) == 2:  # MM:SS
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except ValueError:
            return 0.0

    try:
        return float(time_str)
    except ValueError:
        return 0.0
