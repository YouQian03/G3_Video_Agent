# core/meta_prompts/story_theme_analysis.py
"""
Meta Prompt: 原片影视级深度分析 (Stage 1: Specific Analysis)
用于提取支柱 I: Story Theme 的具体数据
"""

STORY_THEME_ANALYSIS_PROMPT = """
# Prompt: 原片影视级深度分析 (Stage 1: Specific Analysis)

**Role**: You are a world-class film critic, senior narrative strategist, and technical director of photography. Your task is to perform a granular "Film Perspective" analysis of the provided video/script.

**Objective**: Extract a comprehensive 9-dimensional data set that captures the specific narrative and technical essence of the original work.

---

### 1. ANALYSIS GUIDELINES (Extraction Principles)
- **Specific Accuracy**: Since this is the "Specific Analysis" stage, you MUST include specific names, locations, and proper nouns found in the video.
- **Preserve Essence**: Extract the most valuable key information; remove redundancy while maintaining the narrative "soul".
- **Clear and Complete**: Ensure every value has clear meaning and is logically complete.
- **Professional Terminology**: Use precise film industry terms (e.g., "Teal & Orange palette", "Dolly-in", "Three-act structure").
- **Flexible Length**: Content can be a short tag or a detailed description depending on the complexity of the scene.

---

### 2. OUTPUT STRUCTURE (MUST FOLLOW EXACTLY)
Your response must be a valid JSON object. Do not include markdown tags (like ```json) or any conversational text.

{
  "basicInfo": {
    "titleTypeDuration": "e.g., [Filename] / [Genre] / [Sub-genre] / [Exact Duration]",
    "creatorDirector": "Identify the creator or style (e.g., Independent Filmmaker / Professional Studio)",
    "creativeBackground": "e.g., Modern urban setting exploring themes of connection"
  },
  "coreTheme": {
    "themeSummary": "e.g., Finding meaningful connection in an increasingly isolated world",
    "themeKeywords": "Extract 4-5 high-impact keywords (e.g., Loneliness, Connection, Urban life)"
  },
  "narrativeContent": {
    "storyStartingPoint": "Describe the initial status quo or the 'Inciting Incident'",
    "coreConflict": "Identify the primary struggle (Internal vs. External)",
    "climaxSegment": "Pinpoint the moment of highest tension or the 'Turning Point'",
    "endingMethod": "Analyze the resolution style (e.g., Open-ended, Twist, Circular)"
  },
  "narrativeStructure": {
    "narrativeMethod": "e.g., Linear with reflective moments, POV-driven, Nonlinear Montage",
    "timeStructure": "e.g., Chronological, Flashbacks, Slow-motion expansion"
  },
  "characterAnalysis": {
    "protagonist": "Specific description of the protagonist's traits, motivation, and names",
    "characterChange": "Identify the 'Character Arc' (e.g., From isolation to openness)",
    "characterRelationships": "Analyze specific interactions between characters (use names)"
  },
  "audioVisualLanguage": {
    "visualStyle": "Analyze color grading, contrast, and aesthetic (e.g., Muted colors, urban landscapes)",
    "cameraLanguage": "Identify shot scales (CU/WS) and movements (Dolly, Pan, Handheld)",
    "soundDesign": "Describe the foley, score, and use of silence/dialogue"
  },
  "symbolismMetaphor": {
    "repeatingImagery": "Identify visual motifs (e.g., Windows, reflections, empty chairs)",
    "symbolicMeaning": "Decode the deeper subtext of these motifs"
  },
  "thematicStance": {
    "creatorAttitude": "e.g., Sympathetic, Objective, Cynical, Hopeful",
    "emotionalTone": "e.g., Melancholic but ultimately uplifting"
  },
  "realWorldSignificance": {
    "socialEmotionalValue": "Analyze the relevance to modern social or psychological issues",
    "audienceInterpretation": "Predict how the target audience will resonate with the content"
  }
}

---

### 3. INPUT CONTENT TO ANALYZE
Analyze the provided video file/script content:
{input_content}

### 4. DATA INTEGRITY CONSTRAINTS
- **No Omissions**: Every key in the JSON schema MUST be present in your response.
- **Handling Uncertainty**: If a specific element cannot be explicitly identified:
  1. Try to provide a "Reasonable Inference" based on the overall cinematic context (e.g., if the creator is unknown, infer the style as "Independent Stylist").
  2. If an inference is impossible, use an empty string "" or "Not explicitly identified".
- **No Explanations**: Do NOT include conversational filler or apologies (e.g., "I couldn't find...") inside the JSON values.
"""


def convert_to_frontend_format(ai_output: dict) -> dict:
    """
    将 AI 输出格式转换为前端 StoryThemeAnalysis 格式

    AI 输出字段名 -> 前端字段名 映射
    """
    # 解析 titleTypeDuration 字段
    title_type_duration = ai_output.get("basicInfo", {}).get("titleTypeDuration", "")
    parts = [p.strip() for p in title_type_duration.split("/")]

    title = parts[0] if len(parts) > 0 else ""
    type_info = parts[1] if len(parts) > 1 else ""
    if len(parts) > 2:
        type_info += " / " + parts[2]  # 合并 genre 和 sub-genre
    duration = parts[-1] if len(parts) > 3 else (parts[2] if len(parts) > 2 else "")

    return {
        "basicInfo": {
            "title": title,
            "type": type_info,
            "duration": duration,
            "creator": ai_output.get("basicInfo", {}).get("creatorDirector", ""),
            "background": ai_output.get("basicInfo", {}).get("creativeBackground", "")
        },
        "coreTheme": {
            "summary": ai_output.get("coreTheme", {}).get("themeSummary", ""),
            "keywords": ai_output.get("coreTheme", {}).get("themeKeywords", "")
        },
        "narrative": {
            "startingPoint": ai_output.get("narrativeContent", {}).get("storyStartingPoint", ""),
            "coreConflict": ai_output.get("narrativeContent", {}).get("coreConflict", ""),
            "climax": ai_output.get("narrativeContent", {}).get("climaxSegment", ""),
            "ending": ai_output.get("narrativeContent", {}).get("endingMethod", "")
        },
        "narrativeStructure": {
            "narrativeMethod": ai_output.get("narrativeStructure", {}).get("narrativeMethod", ""),
            "timeStructure": ai_output.get("narrativeStructure", {}).get("timeStructure", "")
        },
        "characterAnalysis": {
            "protagonist": ai_output.get("characterAnalysis", {}).get("protagonist", ""),
            "characterChange": ai_output.get("characterAnalysis", {}).get("characterChange", ""),
            "relationships": ai_output.get("characterAnalysis", {}).get("characterRelationships", "")
        },
        "audioVisual": {
            "visualStyle": ai_output.get("audioVisualLanguage", {}).get("visualStyle", ""),
            "cameraLanguage": ai_output.get("audioVisualLanguage", {}).get("cameraLanguage", ""),
            "soundDesign": ai_output.get("audioVisualLanguage", {}).get("soundDesign", "")
        },
        "symbolism": {
            "repeatingImagery": ai_output.get("symbolismMetaphor", {}).get("repeatingImagery", ""),
            "symbolicMeaning": ai_output.get("symbolismMetaphor", {}).get("symbolicMeaning", "")
        },
        "thematicStance": {
            "creatorAttitude": ai_output.get("thematicStance", {}).get("creatorAttitude", ""),
            "emotionalTone": ai_output.get("thematicStance", {}).get("emotionalTone", "")
        },
        "realWorldSignificance": {
            "socialEmotionalValue": ai_output.get("realWorldSignificance", {}).get("socialEmotionalValue", ""),
            "audienceInterpretation": ai_output.get("realWorldSignificance", {}).get("audienceInterpretation", "")
        }
    }
