# core/meta_prompts/__init__.py
"""
Meta Prompts 模块
包含 Film IR 各阶段使用的核心 Prompts
"""

from .story_theme_analysis import (
    STORY_THEME_ANALYSIS_PROMPT,
    convert_to_frontend_format as convert_story_theme_to_frontend,
    extract_abstract_layer as extract_story_theme_abstract
)

from .narrative_extraction import (
    NARRATIVE_EXTRACTION_PROMPT,
    convert_to_frontend_format as convert_narrative_to_frontend,
    extract_abstract_layer as extract_narrative_abstract,
    extract_hidden_assets as extract_narrative_hidden_assets
)

from .shot_decomposition import (
    SHOT_DECOMPOSITION_PROMPT,
    convert_to_frontend_format as convert_shot_recipe_to_frontend,
    extract_abstract_layer as extract_shot_recipe_abstract,
    extract_first_frames as extract_shot_first_frames,
    extract_dialogue_timeline as extract_shot_dialogue_timeline
)

__all__ = [
    # Story Theme (Pillar I)
    "STORY_THEME_ANALYSIS_PROMPT",
    "convert_story_theme_to_frontend",
    "extract_story_theme_abstract",
    # Narrative Template (Pillar II)
    "NARRATIVE_EXTRACTION_PROMPT",
    "convert_narrative_to_frontend",
    "extract_narrative_abstract",
    "extract_narrative_hidden_assets",
    # Shot Recipe (Pillar III)
    "SHOT_DECOMPOSITION_PROMPT",
    "convert_shot_recipe_to_frontend",
    "extract_shot_recipe_abstract",
    "extract_shot_first_frames",
    "extract_shot_dialogue_timeline"
]
