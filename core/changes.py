from typing import Optional

def apply_global_style(wf: dict, new_style_prompt: str, cascade: bool = True) -> int:
    wf.setdefault("global", {})["style_prompt"] = new_style_prompt

    affected = 0
    if cascade:
        for shot in wf.get("shots", []):
            shot.setdefault("status", {})["stylize"] = "NOT_STARTED"
            shot.setdefault("status", {})["video_generate"] = "NOT_STARTED"
            affected += 1
    return affected

def replace_entity_reference(wf: dict, entity_id: str, new_ref_image: str) -> int:
    entities = wf.setdefault("entities", {})
    if entity_id not in entities:
        raise KeyError(f"entity 不存在：{entity_id}")

    entities[entity_id]["reference_image"] = new_ref_image

    affected = 0
    for shot in wf.get("shots", []):
        shot_entities = shot.get("entities", [])
        if entity_id in shot_entities:
            shot.setdefault("status", {})["stylize"] = "NOT_STARTED"
            shot.setdefault("status", {})["video_generate"] = "NOT_STARTED"
            affected += 1
    return affected
