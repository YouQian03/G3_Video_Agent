# core/meta_prompts/__init__.py
"""
Meta Prompts 模块
包含 Film IR 各阶段使用的核心 Prompts

阶段对应:
- Story Theme Analysis (Pillar I)
- Narrative Extraction (Pillar II)
- Shot Decomposition (Pillar III)
- Intent Parser (M4: 意图解析)
- Intent Fusion (M4: 意图融合)
- Asset Generation (M5: 资产生成)
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
    SHOT_DETECTION_PROMPT,
    SHOT_DETAIL_BATCH_PROMPT,
    convert_to_frontend_format as convert_shot_recipe_to_frontend,
    extract_abstract_layer as extract_shot_recipe_abstract,
    extract_first_frames as extract_shot_first_frames,
    extract_dialogue_timeline as extract_shot_dialogue_timeline,
    create_shot_boundaries_text,
    merge_batch_results
)

# M4: Intent Injection
from .intent_parser import (
    INTENT_PARSER_PROMPT,
    parse_intent_result,
    extract_subject_mappings,
    extract_environment_mappings,
    get_intent_summary,
    check_compliance
)

from .intent_fusion import (
    INTENT_FUSION_PROMPT,
    convert_to_remixed_layer,
    extract_identity_anchors,
    extract_t2i_prompts,
    extract_i2v_prompts,
    get_remix_diff,
    validate_fusion_output,
    generate_fusion_summary,
    clean_prompt_artifacts,
    resolve_anchor_placeholders,
    normalize_camera_field,
    post_process_remixed_layer
)

# Character Ledger (Pillar II extension)
from .character_ledger import (
    CHARACTER_CLUSTERING_PROMPT,
    build_shot_subjects_input,
    process_ledger_result,
    get_ledger_display_summary,
    update_shots_with_entity_refs
)

# M5: Asset Generation
from .asset_prompts import (
    CHARACTER_FRONT_TEMPLATE,
    CHARACTER_SIDE_TEMPLATE,
    CHARACTER_BACK_TEMPLATE,
    ENVIRONMENT_TEMPLATE,
    build_character_prompt,
    build_environment_prompt,
    extract_lighting_from_description
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
    # Character Ledger (Pillar II extension)
    "CHARACTER_CLUSTERING_PROMPT",
    "build_shot_subjects_input",
    "process_ledger_result",
    "get_ledger_display_summary",
    "update_shots_with_entity_refs",
    # Shot Recipe (Pillar III)
    "SHOT_DECOMPOSITION_PROMPT",
    "SHOT_DETECTION_PROMPT",
    "SHOT_DETAIL_BATCH_PROMPT",
    "convert_shot_recipe_to_frontend",
    "extract_shot_recipe_abstract",
    "extract_shot_first_frames",
    "extract_shot_dialogue_timeline",
    "create_shot_boundaries_text",
    "merge_batch_results",
    # Intent Parser (M4)
    "INTENT_PARSER_PROMPT",
    "parse_intent_result",
    "extract_subject_mappings",
    "extract_environment_mappings",
    "get_intent_summary",
    "check_compliance",
    # Intent Fusion (M4)
    "INTENT_FUSION_PROMPT",
    "convert_to_remixed_layer",
    "extract_identity_anchors",
    "extract_t2i_prompts",
    "extract_i2v_prompts",
    "get_remix_diff",
    "validate_fusion_output",
    "generate_fusion_summary",
    # Post-processing utilities
    "clean_prompt_artifacts",
    "resolve_anchor_placeholders",
    "normalize_camera_field",
    "post_process_remixed_layer",
    # Asset Generation (M5)
    "CHARACTER_FRONT_TEMPLATE",
    "CHARACTER_SIDE_TEMPLATE",
    "CHARACTER_BACK_TEMPLATE",
    "ENVIRONMENT_TEMPLATE",
    "build_character_prompt",
    "build_environment_prompt",
    "extract_lighting_from_description"
]
