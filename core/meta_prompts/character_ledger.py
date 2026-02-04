# core/meta_prompts/character_ledger.py
"""
Meta Prompt: 角色清单生成 (Character Ledger Generation)
两阶段识别：Phase 1 提取 + Phase 2 聚类
用于 Pillar II: Narrative Template 的 characterLedger 数据
"""

from typing import Dict, Any, List

CHARACTER_CLUSTERING_PROMPT = """
# Task: Character & Environment Clustering for Video Remix

You are a Video Analysis AI specializing in character AND environment identification.

## Mission
Analyze the extracted shot subjects and cluster them into:
1. **UNIQUE CHARACTERS** - People/animals that can be tracked across shots
2. **UNIQUE ENVIRONMENTS** - Distinct locations/settings that appear in the video

Both character AND environment extraction are MANDATORY. Every video has environments.

## Input: Extracted Shot Subjects
{shot_subjects}

## Critical Rules for ID Assignment

### 1. Visual Continuity Tracking (Characters)
- The SAME person appearing in different shots MUST have the SAME ID
- Use visual cues to identify same person across shots:
  - Clothing color and style
  - Body type and posture
  - Props they carry (bike, shopping bags, etc.)
  - Context continuity (same scene, adjacent shots)

### 2. Environment Extraction (MANDATORY)
- Extract ALL unique environments/locations from the "Scene" descriptions
- Common environment types:
  - Interior spaces (car interior, restaurant, shop, home)
  - Exterior spaces (streets, roads, parks, parking lots)
  - Specific landmarks (McDonald's, buildings with signage)
- If the same location appears in multiple shots, cluster them under ONE environment ID
- **You MUST extract at least 1 environment** - every video has at least one setting

### 3. Entity Categories
- **PRIMARY**: Main characters/environments (appear in 3+ shots OR are central to narrative)
- **SECONDARY**: Supporting characters/environments (appear in 1-2 shots)
- **BACKGROUND**: Crowds, extras (do not assign individual IDs, group as "background_crowd")

### 4. ID Naming Convention
- Characters: `orig_char_XX` (e.g., orig_char_01, orig_char_02)
- Environments/Locations: `orig_env_XX` (e.g., orig_env_01)
- Props/Objects: `orig_prop_XX` (e.g., orig_prop_01) - only for KEY props that might need replacement

## Output Format (Strict JSON)

{
  "clusteringSuccess": true,
  "characterLedger": [
    {
      "entityId": "orig_char_01",
      "entityType": "CHARACTER",
      "importance": "PRIMARY",
      "displayName": "Human-readable name (e.g., '骑自行车的男子')",
      "visualSignature": "15-20 word distinctive visual description for identification",
      "detailedDescription": "80-100 word exhaustive visual description for asset generation",
      "appearsInShots": ["shot_01", "shot_05", "shot_12"],
      "shotCount": 3,
      "trackingConfidence": "HIGH",
      "visualCues": ["red jacket", "carrying bike", "male, 30s"]
    }
  ],
  "environmentLedger": [
    {
      "entityId": "orig_env_01",
      "entityType": "ENVIRONMENT",
      "importance": "PRIMARY",
      "displayName": "McDonald's Restaurant",
      "visualSignature": "Fast food restaurant interior with yellow and red branding",
      "detailedDescription": "80-100 word detailed environment description",
      "appearsInShots": ["shot_08", "shot_15", "shot_22"],
      "shotCount": 3
    }
  ],
  "clusteringSummary": {
    "totalCharacters": 5,
    "primaryCharacters": 2,
    "secondaryCharacters": 3,
    "totalEnvironments": 3,
    "totalShots": 24,
    "unclusteredShots": []
  }
}

## Special Instructions

1. **Merge Similar Subjects**: If "骑自行车的男子" in shot_03 and "男子推着自行车" in shot_07 are clearly the same person, assign the SAME entityId.

2. **Do NOT Over-Cluster**: Two different people who both "walk into McDonald's" should have DIFFERENT IDs unless visual evidence suggests they're the same person.

3. **Brand/Logo Entities**: Treat brand elements (McDonald's logo, KFC bucket) as ENVIRONMENT entities, not characters.

4. **Confidence Levels**:
   - HIGH: Clear visual match across shots
   - MEDIUM: Reasonable inference based on context
   - LOW: Ambiguous, might be different people

5. **MANDATORY Environment Extraction**:
   - Read EVERY "Scene" description carefully
   - Extract distinct locations: "interior of a car" → orig_env_01, "snowy road" → orig_env_02, "city street" → orig_env_03, "inside a shop" → orig_env_04
   - If environments are similar but distinct (e.g., two different streets), create separate IDs
   - **Failure to extract environments is NOT acceptable** - the environmentLedger array must NOT be empty

Output ONLY valid JSON. No markdown, no explanation.
"""


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


def process_ledger_result(ai_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 AI 输出，验证和规范化 character ledger 数据

    Args:
        ai_output: Gemini 返回的原始 JSON

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
