# core/meta_prompts/asset_prompts.py
"""
Asset Generation Prompts - 资产生成 Prompt 模板

用于生成角色三视图和环境参考图的 Prompt 模板。
设计原则：
1. 角色一致性：通过详细描述 + 链式参考保持一致
2. 光影锚定：环境图强调光源方向，为 Veo 提供光影配方
3. 技术规范：16:9 构图，无水印，高细节
"""

from typing import List, Optional


# ============================================================
# 角色三视图模板
# ============================================================

CHARACTER_FRONT_TEMPLATE = """Cinematic character reference sheet, front facing view, looking directly at camera.

Character: {anchor_name}
{detailed_description}

{attributes_section}{style_section}

Technical requirements:
- Clean white studio background
- Professional three-point lighting
- High detail, sharp focus
- Single character only, full body visible
- No text, no watermarks, no logos
- Consistent proportions and features
- 16:9 widescreen composition with character centered
- 2K resolution quality
"""

CHARACTER_SIDE_TEMPLATE = """Cinematic character reference sheet, side profile view, facing left.
IMPORTANT: This must be the SAME CHARACTER as the reference image provided.

Character: {anchor_name}
{detailed_description}

{attributes_section}{style_section}

Consistency requirements:
- Exact same clothing, accessories, and features as the front view
- Same body proportions and height
- Same lighting setup and color temperature

Technical requirements:
- Clean white studio background
- Professional three-point lighting, same as front view
- High detail, sharp focus
- Single character only, full body visible
- No text, no watermarks, no logos
- 16:9 widescreen composition with character centered
- 2K resolution quality
"""

CHARACTER_BACK_TEMPLATE = """Cinematic character reference sheet, back view, facing away from camera.
IMPORTANT: This must be the SAME CHARACTER as the reference image provided.

Character: {anchor_name}
{detailed_description}

{attributes_section}{style_section}

Consistency requirements:
- Exact same clothing, accessories, and hairstyle as previous views
- Same body proportions and height
- Same lighting setup and color temperature

Technical requirements:
- Clean white studio background
- Professional three-point lighting, same as other views
- High detail, sharp focus
- Single character only, full body visible
- No text, no watermarks, no logos
- 16:9 widescreen composition with character centered
- 2K resolution quality
"""


# ============================================================
# 环境参考图模板
# ============================================================

ENVIRONMENT_TEMPLATE = """Cinematic environment establishing shot, wide angle composition.

Location: {anchor_name}
{detailed_description}

Lighting anchor (CRITICAL for video generation):
{atmospheric_conditions}

{style_section}

Technical requirements:
- Wide angle lens perspective (24mm equivalent)
- Rich environmental detail and depth
- Cinematic color grading
- High detail, sharp focus throughout depth of field
- No people, no characters in frame
- No text, no watermarks, no logos
- 16:9 widescreen composition
- 2K resolution quality
- Suitable as background reference for video production
"""


# ============================================================
# 辅助函数
# ============================================================

def build_character_prompt(
    view: str,
    anchor_name: str,
    detailed_description: str,
    persistent_attributes: Optional[List[str]] = None,
    style_adaptation: Optional[str] = None
) -> str:
    """
    构建角色视图 prompt

    Args:
        view: "front", "side", "back"
        anchor_name: 角色名称
        detailed_description: 详细描述 (80-120字)
        persistent_attributes: 持久属性列表
        style_adaptation: 风格适配说明

    Returns:
        完整的 prompt 字符串
    """
    # 选择模板
    templates = {
        "front": CHARACTER_FRONT_TEMPLATE,
        "side": CHARACTER_SIDE_TEMPLATE,
        "back": CHARACTER_BACK_TEMPLATE
    }
    template = templates.get(view, CHARACTER_FRONT_TEMPLATE)

    # 构建属性部分
    attributes_section = ""
    if persistent_attributes:
        attrs = ", ".join(persistent_attributes)
        attributes_section = f"Key visual features that MUST be consistent: {attrs}\n\n"

    # 构建风格部分
    style_section = ""
    if style_adaptation:
        style_section = f"Style adaptation: {style_adaptation}\n\n"

    return template.format(
        anchor_name=anchor_name,
        detailed_description=detailed_description,
        attributes_section=attributes_section,
        style_section=style_section
    ).strip()


def build_environment_prompt(
    anchor_name: str,
    detailed_description: str,
    atmospheric_conditions: Optional[str] = None,
    style_adaptation: Optional[str] = None
) -> str:
    """
    构建环境参考图 prompt

    Args:
        anchor_name: 环境名称
        detailed_description: 详细描述 (80-120字)
        atmospheric_conditions: 大气条件（光源方向、天气、时间）
        style_adaptation: 风格适配说明

    Returns:
        完整的 prompt 字符串
    """
    # 默认大气条件
    if not atmospheric_conditions:
        atmospheric_conditions = "Natural daylight, soft shadows, neutral color temperature"

    # 构建风格部分
    style_section = ""
    if style_adaptation:
        style_section = f"Style adaptation: {style_adaptation}\n\n"

    return ENVIRONMENT_TEMPLATE.format(
        anchor_name=anchor_name,
        detailed_description=detailed_description,
        atmospheric_conditions=atmospheric_conditions,
        style_section=style_section
    ).strip()


def extract_lighting_from_description(description: str) -> str:
    """
    从描述中提取光照信息，用于光影锚定

    Args:
        description: 环境详细描述

    Returns:
        光照描述字符串
    """
    # 光照关键词
    lighting_keywords = [
        "sunlight", "daylight", "moonlight", "neon", "fluorescent",
        "warm", "cool", "golden hour", "blue hour", "overcast",
        "rim light", "backlight", "soft light", "hard light",
        "morning", "evening", "night", "afternoon", "dawn", "dusk"
    ]

    found_lighting = []
    description_lower = description.lower()

    for keyword in lighting_keywords:
        if keyword in description_lower:
            found_lighting.append(keyword)

    if found_lighting:
        return f"Detected lighting elements: {', '.join(found_lighting)}"
    else:
        return "Natural ambient lighting"


# ============================================================
# 导出
# ============================================================

__all__ = [
    "CHARACTER_FRONT_TEMPLATE",
    "CHARACTER_SIDE_TEMPLATE",
    "CHARACTER_BACK_TEMPLATE",
    "ENVIRONMENT_TEMPLATE",
    "build_character_prompt",
    "build_environment_prompt",
    "extract_lighting_from_description"
]
