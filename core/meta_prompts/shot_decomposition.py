# core/meta_prompts/shot_decomposition.py
"""
Meta Prompt: 影视级分镜拆解与动力学配方 (Stage 1 & 2 Fused)
用于提取支柱 III: Shot Recipe 的 concrete + abstract 数据
"""

from typing import Dict, Any, Optional, List

SHOT_DECOMPOSITION_PROMPT = """
# Prompt: 影视级分镜拆解与动力学配方 (Shot Recipe Extraction)

**Role**: You are a Master Cinematographer, Storyboard Artist, and VFX Supervisor with expertise in AI-driven video generation pipelines.

**Task**: Perform a frame-by-frame technical decomposition of the provided video. Extract a "Technical Skeleton" that enables an AI pipeline (Imagen 4.0 → Veo 3.1) to replicate the cinematography while allowing for narrative remixing.

**Output Layers**:
- **Concrete**: Specific technical parameters with exact values (for direct T2I/I2V prompt generation)
- **Abstract**: Narrative functions and reusable templates (for remixing with new subjects)

---

## 1. SHOT SPLITTING RULES (Strictly Follow)

### Boundaries
- **Cut Detection**: Identify exact timestamps where visual cuts occur
- **Camera Continuity**: Do NOT split continuous camera movements (pan/tilt/dolly/zoom) unless there is a literal cut
- **Scene Changes**: New location or significant time jump = new shot

### Duration Constraints
- **Minimum**: ≥1.0 second (merge micro-cuts into logical units)
- **Maximum**: No hard limit, but shots >5.0 seconds MUST include `"longTake": true` flag
- **Target Density**: For a 60-second video, aim for 15-25 shots

### Quantity Limit
- **Maximum 30 shots** per video
- If raw cut count exceeds 30, merge adjacent shots that share:
  - Same subject focus
  - Same narrative beat
  - Similar camera language
- Prioritize preserving: HOOK, CATALYST, CLIMAX, RESOLUTION beats

### Precision Requirement
- Sum of all `durationSeconds` MUST equal total video length
- Timestamps in format: `"HH:MM:SS.mmm"` (e.g., `"00:00:02.500"`)

---

## 2. OUTPUT STRUCTURE (STRICT JSON)

{
  "shotRecipe": {
    "videoMetadata": {
      "totalDuration": "00:01:23.456",
      "totalShots": 18,
      "averageShotDuration": 4.6
    },
    "globalSettings": {
      "concrete": {
        "visualLanguage": {
          "visualStyle": "e.g., Cinematic realism with desaturated cool tones",
          "colorPalette": "e.g., Teal shadows (#2A4858), amber highlights (#D4A574), muted earth tones",
          "lightingDesign": "e.g., High-contrast chiaroscuro with motivated practical lights, 4:1 key-to-fill ratio",
          "cameraPhilosophy": "e.g., Intimate handheld for emotional beats, locked-off tripod for tension"
        },
        "soundDesign": {
          "musicStyle": "e.g., Minimalist piano with ambient electronic textures",
          "soundAtmosphere": "e.g., Urban room tone, distant traffic hum, subtle HVAC",
          "rhythmPattern": "e.g., Slow builds punctuated by sharp silence"
        },
        "symbolism": {
          "repeatingImagery": "e.g., Closed doors, rain on windows, empty chairs",
          "symbolicMeaning": "e.g., Doors = emotional barriers; Rain = cleansing/release; Empty chairs = absence"
        }
      },
      "abstract": {
        "styleCategory": "REALISTIC | STYLIZED | HYBRID",
        "moodBoardTags": ["melancholic", "intimate", "urban-grit", "naturalistic"],
        "referenceAesthetics": "e.g., Roger Deakins naturalism meets Wong Kar-wai color sensibility",
        "rhythmSignature": "e.g., Contemplative long takes punctuated by rapid montage bursts"
      }
    },
    "shots": [
      {
        "shotId": "shot_01",
        "beatTag": "HOOK | SETUP | CATALYST | RISING | TURN | CLIMAX | FALLING | RESOLUTION",
        "startTime": "00:00:00.000",
        "endTime": "00:00:03.200",
        "durationSeconds": 3.2,
        "longTake": false,

        "concrete": {
          "firstFrameDescription": "CRITICAL for Imagen 4.0: Exact static composition of frame 1. Include: subject pose, facial expression, gaze direction (degrees from lens), hand positions, body orientation, background elements. (e.g., 'Young woman, mid-20s, seated at wooden cafe table, right hand supporting chin, gaze 45° left of lens, neutral expression with hint of melancholy, wearing navy cardigan over white blouse, rain-streaked window behind her, warm interior lighting')",

          "subject": "Full action description for Veo 3.1 motion. Include: character identity, physical state, intended motion trajectory, emotional undertone. (e.g., 'Woman slowly shifts gaze from window to coffee cup, slight shoulder droop conveying fatigue, fingers trace rim of ceramic mug')",

          "scene": "Environment with temporal and atmospheric detail. (e.g., 'Rainy late afternoon, small corner cafe interior, condensation on floor-to-ceiling windows, warm amber pendant lights contrast cool grey exterior, sparse patrons in soft focus background')",

          "camera": {
            "shotSize": "ECU | CU | MCU | MS | MLS | LS | ELS | POV | OTS",
            "cameraAngle": "Eye-level | Low-angle | High-angle | Dutch | Bird's-eye | Worm's-eye",
            "cameraMovement": "Static | Pan L/R | Tilt U/D | Dolly In/Out | Track L/R | Crane | Handheld | Steadicam | Zoom",
            "focalLengthDepth": "e.g., 85mm f/1.8, shallow DOF isolating subject, background bokeh"
          },

          "lighting": "Technical lighting setup. Include: key light source/direction, fill ratio, color temperature, practical lights, atmosphere. (e.g., 'Soft diffused window light from frame-left, 3:1 key-to-fill ratio, 4500K daylight balanced, warm 2700K practical pendant in background, volumetric haze from steam')",

          "dynamics": "Physics and secondary motion for Veo 3.1. (e.g., 'Steam rising from coffee cup with slow dissipation, rain droplets trickling down window glass, subtle fabric movement as subject breathes, background patrons in slow ambient motion')",

          "audio": {
            "soundDesign": "Ambient and SFX layers. (e.g., 'Cafe ambience -20dB, rain on glass -15dB, distant espresso machine, muted conversation walla')",
            "music": "Score description. (e.g., 'Soft piano melody enters at 00:00:02.000, single note sustain, melancholic minor key')",
            "dialogue": "Speaker and delivery. (e.g., 'No dialogue' OR 'Woman, internal monologue VO')",
            "dialogueText": "Exact transcription for lip-sync. (e.g., '' OR 'I used to believe that silence meant peace...')"
          },

          "style": "Rendering quality directives. (e.g., 'Cinematic 2.39:1 aspect, film grain 15%, slight desaturation -10%, subtle vignette, 4K resolution, anamorphic lens flare on highlights')",

          "negative": "CRITICAL exclusions for generation quality. Always include: 'blurry, out of focus (unless intentional), extra limbs, malformed hands, text overlays, watermarks, logos, cartoon style, anime, oversaturated colors, harsh shadows (unless specified), duplicate subjects'"
        },

        "abstract": {
          "narrativeFunction": "Story purpose. (e.g., 'Establish protagonist emotional state of quiet desperation and routine isolation')",
          "visualFunction": "Cinematic purpose. (e.g., 'Create audience empathy through intimate framing and environmental storytelling')",
          "subjectPlaceholder": "[PROTAGONIST_A] | [PROTAGONIST_B] | [ANTAGONIST] | [SUPPORTING_CHAR] | [ENVIRONMENT_ONLY]",
          "actionTemplate": "Reusable motion template. (e.g., '[PROTAGONIST_A] shifts gaze from [OBJECT_A] to [OBJECT_B], displaying [EMOTIONAL_STATE] through subtle body language')",
          "cameraPreserved": "COPY of concrete.camera (cinematography parameters are NEVER abstracted)"
        }
      }
    ]
  }
}

---

## 3. EXTRACTION GUIDELINES (Imagen 4.0 + Veo 3.1 Alignment)

### First Frame (Imagen 4.0 Critical)
- `firstFrameDescription` is the MOST IMPORTANT field
- Describe as if directing a photographer for a single still image
- Include: exact pose, facial micro-expression, gaze vector, hand positions, clothing state, prop positions
- Precision here determines video stability in Veo 3.1

### Motion & Gaze (Veo 3.1 Critical)
- In `subject`, describe the MOTION ARC from first frame to last frame of the shot
- Eye contact changes are especially important (e.g., "shifts gaze from 45° left to direct lens contact")
- Specify motion speed: "slowly", "suddenly", "gradually"

### Dialogue & Lip-Sync
- If dialogue exists, `dialogueText` MUST contain exact transcription
- Note emotional delivery in `audio.dialogue` (e.g., "whispered, trembling", "confident, measured")
- For non-dialogue shots, set `dialogueText` to empty string `""`

### Dynamics (Physics Simulation)
- Identify ALL secondary motions: hair, fabric, particles, liquids, smoke, reflections
- Veo 3.1 needs explicit physics cues for realistic animation
- Include environmental dynamics: background movement, light flicker, weather effects

### Negative Prompts (Quality Assurance)
- ALWAYS include baseline artifacts: `"blurry, extra limbs, malformed hands, text, watermark"`
- Add shot-specific exclusions based on content (e.g., for close-up: `"visible pores exaggerated, skin smoothing"`)
- For stylized content, exclude conflicting styles (e.g., `"photorealistic"` for animation)

---

## 4. BEAT TAGGING REFERENCE

| Beat Tag | Narrative Function | Typical Position |
|----------|-------------------|------------------|
| HOOK | Capture attention, establish intrigue | 0-10% |
| SETUP | Establish world, characters, status quo | 5-25% |
| CATALYST | Inciting incident, disruption | 20-30% |
| RISING | Escalating tension, complications | 30-50% |
| TURN | Major reversal, midpoint shift | 45-55% |
| CLIMAX | Peak conflict, maximum tension | 70-85% |
| FALLING | Consequences unfold | 80-90% |
| RESOLUTION | New equilibrium, closure | 85-100% |

---

## 5. DATA INTEGRITY CONSTRAINTS

- Output **ONLY pure JSON**. No markdown code blocks, no explanatory text.
- Every field in the schema **MUST** be present for every shot.
- If a technical value cannot be determined (e.g., exact focal length), provide a **"Cinematic Inference"** based on visual analysis (e.g., "Estimated 50mm based on compression and DOF").
- `dialogueText` must be empty string `""` if no dialogue, never `null` or omitted.
- `longTake` boolean is REQUIRED for all shots.

---

## 6. INPUT CONTENT TO ANALYZE

Analyze the provided video file:
{input_content}
"""


def convert_to_frontend_format(ai_output: dict) -> dict:
    """
    将 AI 输出的 concrete 层转换为前端 Storyboard 格式

    提取 globalSettings.concrete 和 shots[].concrete
    """
    recipe = ai_output.get("shotRecipe", ai_output)

    global_settings = recipe.get("globalSettings", {})
    global_concrete = global_settings.get("concrete", {})

    shots_raw = recipe.get("shots", [])
    shots_concrete = []

    for shot in shots_raw:
        concrete = shot.get("concrete", {})
        shot_data = {
            "shotId": shot.get("shotId"),
            "beatTag": shot.get("beatTag"),
            "startTime": shot.get("startTime"),
            "endTime": shot.get("endTime"),
            "durationSeconds": shot.get("durationSeconds"),
            "representativeTimestamp": shot.get("representativeTimestamp"),  # 🎯 AI 语义锚点
            "longTake": shot.get("longTake", False),
            # 8 核心字段
            "firstFrameDescription": concrete.get("firstFrameDescription", ""),
            "subject": concrete.get("subject", ""),
            "scene": concrete.get("scene", ""),
            "camera": concrete.get("camera", {}),
            "lighting": concrete.get("lighting", ""),
            "dynamics": concrete.get("dynamics", ""),
            "audio": concrete.get("audio", {}),
            "style": concrete.get("style", ""),
            "negative": concrete.get("negative", "")
        }
        shots_concrete.append(shot_data)

    return {
        "videoMetadata": recipe.get("videoMetadata", {}),
        "globalSettings": global_concrete,
        "shots": shots_concrete
    }


def extract_abstract_layer(ai_output: dict) -> dict:
    """
    提取 AI 输出的 abstract 层，作为隐形模板存储

    用于后续 Remix 阶段的意图注入
    """
    recipe = ai_output.get("shotRecipe", ai_output)

    global_settings = recipe.get("globalSettings", {})
    global_abstract = global_settings.get("abstract", {})

    shots_raw = recipe.get("shots", [])
    shots_abstract = []

    for shot in shots_raw:
        abstract = shot.get("abstract", {})
        shot_data = {
            "shotId": shot.get("shotId"),
            "beatTag": shot.get("beatTag"),
            "startTime": shot.get("startTime"),
            "endTime": shot.get("endTime"),
            "durationSeconds": shot.get("durationSeconds"),
            # Abstract 字段
            "narrativeFunction": abstract.get("narrativeFunction", ""),
            "visualFunction": abstract.get("visualFunction", ""),
            "subjectPlaceholder": abstract.get("subjectPlaceholder", ""),
            "actionTemplate": abstract.get("actionTemplate", ""),
            "cameraPreserved": abstract.get("cameraPreserved", {})
        }
        shots_abstract.append(shot_data)

    return {
        "globalSettings": global_abstract,
        "shotFunctions": shots_abstract
    }


def extract_first_frames(ai_output: dict) -> List[dict]:
    """
    提取所有镜头的首帧描述，用于 Imagen 4.0 批量生成

    Returns:
        List of {shotId, firstFrameDescription, camera, lighting, style, negative}
    """
    recipe = ai_output.get("shotRecipe", ai_output)
    shots_raw = recipe.get("shots", [])

    first_frames = []
    for shot in shots_raw:
        concrete = shot.get("concrete", {})
        first_frames.append({
            "shotId": shot.get("shotId"),
            "firstFrameDescription": concrete.get("firstFrameDescription", ""),
            "camera": concrete.get("camera", {}),
            "lighting": concrete.get("lighting", ""),
            "style": concrete.get("style", ""),
            "negative": concrete.get("negative", "")
        })

    return first_frames


def extract_dialogue_timeline(ai_output: dict) -> List[dict]:
    """
    提取对白时间线，用于 Lip-sync 处理

    Returns:
        List of {shotId, startTime, endTime, dialogueText, dialogueDelivery}
        (仅包含有对白的镜头)
    """
    recipe = ai_output.get("shotRecipe", ai_output)
    shots_raw = recipe.get("shots", [])

    dialogue_timeline = []
    for shot in shots_raw:
        concrete = shot.get("concrete", {})
        audio = concrete.get("audio", {})
        dialogue_text = audio.get("dialogueText", "")

        if dialogue_text and dialogue_text.strip():
            dialogue_timeline.append({
                "shotId": shot.get("shotId"),
                "startTime": shot.get("startTime"),
                "endTime": shot.get("endTime"),
                "durationSeconds": shot.get("durationSeconds"),
                "dialogueText": dialogue_text,
                "dialogueDelivery": audio.get("dialogue", "")
            })

    return dialogue_timeline


# ============================================================
# Two-Phase Shot Analysis (避免 JSON 截断)
# ============================================================

SHOT_DETECTION_PROMPT = """
# Prompt: Lightweight Shot Detection (Phase 1)

**Role**: Video Editor performing shot boundary detection.

**Task**: Identify all shot boundaries in the video and extract basic metadata ONLY.
Do NOT provide detailed descriptions - those will be extracted in Phase 2.

## ⚠️ CRITICAL CALIBRATION WARNING ⚠️
Internal testing shows your timestamp detection for scene cuts is consistently **1.0-1.5 seconds EARLIER** than the actual visual change.
To compensate: When outputting `representativeTimestamp`, you MUST manually **ADD 1.0 seconds** to your initial visual estimate to ensure the captured frame belongs to the CORRECT shot.

## Output Requirements
- **CRITICAL**: Keep JSON compact. Only include fields specified below.
- Maximum 30 shots per video
- If cuts exceed 30, merge adjacent shots sharing same subject/scene

## Representative Timestamp (CRITICAL - READ CAREFULLY)
For each shot, you MUST provide a `representativeTimestamp` (in seconds as a decimal number).

This must be the exact second where the new scene is **100% VISUALLY ESTABLISHED**.

**RULES:**
1. **DO NOT pick a point near the start boundary**. If you detect a cut at 1.4s but the previous scene is still fading out, you MUST pick a timestamp at least 1.0s AFTER your detected start time.
2. **Look for "Peak Stability"**: The moment where the subject is fully in frame and motion blur is minimal.
3. **FOR SHORT SHOTS (duration < 2 seconds)**: Set `representativeTimestamp` to exactly `endTime - 0.2`. This is the ONLY way to ensure the scene transition has completed for fast-cut videos.
4. **FOR NORMAL SHOTS (duration >= 2 seconds)**: Pick a timestamp in the 70-90% range of the shot duration.

Example: If you describe "A choir singing" for a shot from 3.14s to 4.27s (duration 1.13s < 2s), use `representativeTimestamp: 4.07` (which is endTime - 0.2)

## Output Format (Strict JSON)

{
  "shotRecipe": {
    "videoMetadata": {
      "totalDuration": "00:01:23.456",
      "totalShots": 18,
      "averageShotDuration": 4.6
    },
    "globalSettings": {
      "concrete": {
        "visualStyle": "Brief visual style description",
        "colorPalette": "Primary colors observed",
        "lightingDesign": "General lighting approach"
      },
      "abstract": {
        "styleCategory": "REALISTIC | STYLIZED | HYBRID",
        "moodBoardTags": ["tag1", "tag2", "tag3"]
      }
    },
    "shots": [
      {
        "shotId": "shot_01",
        "beatTag": "HOOK | SETUP | CATALYST | RISING | TURN | CLIMAX | FALLING | RESOLUTION",
        "startTime": "00:00:00.000",
        "endTime": "00:00:03.200",
        "durationSeconds": 3.2,
        "representativeTimestamp": 2.1,
        "longTake": false,
        "briefSubject": "One-line subject description (10 words max)",
        "briefScene": "One-line scene description (10 words max)"
      }
    ]
  }
}

Output ONLY valid JSON. No markdown, no explanation.

Analyze: {input_content}
"""


SHOT_DETAIL_BATCH_PROMPT = """
# Prompt: Shot Detail Extraction (Phase 2 - Batch)

**Role**: Master Cinematographer extracting detailed shot parameters.

**Task**: For the shots listed below, provide FULL concrete and abstract details.
You are analyzing shots {batch_start} to {batch_end} of {total_shots} total.

## Shots to Analyze
{shot_boundaries}

## Output Format (Strict JSON)

{
  "batchInfo": {
    "batchStart": {batch_start},
    "batchEnd": {batch_end},
    "processedCount": N
  },
  "shots": [
    {
      "shotId": "shot_XX",
      "concrete": {
        "firstFrameDescription": "CRITICAL: 50-80 word exact static composition of frame 1. Include: subject pose, facial expression, gaze direction, hand positions, body orientation, background elements, clothing details.",

        "subject": "Full action description for motion. Include: character identity, physical state, intended motion trajectory, emotional undertone. (30-50 words)",

        "scene": "Environment with temporal and atmospheric detail. (20-40 words)",

        "camera": {
          "shotSize": "ECU | CU | MCU | MS | MLS | LS | ELS | POV | OTS",
          "cameraAngle": "Eye-level | Low-angle | High-angle | Dutch | Bird's-eye | Worm's-eye",
          "cameraMovement": "Static | Pan L/R | Tilt U/D | Dolly In/Out | Track L/R | Crane | Handheld | Steadicam | Zoom",
          "focalLengthDepth": "e.g., 85mm f/1.8, shallow DOF"
        },

        "lighting": "Technical lighting setup. (15-30 words)",

        "dynamics": "Physics and secondary motion. (15-30 words)",

        "audio": {
          "soundDesign": "Ambient and SFX layers",
          "music": "Score description",
          "dialogue": "Speaker and delivery",
          "dialogueText": "Exact transcription or empty string"
        },

        "style": "Rendering quality directives (15-25 words)",

        "negative": "blurry, extra limbs, malformed hands, text, watermark, [add shot-specific exclusions]"
      },
      "abstract": {
        "narrativeFunction": "Story purpose (10-20 words)",
        "visualFunction": "Cinematic purpose (10-20 words)",
        "subjectPlaceholder": "[PROTAGONIST_A] | [PROTAGONIST_B] | [ANTAGONIST] | [SUPPORTING_CHAR] | [ENVIRONMENT_ONLY]",
        "actionTemplate": "Reusable motion template",
        "cameraPreserved": "COPY of concrete.camera"
      }
    }
  ]
}

Output ONLY valid JSON. No markdown, no explanation.

Analyze the video focusing on the specified shots: {input_content}
"""


def create_shot_boundaries_text(shots_basic: List[dict], start_idx: int, end_idx: int) -> str:
    """
    创建批次 shot 边界描述文本

    Args:
        shots_basic: Phase 1 返回的基础 shot 列表
        start_idx: 批次起始索引 (0-based)
        end_idx: 批次结束索引 (exclusive)

    Returns:
        格式化的 shot 边界文本
    """
    lines = []
    for shot in shots_basic[start_idx:end_idx]:
        shot_id = shot.get("shotId", "unknown")
        start_time = shot.get("startTime", "00:00:00.000")
        end_time = shot.get("endTime", "00:00:00.000")
        duration = shot.get("durationSeconds", 0)
        brief_subject = shot.get("briefSubject", "")
        brief_scene = shot.get("briefScene", "")

        lines.append(f"- {shot_id}: {start_time} → {end_time} ({duration}s)")
        lines.append(f"  Subject: {brief_subject}")
        lines.append(f"  Scene: {brief_scene}")
        lines.append("")

    return "\n".join(lines)


def merge_batch_results(
    phase1_result: Dict[str, Any],
    batch_results: List[Dict[str, Any]],
    degraded_batches: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    合并 Phase 1 基础数据和 Phase 2 批次详情

    Args:
        phase1_result: Phase 1 返回的基础结构
        batch_results: 成功的批次结果列表
        degraded_batches: 降级的批次信息

    Returns:
        完整的 shot recipe 结构
    """
    recipe = phase1_result.get("shotRecipe", phase1_result)
    shots_basic = recipe.get("shots", [])

    # 创建 shotId -> detailed_shot 映射
    detailed_shots_map = {}
    for batch in batch_results:
        for shot in batch.get("shots", []):
            shot_id = shot.get("shotId")
            if shot_id:
                detailed_shots_map[shot_id] = shot

    # 合并结果
    merged_shots = []
    for basic_shot in shots_basic:
        shot_id = basic_shot.get("shotId")

        if shot_id in detailed_shots_map:
            # 使用详细数据
            detailed = detailed_shots_map[shot_id]
            merged_shot = {
                "shotId": shot_id,
                "beatTag": basic_shot.get("beatTag"),
                "startTime": basic_shot.get("startTime"),
                "endTime": basic_shot.get("endTime"),
                "durationSeconds": basic_shot.get("durationSeconds"),
                "representativeTimestamp": basic_shot.get("representativeTimestamp"),  # 🎯 AI 语义锚点
                "longTake": basic_shot.get("longTake", False),
                "concrete": detailed.get("concrete", {}),
                "abstract": detailed.get("abstract", {}),
                "_degraded": False
            }
        else:
            # 使用降级数据 (Phase 1 基础信息)
            merged_shot = {
                "shotId": shot_id,
                "beatTag": basic_shot.get("beatTag"),
                "startTime": basic_shot.get("startTime"),
                "endTime": basic_shot.get("endTime"),
                "durationSeconds": basic_shot.get("durationSeconds"),
                "representativeTimestamp": basic_shot.get("representativeTimestamp"),  # 🎯 AI 语义锚点
                "longTake": basic_shot.get("longTake", False),
                "concrete": {
                    "firstFrameDescription": basic_shot.get("briefSubject", ""),
                    "subject": basic_shot.get("briefSubject", ""),
                    "scene": basic_shot.get("briefScene", ""),
                    "camera": {},
                    "lighting": "",
                    "dynamics": "",
                    "audio": {"soundDesign": "", "music": "", "dialogue": "", "dialogueText": ""},
                    "style": "",
                    "negative": "blurry, extra limbs, malformed hands, text, watermark"
                },
                "abstract": {
                    "narrativeFunction": "",
                    "visualFunction": "",
                    "subjectPlaceholder": "[SUBJECT]",
                    "actionTemplate": "",
                    "cameraPreserved": {}
                },
                "_degraded": True
            }

        merged_shots.append(merged_shot)

    # 构建最终结果
    result = {
        "shotRecipe": {
            "videoMetadata": recipe.get("videoMetadata", {}),
            "globalSettings": recipe.get("globalSettings", {}),
            "shots": merged_shots,
            "_analysisMetadata": {
                "twoPhaseAnalysis": True,
                "totalShots": len(merged_shots),
                "degradedShots": sum(1 for s in merged_shots if s.get("_degraded")),
                "degradedBatches": degraded_batches
            }
        }
    }

    return result
