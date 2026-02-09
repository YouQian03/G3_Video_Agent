# core/meta_prompts/character_ledger.py
"""
Meta Prompt: 角色清单生成 (Character Ledger Generation)
分离式提取：独立的角色提取 + 独立的场景提取
用于 Pillar II: Narrative Template 的 characterLedger 数据
"""

from typing import Dict, Any, List

# ============================================================
# 角色提取提示词 (Character Extraction Prompt)
# 使用 "Forensic Auditor" 角色确保不遗漏背景角色和群体
# ============================================================
CHARACTER_EXTRACTION_PROMPT = """
# Role: Forensic Character Analyst and Casting Director
# Task: Create an exhaustive inventory of ALL human or sentient entities mentioned in the shot descriptions.

# Instructions:
1. Audit EVERY shot description sequentially. Do not summarize or skip any shots.
2. Identify every distinct individual or defined group (e.g., "crowd", "family of four").
3. CLUSTER IDENTITIES: If a character in shot_05 is clearly the same person as in shot_01 based on description (e.g., "man in car" vs "man walking"), merge them into a single entity.
4. If a description is vague (e.g., "a person"), treat them as a new character unless context strongly suggests otherwise.
5. Provide a detailed 'visualDescription' by aggregating all descriptive details from every shot they appear in.
6. Count the characters; if you find a new person in a shot, you MUST add a new entry. Do not worry about length; accuracy is the priority. Even if there are 10+ characters, list them ALL.

# Constraints:
- Output ONLY valid JSON.
- No markdown formatting, no conversational filler.
- Ensure every character mentioned is captured.

# Schema:
{
  "characters": [
    {
      "entityId": "orig_char_01",
      "displayName": "Short descriptive name",
      "appearsInShots": ["shot_01", "shot_02"],
      "visualDescription": "Consolidated physical details: clothing, age, expression, props.",
      "importance": "PRIMARY or SECONDARY"
    }
  ]
}

# Input Data:
{shot_subjects}
"""

# ============================================================
# 场景/环境提取提示词 (Environment Extraction Prompt)
# 确保 100% 镜头覆盖率
# ============================================================
ENVIRONMENT_EXTRACTION_PROMPT = """
# Role: Architectural Location Scout and Scene Auditor
# Task: Extract every unique physical location and ensure 100% shot-to-environment mapping.

# Instructions:
1. Perform a "Location Audit": Every single shot ID provided MUST be assigned to an environment entity.
2. CLUSTER LOCATIONS: Group shots that take place in the same physical space (e.g., "Inside McDonald's at a table" and "Inside McDonald's by the counter" = "McDonald's Interior").
3. DIFFERENTIATE: If a location is distinct (e.g., "Car Interior" vs "Street Outside"), they must be separate entities.
4. Visual Description: Synthesize the atmospheric details (lighting, weather, specific props/landmarks) from the combined shots.

# Constraints:
- Output ONLY valid JSON.
- No markdown, no filler.
- TOTAL COVERAGE: Every shot ID in the input must appear in exactly one 'appearsInShots' array.

# Schema:
{
  "environments": [
    {
      "entityId": "orig_env_01",
      "displayName": "Specific location name",
      "appearsInShots": ["shot_01"],
      "visualDescription": "Atmospheric and architectural details: lighting, time of day, weather, key background elements.",
      "importance": "PRIMARY or SECONDARY"
    }
  ]
}

# Input Data:
{shot_subjects}
"""

# ============================================================
# 保留旧的合并提示词作为备用 (Legacy combined prompt)
# ============================================================
CHARACTER_CLUSTERING_PROMPT = CHARACTER_EXTRACTION_PROMPT  # Alias for backward compatibility


def build_shot_subjects_input(shots: List[Dict]) -> str:
    """
    构建 shot subjects 输入文本供 AI 聚类

    Args:
        shots: Pillar III 的 concrete shots 列表

    Returns:
        格式化的 shot subjects 文本
    """
    lines = []
    for shot in shots:
        shot_id = shot.get("shotId", "unknown")
        subject = shot.get("subject", "No subject")
        scene = shot.get("scene", "No scene")

        lines.append(f"- {shot_id}:")
        lines.append(f"    Subject: {subject}")
        lines.append(f"    Scene: {scene}")
        lines.append("")

    return "\n".join(lines)


def process_ledger_result(ai_output: Dict[str, Any], all_shot_ids: List[str] = None) -> Dict[str, Any]:
    """
    处理 AI 输出，验证和规范化 character ledger 数据

    Args:
        ai_output: Gemini 返回的原始 JSON
        all_shot_ids: 所有 shot ID 列表，用于验证覆盖率

    Returns:
        规范化的 ledger 数据
    """
    if not ai_output.get("clusteringSuccess"):
        return {
            "characterLedger": [],
            "environmentLedger": [],
            "clusteringSummary": {"error": "Clustering failed"}
        }

    # 验证并规范化 character ledger
    character_ledger = []
    for char in ai_output.get("characterLedger", []):
        normalized = {
            "entityId": char.get("entityId", ""),
            "entityType": char.get("entityType", "CHARACTER"),
            "importance": char.get("importance", "SECONDARY"),
            "displayName": char.get("displayName", "Unknown"),
            "visualSignature": char.get("visualSignature", ""),
            "detailedDescription": char.get("detailedDescription", ""),
            "appearsInShots": char.get("appearsInShots", []),
            "shotCount": len(char.get("appearsInShots", [])),
            "trackingConfidence": char.get("trackingConfidence", "MEDIUM"),
            "visualCues": char.get("visualCues", [])
        }

        # 确保 entityId 格式正确
        if not normalized["entityId"].startswith("orig_char_"):
            normalized["entityId"] = f"orig_char_{len(character_ledger) + 1:02d}"

        character_ledger.append(normalized)

    # 验证并规范化 environment ledger
    environment_ledger = []
    for env in ai_output.get("environmentLedger", []):
        normalized = {
            "entityId": env.get("entityId", ""),
            "entityType": "ENVIRONMENT",
            "importance": env.get("importance", "SECONDARY"),
            "displayName": env.get("displayName", "Unknown"),
            "visualSignature": env.get("visualSignature", ""),
            "detailedDescription": env.get("detailedDescription", ""),
            "appearsInShots": env.get("appearsInShots", []),
            "shotCount": len(env.get("appearsInShots", []))
        }

        # 确保 entityId 格式正确
        if not normalized["entityId"].startswith("orig_env_"):
            normalized["entityId"] = f"orig_env_{len(environment_ledger) + 1:02d}"

        environment_ledger.append(normalized)

    # 🎯 Post-processing: Ensure 100% shot coverage
    if all_shot_ids:
        # Collect all covered shots
        covered_shots = set()
        for char in character_ledger:
            covered_shots.update(char.get("appearsInShots", []))
        for env in environment_ledger:
            covered_shots.update(env.get("appearsInShots", []))

        # Find missing shots
        missing_shots = [sid for sid in all_shot_ids if sid not in covered_shots]

        if missing_shots:
            print(f"   ⚠️ [Post-processing] {len(missing_shots)} shots not covered: {missing_shots[:5]}{'...' if len(missing_shots) > 5 else ''}")

            # Add missing shots to a generic environment or create one
            if environment_ledger:
                # Find the environment with most shots (likely the main setting)
                main_env = max(environment_ledger, key=lambda e: len(e.get("appearsInShots", [])))
                main_env["appearsInShots"].extend(missing_shots)
                main_env["shotCount"] = len(main_env["appearsInShots"])
                print(f"   ✅ [Post-processing] Added {len(missing_shots)} missing shots to '{main_env['displayName']}'")
            else:
                # Create a generic environment
                generic_env = {
                    "entityId": "orig_env_01",
                    "entityType": "ENVIRONMENT",
                    "importance": "PRIMARY",
                    "displayName": "Video Setting",
                    "visualSignature": "General video environment",
                    "detailedDescription": "The main setting of the video",
                    "appearsInShots": missing_shots,
                    "shotCount": len(missing_shots)
                }
                environment_ledger.append(generic_env)
                print(f"   ✅ [Post-processing] Created generic environment for {len(missing_shots)} missing shots")

    # 计算汇总信息
    primary_chars = [c for c in character_ledger if c["importance"] == "PRIMARY"]
    secondary_chars = [c for c in character_ledger if c["importance"] == "SECONDARY"]

    summary = {
        "totalCharacters": len(character_ledger),
        "primaryCharacters": len(primary_chars),
        "secondaryCharacters": len(secondary_chars),
        "totalEnvironments": len(environment_ledger),
        "totalShots": ai_output.get("clusteringSummary", {}).get("totalShots", 0),
        "unclusteredShots": ai_output.get("clusteringSummary", {}).get("unclusteredShots", [])
    }

    return {
        "characterLedger": character_ledger,
        "environmentLedger": environment_ledger,
        "clusteringSummary": summary
    }


def get_ledger_display_summary(ledger_data: Dict[str, Any]) -> str:
    """
    生成人类可读的 ledger 摘要
    """
    summary = ledger_data.get("clusteringSummary", {})
    chars = ledger_data.get("characterLedger", [])
    envs = ledger_data.get("environmentLedger", [])

    lines = [
        "=== Character Ledger Summary ===",
        f"Characters: {summary.get('totalCharacters', 0)} ({summary.get('primaryCharacters', 0)} primary, {summary.get('secondaryCharacters', 0)} secondary)",
        f"Environments: {summary.get('totalEnvironments', 0)}",
        "",
        "PRIMARY Characters:"
    ]

    for char in chars:
        if char.get("importance") == "PRIMARY":
            lines.append(f"  - {char['entityId']}: {char['displayName']} (appears in {char['shotCount']} shots)")

    lines.append("")
    lines.append("Environments:")
    for env in envs:
        lines.append(f"  - {env['entityId']}: {env['displayName']} ({env['shotCount']} shots)")

    return "\n".join(lines)


def update_shots_with_entity_refs(shots: List[Dict], ledger_data: Dict[str, Any]) -> List[Dict]:
    """
    更新 shots 数据，添加 entityRefs 字段

    Args:
        shots: 原始 shots 列表
        ledger_data: character ledger 数据

    Returns:
        更新后的 shots 列表，每个 shot 包含 entityRefs
    """
    # 建立 shot -> entities 的反向映射
    shot_to_chars = {}
    shot_to_envs = {}

    for char in ledger_data.get("characterLedger", []):
        for shot_id in char.get("appearsInShots", []):
            if shot_id not in shot_to_chars:
                shot_to_chars[shot_id] = []
            shot_to_chars[shot_id].append(char["entityId"])

    for env in ledger_data.get("environmentLedger", []):
        for shot_id in env.get("appearsInShots", []):
            if shot_id not in shot_to_envs:
                shot_to_envs[shot_id] = []
            shot_to_envs[shot_id].append(env["entityId"])

    # 更新每个 shot
    updated_shots = []
    for shot in shots:
        shot_id = shot.get("shotId", "")
        updated_shot = shot.copy()
        updated_shot["entityRefs"] = {
            "characters": shot_to_chars.get(shot_id, []),
            "environments": shot_to_envs.get(shot_id, [])
        }
        updated_shots.append(updated_shot)

    return updated_shots
