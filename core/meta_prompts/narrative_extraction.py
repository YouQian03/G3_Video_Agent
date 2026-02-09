# core/meta_prompts/narrative_extraction.py
"""
Meta Prompt: 脚本深度分析与逻辑抽象 (Stage 1 & 2 Fused)
用于提取支柱 II: Narrative Template 的 concrete + abstract 数据
"""

NARRATIVE_EXTRACTION_PROMPT = """
# Prompt: 脚本深度分析与逻辑抽象 (Stage 1 & 2 Fused)

**Role**: You are a Master Screenwriter and Narrative Architect.

**Task**: Reverse-engineer the provided video to extract its "Narrative Skeleton". You must provide two layers of data:
- **Concrete**: Specific details for UI display (with names, locations, proper nouns)
- **Abstract**: Universal archetypes for remixing (with bracketed placeholders)

---

## 1. OUTPUT STRUCTURE (STRICT JSON)

You MUST output a JSON object with the following structure. Each module contains a `concrete` field and an `abstract` field.

```json
{
  "narrativeTemplate": {
    "basicInfo": {
      "concrete": { "scriptName": "", "typeStyle": "", "lengthDuration": "", "creativeBackground": "" },
      "abstract": { "typeStyle": "[GENRE_ARCHETYPE]", "creativeBackground": "[THEMATIC_CONTEXT]" }
    },
    "themeIntent": {
      "concrete": { "coreTheme": "", "subTheme": "", "valueStance": "" },
      "abstract": { "coreTheme": "[UNIVERSAL_MESSAGE]", "subTheme": "[SECONDARY_THEMES]", "valueStance": "[MORAL_POSITION]" }
    },
    "storyStructure": {
      "concrete": { "storyWorld": "", "threeActStructure": "", "plotPoints": "", "endingType": "" },
      "abstract": { "storyWorld": "[WORLD_LOGIC]", "threeActStructure": "[STRUCTURAL_SKELETON]", "plotPoints": "[BEAT_SHEET]", "endingType": "[RESOLUTION_NATURE]" }
    },
    "characterSystem": {
      "concrete": { "protagonist": "", "antagonist": "", "supportingRoles": "", "relationships": "" },
      "abstract": { "protagonist": "[PROTAGONIST_ARCHETYPE]", "antagonist": "[OPPOSING_FORCE]", "supportingRoles": "[SUPPORT_ROLES]", "relationships": "[DYNAMIC_LOGIC]" }
    },
    "characterArc": {
      "concrete": { "initialState": "", "actionChanges": "", "finalState": "" },
      "abstract": { "initialState": "[START_STATE]", "actionChanges": "[TRANSFORMATION_TRIGGERS]", "finalState": "[END_STATE]" }
    },
    "conflictDesign": {
      "concrete": { "externalConflict": "", "internalConflict": "", "conflictEscalation": "" },
      "abstract": { "externalConflict": "[OUTSIDE_STRUGGLE]", "internalConflict": "[PSYCHOLOGICAL_STRUGGLE]", "conflictEscalation": "[TENSION_CURVE]" }
    },
    "plotRhythm": {
      "concrete": { "sceneArrangement": "", "rhythmControl": "", "suspenseSetting": "" },
      "abstract": { "sceneArrangement": "[SEQUENCE_LOGIC]", "rhythmControl": "[PACING_TEMPLATE]", "suspenseSetting": "[ENGAGEMENT_METHOD]" }
    },
    "dialogueAction": {
      "concrete": { "dialogueFunction": "", "subtext": "", "behaviorLogic": "" },
      "abstract": { "dialogueFunction": "[COMMUNICATION_PURPOSE]", "subtext": "[HIDDEN_MEANING]", "behaviorLogic": "[ACTION_MOTIVATION]" }
    },
    "symbolMetaphor": {
      "concrete": { "coreImagery": "", "symbolicMeaning": "" },
      "abstract": { "coreImagery": "[VISUAL_MOTIFS]", "symbolicMeaning": "[REPRESENTATIONAL_LOGIC]" }
    },
    "genreStyle": {
      "concrete": { "genreRules": "", "narrativeStyle": "" },
      "abstract": { "genreRules": "[GENRE_CONVENTIONS]", "narrativeStyle": "[STORYTELLING_TONE]" }
    },
    "visualPotential": {
      "concrete": { "visualSense": "", "audioVisualSpace": "" },
      "abstract": { "visualSense": "[AESTHETIC_OPPORTUNITY]", "audioVisualSpace": "[SENSORY_LOGIC]" }
    },
    "overallEvaluation": {
      "concrete": { "strengths": "", "weaknesses": "", "revisionDirection": "" },
      "abstract": { "strengths": "[STRUCTURAL_ASSETS]", "weaknesses": "[LOGICAL_GAPS]", "revisionDirection": "[REMIX_STRATEGY]" }
    },
    "detailedCharacterBios": {
       "protagonist_detail": "80-120 word exhaustive visual and background description using SPECIFIC details from video.",
       "antagonist_detail": "If applicable, 50-80 word visual description of the opposing force.",
       "props_detail": "Detailed visual description of key items, objects, or environmental elements."
    }
  }
}
```

---

## 2. EXTRACTION GUIDELINES

- **Concrete Layer**: Use specific names (Jack), locations (Seattle), and details. Keep each value within **15-20 words** to fit the UI table.
- **Abstract Layer**: Replace proper nouns with bracketed placeholders or archetypes (e.g., "[PROTAGONIST]", "A high-pressure metropolis").
- **Detailed Bios**: This is the **only place** allowed to have long text (80-120 words). It must be ultra-descriptive to serve as a prompt anchor for asset generation.
- **Terminology**: Use professional screenwriting terms ("Inciting Incident", "Character Arc", "Three-Act Structure", etc.).

---

## 3. DATA INTEGRITY CONSTRAINTS

- Output **ONLY pure JSON**. No markdown code blocks, no conversational text.
- Every key in the schema **MUST** be present in your response.
- If an element cannot be explicitly identified, provide a **"Reasonable Inference"** based on cinematic context.
- Do NOT include apologies or explanations inside JSON values.

---

## 4. INPUT CONTENT TO ANALYZE

Analyze the provided video file:
{input_content}
"""


def convert_to_frontend_format(ai_output) -> dict:
    """
    将 AI 输出的 concrete 层转换为前端 ScriptAnalysis 格式

    主要处理:
    - 提取每个模块的 concrete 部分
    - lengthDuration -> length 字段映射
    """
    # 处理 list 类型的输出（Gemini 有时返回数组）
    if isinstance(ai_output, list):
        if len(ai_output) > 0 and isinstance(ai_output[0], dict):
            ai_output = ai_output[0]
        else:
            return {}

    if not isinstance(ai_output, dict):
        return {}

    template = ai_output.get("narrativeTemplate", ai_output)

    def get_concrete(module_name: str) -> dict:
        """安全获取 concrete 数据"""
        module = template.get(module_name, {})
        if isinstance(module, dict):
            return module.get("concrete", module)
        return {}

    basic_info = get_concrete("basicInfo")

    return {
        "basicInfo": {
            "scriptName": basic_info.get("scriptName", ""),
            "typeStyle": basic_info.get("typeStyle", ""),
            "length": basic_info.get("lengthDuration", ""),  # 字段映射
            "creativeBackground": basic_info.get("creativeBackground", "")
        },
        "themeIntent": get_concrete("themeIntent"),
        "storyStructure": get_concrete("storyStructure"),
        "characterSystem": get_concrete("characterSystem"),
        "characterArc": get_concrete("characterArc"),
        "conflictDesign": get_concrete("conflictDesign"),
        "plotRhythm": get_concrete("plotRhythm"),
        "dialogueAction": get_concrete("dialogueAction"),
        "symbolMetaphor": get_concrete("symbolMetaphor"),
        "genreStyle": get_concrete("genreStyle"),
        "visualPotential": get_concrete("visualPotential"),
        "overallEvaluation": get_concrete("overallEvaluation")
    }


def extract_abstract_layer(ai_output) -> dict:
    """
    提取 AI 输出的 abstract 层，作为隐形模板存储
    """
    # 处理 list 类型的输出
    if isinstance(ai_output, list):
        if len(ai_output) > 0 and isinstance(ai_output[0], dict):
            ai_output = ai_output[0]
        else:
            return {}

    if not isinstance(ai_output, dict):
        return {}

    template = ai_output.get("narrativeTemplate", ai_output)

    def get_abstract(module_name: str) -> dict:
        """安全获取 abstract 数据"""
        module = template.get(module_name, {})
        if isinstance(module, dict):
            return module.get("abstract", {})
        return {}

    return {
        "basicInfo": get_abstract("basicInfo"),
        "themeIntent": get_abstract("themeIntent"),
        "storyStructure": get_abstract("storyStructure"),
        "characterSystem": get_abstract("characterSystem"),
        "characterArc": get_abstract("characterArc"),
        "conflictDesign": get_abstract("conflictDesign"),
        "plotRhythm": get_abstract("plotRhythm"),
        "dialogueAction": get_abstract("dialogueAction"),
        "symbolMetaphor": get_abstract("symbolMetaphor"),
        "genreStyle": get_abstract("genreStyle"),
        "visualPotential": get_abstract("visualPotential"),
        "overallEvaluation": get_abstract("overallEvaluation")
    }


def extract_hidden_assets(ai_output) -> dict:
    """
    提取 detailedCharacterBios 作为隐藏资产
    用于 Stage 3 资产生成
    """
    # 处理 list 类型的输出
    if isinstance(ai_output, list):
        if len(ai_output) > 0 and isinstance(ai_output[0], dict):
            ai_output = ai_output[0]
        else:
            return {}

    if not isinstance(ai_output, dict):
        return {}

    template = ai_output.get("narrativeTemplate", ai_output)
    return template.get("detailedCharacterBios", {})
