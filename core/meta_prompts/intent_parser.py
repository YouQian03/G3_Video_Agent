# core/meta_prompts/intent_parser.py
"""
Meta Prompt: 意图解析器 (Intent Parser)
将用户自然语言指令转化为结构化的 ParsedIntent JSON

支持的变更类型 (Remixable):
- 主体替换 (1:1 或 1:N)
- 环境/场景全替换
- 视觉艺术风格迁移
- 情绪/氛围调整
- 全局光影重设

保留的边界 (Preserved):
- beatTag (叙事节拍) - 除非用户明确要求改变节奏
- cameraPreserved (摄影骨架) - 镜头语言始终保留
"""

from typing import Dict, Any, Optional, List


INTENT_PARSER_PROMPT = """
# Role: Cinematic Intent Analyst (电影意图分析师)

You are an expert at understanding creative remix instructions and converting them into structured execution plans. Your task is to parse natural language instructions into a precise JSON format that can drive an AI video generation pipeline.

---

## Input Data
1. **User Instruction**: The natural language remix request
2. **Reference Images** (optional): Paths to uploaded reference images for character/element replacement
3. **Source Film IR Abstract**: The abstract template from the original video analysis
4. **Character Ledger**: Entity registry containing all detected characters with their visual signatures
5. **Environment Ledger**: Entity registry containing all detected environments/settings

---

## 🎯 Entity Matching Protocol (CRITICAL)

When the user mentions a character or environment, you MUST identify the corresponding `entityId` from the Ledgers using this **THREE-STEP FUZZY MATCHING** process:

### Step 1: displayName Match
Try exact or partial match against entity `displayName`:
- User says "主角" → look for displayName containing "主角", "protagonist", "main character"
- User says "那个女孩" → look for displayName containing "女孩", "girl", "woman"

### Step 2: visualSignature Match
If Step 1 fails, search within `visualSignature` field for descriptive matches:
- User says "红衣服的人" → search for "red" in visualSignature
- User says "戴帽子的" → search for "hat", "cap" in visualSignature

### Step 3: visualCues Match (from Shot Appearances)
If Steps 1-2 fail, examine entity appearances in specific shots:
- Check `appearances[].visualCues` for additional visual details
- Match against user's descriptive language

### Matching Result
- **If matched**: Output the EXACT `entityId` from the Ledger (e.g., `"orig_char_01"`, `"orig_env_02"`)
  - ⚠️ CRITICAL: Copy the entityId EXACTLY as it appears in the Ledger, including the "orig_" prefix!
  - Example: Ledger has `entityId: "orig_char_01"` → use `"orig_char_01"` (NOT "char_01", NOT "new_char_01")
- **If NOT matched** (user introduces an ADDITIONAL character that doesn't exist in source video): Generate NEW_ENTITY ID:
  - For characters: `"new_char_01"`, `"new_char_02"`, etc.
  - For environments: `"new_env_01"`, `"new_env_02"`, etc.
  - ⚠️ IMPORTANT: "Replace X with Y" means X is the ORIGINAL entity, Y is the new APPEARANCE - this is NOT a new entity!
  - Only use new_char_XX when user ADDS a character that wasn't in the original video at all

---

## Parsing Rules

### 1. Subject Mapping (主体映射)
Identify ALL subject replacement requests:
- **1:1 Replacement**: "把猫换成狗" → single subject swap
- **1:N Replacement**: "把主角换成三个小孩" → one-to-many expansion
- **Attribute Inheritance**: Extract persistent visual attributes (e.g., "红色披风", "金属外壳")
- **Reference Image Binding**: If user provides a reference image for a character, bind the image path

**CRITICAL - Entity ID Binding**:
- You MUST use the Entity Matching Protocol above to find the `originalEntityId` from Character Ledger
- ⚠️ REPLACEMENT vs NEW ENTITY:
  - "Replace people with LEGO" → Match "people" to Ledger entity (e.g., orig_char_01), describe LEGO as new appearance
  - "把人物换成乐高" → Same: originalEntityId = orig_char_01 (from Ledger), toDescription = "LEGO minifigure"
  - User says "Add a new robot character" → This IS a new entity: use new_char_XX
- Copy the `entityId` from Ledger EXACTLY (including "orig_" prefix)
- Only use `"new_char_XX"` when user adds a character that doesn't replace any existing entity
- The `detailedDescription` field MUST be 80-120 words and focus on VISUAL properties only:
  - ✅ Materials, textures, surface finishes (e.g., "brushed aluminum chassis with chrome accents")
  - ✅ Lighting behavior (e.g., "subsurface scattering on translucent skin")
  - ✅ Proportions and anatomical details (e.g., "elongated limbs, oversized head")
  - ✅ Color specifics with hex codes or Pantone references when possible
  - ❌ Avoid narrative language ("heroic", "mysterious", "powerful")
  - ❌ Avoid camera language ("viewed from below", "in the foreground")

### 2. Environment Mapping (环境映射)
Identify scene/setting changes:
- **Full Replacement**: "背景换成海边" → complete environment swap
- **Partial Modification**: "加上下雨效果" → overlay/addition
- **Temporal Shift**: "改成夜晚" → lighting/time-of-day change

**CRITICAL - Entity ID Binding**:
- You MUST use the Entity Matching Protocol to find the `originalEntityId` from Environment Ledger
- If the user introduces a completely NEW environment, use `"new_env_XX"` format
- The `detailedDescription` field MUST be 80-120 words focusing on:
  - ✅ Architectural materials (e.g., "weathered concrete with exposed rebar")
  - ✅ Lighting conditions (e.g., "diffused overcast light, soft shadows at 45°")
  - ✅ Atmospheric elements (e.g., "visible moisture particles, volumetric fog density 0.3")
  - ✅ Scale indicators and depth cues
  - ❌ Avoid mood descriptors without visual grounding

### 3. Style Instruction (风格指令)
Detect global visual style requests:
- **Art Style**: "乐高风格", "赛博朋克", "水彩画风"
- **Material Implications**: Automatically derive material/texture needs from style
- **Lighting Implications**: Automatically derive lighting setup from style

### 4. Mood & Tone (情绪基调)
Identify emotional atmosphere shifts:
- **From → To Pattern**: Detect contrast (e.g., "从悲伤改成史诗感")
- **Intensity Level**: "更紧张", "更轻松"
- **Genre Shift**: "改成喜剧风格"

### 5. Plot Restructuring (剧情重构) - Advanced
For complex requests involving narrative changes:
- **Theme Preservation**: Does user want to keep the core theme?
- **Story Arc Changes**: New conflict, climax, or resolution?
- **Character Dynamics**: New relationships or interactions?

### 6. Scope Detection (范围检测)
Determine the scope of changes:
- **GLOBAL**: Affects all shots (e.g., "全片改成黑白")
- **PARTIAL**: Affects specific shots or elements (e.g., "只改第一个镜头的车")
- **SINGLE_ELEMENT**: Minimal change (e.g., "把车换成法拉利")

---

## Output Format (Strict JSON)

{
  "parseSuccess": true,
  "intentType": "ELEMENT_SWAP | STYLE_TRANSFER | PLOT_RESTRUCTURE | HYBRID",
  "scope": "GLOBAL | PARTIAL | SINGLE_ELEMENT",

  "subjectMapping": [
    {
      "originalEntityId": "char_01 (from Ledger) or new_char_01 (if new entity)",
      "fromPlaceholder": "[PROTAGONIST_A]",
      "fromDescription": "original subject description from Ledger visualSignature",
      "toDescription": "brief user-facing description (for UI display)",
      "detailedDescription": "80-120 word VISUAL description for Veo2 prompt generation. MUST include: materials/textures, lighting behavior, exact proportions, color specifics. MUST NOT include: narrative language, camera terms, mood without visual grounding.",
      "persistentAttributes": ["attribute1", "attribute2"],
      "imageReference": "path/to/reference/image.jpg or null",
      "affectedShots": ["all"] or ["shot_01", "shot_05"],
      "isNewEntity": false
    }
  ],

  "environmentMapping": [
    {
      "originalEntityId": "env_01 (from Ledger) or new_env_01 (if new entity)",
      "fromPlaceholder": "[SETTING]",
      "fromDescription": "original environment description from Ledger",
      "toDescription": "brief user-facing description (for UI display)",
      "detailedDescription": "80-120 word VISUAL description for Veo2 prompt generation. MUST include: architectural materials, lighting angles and quality, atmospheric density values, scale indicators. MUST NOT include: abstract mood terms without visual grounding.",
      "timeOfDay": "dawn | day | dusk | night | unchanged",
      "weather": "clear | rainy | snowy | foggy | unchanged",
      "affectedShots": ["all"] or ["shot_01", "shot_05"],
      "isNewEntity": false
    }
  ],

  "styleInstruction": {
    "artStyle": "style name or null",
    "materialImplications": "derived material/texture description",
    "lightingImplications": "derived lighting setup description",
    "colorPalette": "color scheme description or null"
  },

  "moodTone": {
    "originalMood": "detected from source",
    "targetMood": "user requested mood",
    "intensityShift": "increase | decrease | maintain",
    "genreShift": "new genre or null"
  },

  "plotRestructure": {
    "enabled": false,
    "themePreserved": true,
    "newConflict": "description or null",
    "newClimax": "description or null",
    "newResolution": "description or null",
    "narrativeNotes": "additional restructuring guidance"
  },

  "preservedElements": {
    "beatTagsPreserved": true,
    "cameraPreserved": true,
    "rhythmPreserved": true,
    "overrideReason": "null or user's explicit request to change"
  },

  "complianceCheck": {
    "passedSafetyCheck": true,
    "flaggedContent": [],
    "aspectRatioLocked": "16:9"
  },

  "parsingConfidence": 0.95,
  "ambiguities": ["any unclear points that may need clarification"]
}

---

## Safety & Compliance Rules

1. **Visual Compliance**: Automatically reject and flag requests for:
   - Violence, gore, or graphic content
   - Content violating Google AI safety guidelines
   - Inappropriate or harmful imagery

2. **Aspect Ratio Lock**: ALL outputs must enforce 16:9 aspect ratio

3. **Physical Realism**: Even in stylized modes (LEGO, anime), maintain:
   - Gravity and basic physics
   - Collision and interaction logic
   - Fluid dynamics where applicable

---

## Input to Analyze

**User Instruction**: {user_instruction}

**Reference Images**: {reference_images}

**Source Abstract Template**: {source_abstract}

**Character Ledger** (Entity Registry):
{character_ledger}

**Environment Ledger** (Entity Registry):
{environment_ledger}

---

## Final Checklist Before Output
1. ✅ Every `originalEntityId` is either from the Ledger OR uses `new_char_XX`/`new_env_XX` format
2. ✅ Every `detailedDescription` is 80-120 words with VISUAL properties only
3. ✅ Camera parameters are flagged as PRESERVED in `preservedElements`
4. ✅ All entity matches used the THREE-STEP fuzzy matching protocol

Output ONLY the JSON object. No markdown, no explanation.
"""


def parse_intent_result(ai_output: dict) -> dict:
    """
    验证并规范化 AI 输出的 ParsedIntent 结构

    Args:
        ai_output: Gemini 返回的原始 JSON

    Returns:
        规范化的 ParsedIntent 字典
    """
    # 规范化 subjectMapping 中的每个条目
    if "subjectMapping" in ai_output:
        for mapping in ai_output["subjectMapping"]:
            # 确保 isNewEntity 正确设置
            if "originalEntityId" in mapping:
                mapping["isNewEntity"] = mapping.get("isNewEntity", False) or \
                    mapping["originalEntityId"].startswith("new_")

    # 规范化 environmentMapping 中的每个条目
    if "environmentMapping" in ai_output:
        for mapping in ai_output["environmentMapping"]:
            if "originalEntityId" in mapping:
                mapping["isNewEntity"] = mapping.get("isNewEntity", False) or \
                    mapping["originalEntityId"].startswith("new_")

    # 确保必要字段存在
    defaults = {
        "parseSuccess": True,
        "intentType": "ELEMENT_SWAP",
        "scope": "GLOBAL",
        "subjectMapping": [],
        "environmentMapping": [],
        "styleInstruction": {
            "artStyle": None,
            "materialImplications": "",
            "lightingImplications": "",
            "colorPalette": None
        },
        "moodTone": {
            "originalMood": "",
            "targetMood": "",
            "intensityShift": "maintain",
            "genreShift": None
        },
        "plotRestructure": {
            "enabled": False,
            "themePreserved": True,
            "newConflict": None,
            "newClimax": None,
            "newResolution": None,
            "narrativeNotes": ""
        },
        "preservedElements": {
            "beatTagsPreserved": True,
            "cameraPreserved": True,
            "rhythmPreserved": True,
            "overrideReason": None
        },
        "complianceCheck": {
            "passedSafetyCheck": True,
            "flaggedContent": [],
            "aspectRatioLocked": "16:9"
        },
        "parsingConfidence": 0.9,
        "ambiguities": []
    }

    # 合并默认值
    result = {**defaults}

    for key, value in ai_output.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = {**result[key], **value}
            else:
                result[key] = value

    return result


def extract_subject_mappings(parsed_intent: dict) -> List[dict]:
    """
    提取主体映射列表，用于后续 Identity Anchor 生成

    Returns:
        List of {originalEntityId, fromPlaceholder, toDescription, detailedDescription,
                 persistentAttributes, imageReference, affectedShots, isNewEntity}
    """
    mappings = parsed_intent.get("subjectMapping", [])
    return [
        {
            "originalEntityId": m.get("originalEntityId", "new_char_01"),
            "fromPlaceholder": m.get("fromPlaceholder", "[SUBJECT]"),
            "fromDescription": m.get("fromDescription", ""),
            "toDescription": m.get("toDescription", ""),
            "detailedDescription": m.get("detailedDescription", ""),
            "persistentAttributes": m.get("persistentAttributes", []),
            "imageReference": m.get("imageReference"),
            "affectedShots": m.get("affectedShots", ["all"]),
            "isNewEntity": m.get("isNewEntity", False) or m.get("originalEntityId", "").startswith("new_")
        }
        for m in mappings
    ]


def extract_environment_mappings(parsed_intent: dict) -> List[dict]:
    """
    提取环境映射列表

    Returns:
        List of {originalEntityId, fromPlaceholder, toDescription, detailedDescription,
                 timeOfDay, weather, affectedShots, isNewEntity}
    """
    mappings = parsed_intent.get("environmentMapping", [])
    return [
        {
            "originalEntityId": m.get("originalEntityId", "new_env_01"),
            "fromPlaceholder": m.get("fromPlaceholder", "[SETTING]"),
            "fromDescription": m.get("fromDescription", ""),
            "toDescription": m.get("toDescription", ""),
            "detailedDescription": m.get("detailedDescription", ""),
            "timeOfDay": m.get("timeOfDay", "unchanged"),
            "weather": m.get("weather", "unchanged"),
            "affectedShots": m.get("affectedShots", ["all"]),
            "isNewEntity": m.get("isNewEntity", False) or m.get("originalEntityId", "").startswith("new_")
        }
        for m in mappings
    ]


def get_intent_summary(parsed_intent: dict) -> str:
    """
    生成意图摘要，用于日志和调试

    Returns:
        Human-readable summary string
    """
    intent_type = parsed_intent.get("intentType", "UNKNOWN")
    scope = parsed_intent.get("scope", "UNKNOWN")

    subjects = len(parsed_intent.get("subjectMapping", []))
    environments = len(parsed_intent.get("environmentMapping", []))

    style = parsed_intent.get("styleInstruction", {}).get("artStyle", "None")
    mood = parsed_intent.get("moodTone", {}).get("targetMood", "unchanged")

    plot_enabled = parsed_intent.get("plotRestructure", {}).get("enabled", False)

    summary_parts = [
        f"Type: {intent_type}",
        f"Scope: {scope}",
        f"Subject Changes: {subjects}",
        f"Environment Changes: {environments}",
        f"Style: {style}",
        f"Mood: {mood}",
        f"Plot Restructure: {'Yes' if plot_enabled else 'No'}"
    ]

    return " | ".join(summary_parts)


def check_compliance(parsed_intent: dict) -> tuple:
    """
    检查意图是否通过合规检查

    Returns:
        (is_compliant: bool, issues: List[str])
    """
    compliance = parsed_intent.get("complianceCheck", {})

    is_compliant = compliance.get("passedSafetyCheck", True)
    flagged = compliance.get("flaggedContent", [])

    issues = []

    if not is_compliant:
        issues.append("Safety check failed")

    if flagged:
        issues.extend([f"Flagged: {item}" for item in flagged])

    # 检查 aspect ratio
    ar = compliance.get("aspectRatioLocked", "16:9")
    if ar != "16:9":
        issues.append(f"Invalid aspect ratio: {ar} (must be 16:9)")

    return (len(issues) == 0, issues)
