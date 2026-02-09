# core/meta_prompts/story_theme_analysis.py
"""
Meta Prompt: 原片影视级深度分析 (Stage 1 & 2 Fused)
用于提取支柱 I: Story Theme 的 concrete + abstract 数据
"""

from typing import Dict, Any, Optional

STORY_THEME_ANALYSIS_PROMPT = """
# Prompt: 原片影视级深度分析 (Stage 1 & 2 Fused)

**Role**: You are a world-class film critic, senior narrative strategist, and technical director of photography.

**Task**: Perform a granular "Film Perspective" analysis of the provided video. You must provide two layers of data:
- **Concrete**: Specific details with names, locations, proper nouns (for UI display)
- **Abstract**: Universal archetypes and reusable templates (for remixing)

---

## 1. OUTPUT STRUCTURE (STRICT JSON)

You MUST output a JSON object where each module contains a `concrete` field and an `abstract` field. Maintain the exact structure below.

{
  "storyThemeAnalysis": {
    "basicInfo": {
      "concrete": {
        "title": "e.g., Urban Solitude",
        "type": "e.g., Drama / Slice of Life",
        "duration": "e.g., 5:32",
        "creator": "e.g., Independent Filmmaker",
        "background": "e.g., Modern Seattle exploring themes of urban isolation"
      },
      "abstract": {
        "title": "[VIDEO_TITLE]",
        "type": "[GENRE_PRIMARY] / [GENRE_SECONDARY]",
        "duration": "[DURATION_CATEGORY]",
        "creator": "[CREATOR_ARCHETYPE]",
        "background": "[TEMPORAL_SETTING] [SPATIAL_ARCHETYPE] exploring [THEMATIC_DOMAIN]"
      }
    },
    "coreTheme": {
      "concrete": {
        "summary": "e.g., Jack's journey from isolation to connection through unexpected encounters",
        "keywords": "e.g., Loneliness, Connection, Urban life, Redemption"
      },
      "abstract": {
        "summary": "[PROTAGONIST_ARCHETYPE]'s transformation from [INITIAL_STATE] to [FINAL_STATE] through [CATALYST_TYPE]",
        "keywords": "[EMOTION_A], [EMOTION_B], [SETTING_QUALITY], [RESOLUTION_THEME]"
      }
    },
    "narrative": {
      "concrete": {
        "startingPoint": "e.g., Jack wakes up alone in his apartment, routine morning",
        "coreConflict": "e.g., Jack's fear of vulnerability vs. desire for connection",
        "climax": "e.g., Confrontation with Sarah at the coffee shop",
        "ending": "e.g., Open-ended; Jack takes first step toward reconciliation"
      },
      "abstract": {
        "startingPoint": "[PROTAGONIST] in [EQUILIBRIUM_STATE], establishing [WORLD_NORMAL]",
        "coreConflict": "[INTERNAL_DESIRE] vs. [EXTERNAL_OBSTACLE] or [PSYCHOLOGICAL_BARRIER]",
        "climax": "[CONFRONTATION_TYPE] at [SYMBOLIC_LOCATION] forcing [CHOICE_MOMENT]",
        "ending": "[RESOLUTION_TYPE]: [PROTAGONIST] achieves [TRANSFORMATION_OUTCOME]"
      }
    },
    "narrativeStructure": {
      "concrete": {
        "narrativeMethod": "e.g., Linear with reflective voiceover moments",
        "timeStructure": "e.g., Chronological with slow-motion emotional beats"
      },
      "abstract": {
        "narrativeMethod": "[STRUCTURE_TYPE] with [NARRATIVE_DEVICE] for [EMOTIONAL_PURPOSE]",
        "timeStructure": "[TEMPORAL_FLOW] with [TIME_MANIPULATION] at [DRAMATIC_MOMENTS]"
      }
    },
    "characterAnalysis": {
      "concrete": {
        "protagonist": "e.g., Jack, 35, introverted barista struggling with divorce",
        "characterChange": "e.g., From closed-off cynicism to cautious openness",
        "relationships": "e.g., Estranged from ex-wife Sarah; mentored by elderly customer Mr. Chen"
      },
      "abstract": {
        "protagonist": "[ARCHETYPE], [AGE_RANGE], [DEFINING_TRAIT] dealing with [CORE_WOUND]",
        "characterChange": "From [INITIAL_FLAW] to [GROWTH_DESTINATION] via [TRANSFORMATION_ARC]",
        "relationships": "[RELATIONSHIP_A]: [DYNAMIC_TYPE]; [RELATIONSHIP_B]: [FUNCTION_IN_STORY]"
      }
    },
    "audioVisual": {
      "concrete": {
        "visualStyle": "e.g., Muted teal-orange palette, high contrast, urban grit aesthetic",
        "cameraLanguage": "e.g., Intimate close-ups, slow dolly-ins, handheld during conflict",
        "soundDesign": "e.g., Ambient city noise, melancholic piano score, sparse dialogue"
      },
      "abstract": {
        "visualStyle": "[COLOR_TEMPERATURE] [CONTRAST_LEVEL] palette with [AESTHETIC_QUALITY] texture",
        "cameraLanguage": "[SHOT_SCALE_TENDENCY] with [MOVEMENT_STYLE] for [EMOTIONAL_EFFECT]",
        "soundDesign": "[AMBIENT_LAYER] base, [SCORE_MOOD] instrumentation, [DIALOGUE_DENSITY] speech"
      }
    },
    "symbolism": {
      "concrete": {
        "repeatingImagery": "e.g., Empty coffee cups, rain on windows, closed doors",
        "symbolicMeaning": "e.g., Cups = emptiness seeking filling; Rain = emotional cleansing"
      },
      "abstract": {
        "repeatingImagery": "[OBJECT_MOTIF_A], [ENVIRONMENTAL_MOTIF], [BARRIER_SYMBOL]",
        "symbolicMeaning": "[MOTIF_A] = [THEMATIC_REPRESENTATION]; [MOTIF_B] = [EMOTIONAL_SUBTEXT]"
      }
    },
    "thematicStance": {
      "concrete": {
        "creatorAttitude": "e.g., Sympathetic but unflinching; avoids easy resolutions",
        "emotionalTone": "e.g., Melancholic with undercurrents of hope"
      },
      "abstract": {
        "creatorAttitude": "[STANCE_TYPE] perspective with [TONAL_QUALITY] toward subject",
        "emotionalTone": "[PRIMARY_EMOTION] balanced by [COUNTER_EMOTION]"
      }
    },
    "realWorldSignificance": {
      "concrete": {
        "socialEmotionalValue": "e.g., Addresses epidemic of urban loneliness in modern society",
        "audienceInterpretation": "e.g., Resonates with 25-45 urban professionals feeling disconnected"
      },
      "abstract": {
        "socialEmotionalValue": "Addresses [CONTEMPORARY_ISSUE] in [CULTURAL_CONTEXT]",
        "audienceInterpretation": "Resonates with [TARGET_DEMOGRAPHIC] experiencing [SHARED_CONDITION]"
      }
    }
  }
}

---

## 2. EXTRACTION GUIDELINES

### Concrete Layer:
- Use **specific names** (Jack, Seattle, Mr. Chen), exact durations, and real details
- Keep each value **concise** (15-25 words) to fit UI table cells
- Preserve the "soul" of the original work

### Abstract Layer:
- Replace proper nouns with **bracketed archetypes** (e.g., `[PROTAGONIST]`, `[URBAN_SETTING]`)
- **Conceptual abstraction, NOT simple bracketing**:
  - BAD: `"[Theme]"`
  - GOOD: `"Exploring [ARCHETYPE_A]'s core conflict and self-redemption in [SPECIFIC_ENVIRONMENT]"`
- For **audioVisual**: Keep technical parameters (shot scale, contrast, color temperature) but strip scene-specific descriptions
  - BAD: `"Yellow warm light in the coffee shop"`
  - GOOD: `"Low-contrast warm lighting with enveloping atmospheric quality"`

### Terminology:
- Use professional film terms: "Inciting Incident", "Character Arc", "Teal & Orange", "Dolly-in", etc.

---

## 3. DATA INTEGRITY CONSTRAINTS

- Output **ONLY pure JSON**. No markdown code blocks, no conversational text.
- Every key in the schema **MUST** be present.
- If an element cannot be explicitly identified, provide a **"Reasonable Inference"** based on cinematic context.
- Do NOT include apologies or explanations inside JSON values.

---

## 4. INPUT CONTENT TO ANALYZE

Analyze the provided video file:
{input_content}
"""


def convert_to_frontend_format(ai_output) -> dict:
    """
    将 AI 输出的 concrete 层转换为前端 StoryThemeAnalysis 格式

    从新的双层结构中提取 concrete 子字段
    """
    # 处理 list 类型的输出（Gemini 有时返回数组）
    if isinstance(ai_output, list):
        if len(ai_output) > 0 and isinstance(ai_output[0], dict):
            ai_output = ai_output[0]
        else:
            return {}

    if not isinstance(ai_output, dict):
        return {}

    # 获取 storyThemeAnalysis 根对象
    analysis = ai_output.get("storyThemeAnalysis", ai_output)

    def get_concrete(module_name: str) -> dict:
        """安全获取 concrete 数据"""
        module = analysis.get(module_name, {})
        if isinstance(module, dict):
            # 新格式：有 concrete 子字段
            if "concrete" in module:
                return module["concrete"]
            # 兼容旧格式：直接返回模块数据
            return module
        return {}

    return {
        "basicInfo": get_concrete("basicInfo"),
        "coreTheme": get_concrete("coreTheme"),
        "narrative": get_concrete("narrative"),
        "narrativeStructure": get_concrete("narrativeStructure"),
        "characterAnalysis": get_concrete("characterAnalysis"),
        "audioVisual": get_concrete("audioVisual"),
        "symbolism": get_concrete("symbolism"),
        "thematicStance": get_concrete("thematicStance"),
        "realWorldSignificance": get_concrete("realWorldSignificance")
    }


def extract_abstract_layer(ai_output) -> dict:
    """
    提取 AI 输出的 abstract 层，作为隐形模板存储

    用于后续 Remix 阶段的意图注入
    """
    # 处理 list 类型的输出（Gemini 有时返回数组）
    if isinstance(ai_output, list):
        if len(ai_output) > 0 and isinstance(ai_output[0], dict):
            ai_output = ai_output[0]
        else:
            return {}

    if not isinstance(ai_output, dict):
        return {}

    # 获取 storyThemeAnalysis 根对象
    analysis = ai_output.get("storyThemeAnalysis", ai_output)

    def get_abstract(module_name: str) -> dict:
        """安全获取 abstract 数据"""
        module = analysis.get(module_name, {})
        if isinstance(module, dict):
            return module.get("abstract", {})
        return {}

    return {
        "basicInfo": get_abstract("basicInfo"),
        "coreTheme": get_abstract("coreTheme"),
        "narrative": get_abstract("narrative"),
        "narrativeStructure": get_abstract("narrativeStructure"),
        "characterAnalysis": get_abstract("characterAnalysis"),
        "audioVisual": get_abstract("audioVisual"),
        "symbolism": get_abstract("symbolism"),
        "thematicStance": get_abstract("thematicStance"),
        "realWorldSignificance": get_abstract("realWorldSignificance")
    }
