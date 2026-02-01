# core/meta_prompts/__init__.py
"""
Meta Prompts 模块
包含 Film IR 各阶段使用的核心 Prompts
"""

from .story_theme_analysis import (
    STORY_THEME_ANALYSIS_PROMPT,
    convert_to_frontend_format as convert_story_theme_to_frontend
)

__all__ = [
    "STORY_THEME_ANALYSIS_PROMPT",
    "convert_story_theme_to_frontend"
]
