# core/film_ir_manager.py
"""
Film IR Manager
===============
电影逻辑中间层管理器，负责：
1. 阶段流转控制
2. 支柱数据管理
3. 抽象化与意图注入调度

三阶段流程:
- Stage 1: Specific Analysis (具体分析)
- Stage 2: Abstraction (逻辑抽象)
- Stage 3: Intent Injection (意图注入)
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from google import genai
from google.genai import types


def gemini_call_with_retry(client, model: str, contents: list, config=None, max_retries: int = 2, base_delay: float = 5.0):
    """
    带重试和自动降级的 Gemini API 调用

    策略：
    1. 使用指定模型重试 max_retries 次
    2. 如果仍然失败，自动降级到 gemini-2.0-flash

    Args:
        client: Gemini 客户端
        model: 模型名称
        contents: 请求内容
        config: 生成配置
        max_retries: 最大重试次数（默认2次）
        base_delay: 基础等待时间（秒）

    Returns:
        Gemini 响应
    """
    # 降级模型映射
    fallback_model = "gemini-2.0-flash" if "3" in model else None

    last_error = None
    current_model = model

    # 第一轮：使用原始模型重试
    for attempt in range(max_retries + 1):
        try:
            if config:
                response = client.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=config
                )
            else:
                response = client.models.generate_content(
                    model=current_model,
                    contents=contents
                )
            return response
        except Exception as e:
            error_str = str(e)
            last_error = e

            # 检查是否是可重试的错误 (503 过载, 429 限流)
            if "503" in error_str or "overloaded" in error_str.lower() or "429" in error_str:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # 指数退避: 5s, 10s
                    print(f"   ⏳ {current_model} overloaded, retrying in {delay:.0f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # 重试次数用完，尝试降级
                    break
            else:
                # 其他错误直接抛出
                raise

    # 第二轮：降级到备用模型
    if fallback_model and fallback_model != model:
        print(f"   🔄 Falling back to {fallback_model}...")
        try:
            if config:
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=contents,
                    config=config
                )
            else:
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=contents
                )
            print(f"   ✅ Fallback to {fallback_model} succeeded")
            return response
        except Exception as e:
            print(f"   ❌ Fallback also failed: {e}")
            # 降级也失败，抛出原始错误
            raise last_error

    # 无法降级，抛出原始错误
    raise last_error

from core.film_ir_schema import create_empty_film_ir, StageStatus
from core.film_ir_io import (
    load_film_ir, save_film_ir, film_ir_exists,
    update_film_ir_stage, update_film_ir_pillar,
    set_user_intent, get_hidden_template, get_active_layer,
    convert_to_frontend_story_theme,
    convert_to_frontend_script_analysis,
    convert_to_frontend_storyboard
)
from core.meta_prompts import (
    # Pillar I-III Analysis
    STORY_THEME_ANALYSIS_PROMPT,
    convert_story_theme_to_frontend,
    extract_story_theme_abstract,
    NARRATIVE_EXTRACTION_PROMPT,
    convert_narrative_to_frontend,
    extract_narrative_abstract,
    extract_narrative_hidden_assets,
    SHOT_DECOMPOSITION_PROMPT,
    SHOT_DETECTION_PROMPT,
    SHOT_DETAIL_BATCH_PROMPT,
    convert_shot_recipe_to_frontend,
    extract_shot_recipe_abstract,
    extract_shot_first_frames,
    extract_shot_dialogue_timeline,
    create_shot_boundaries_text,
    merge_batch_results,
    # Character Ledger (Pillar II extension) - Split prompts for better extraction
    CHARACTER_EXTRACTION_PROMPT,
    ENVIRONMENT_EXTRACTION_PROMPT,
    build_shot_subjects_input,
    process_ledger_result,
    get_ledger_display_summary,
    update_shots_with_entity_refs,
    # M4: Intent Injection
    INTENT_PARSER_PROMPT,
    parse_intent_result,
    extract_subject_mappings,
    get_intent_summary,
    check_compliance,
    INTENT_FUSION_PROMPT,
    convert_to_remixed_layer,
    extract_identity_anchors,
    extract_t2i_prompts,
    extract_i2v_prompts,
    validate_fusion_output,
    generate_fusion_summary,
    post_process_remixed_layer
)


class FilmIRManager:
    """
    Film IR 管理器

    Usage:
        manager = FilmIRManager(job_id, project_root)
        manager.run_stage("specificAnalysis")
        manager.run_stage("abstraction")
        manager.inject_intent("把猫换成霸王龙")
        manager.run_stage("assetGeneration")
    """

    def __init__(self, job_id: str, project_root: Optional[Path] = None):
        """
        初始化 Film IR Manager

        Args:
            job_id: 作业 ID
            project_root: 项目根目录
        """
        self.project_dir = project_root or Path(__file__).parent.parent
        self.job_id = job_id
        self.job_dir = self.project_dir / "jobs" / job_id

        # 加载或创建 Film IR
        if film_ir_exists(self.job_dir):
            self.ir = load_film_ir(self.job_dir)
        else:
            self.ir = create_empty_film_ir(job_id)

    # ============================================================
    # 属性访问
    # ============================================================

    @property
    def stages(self) -> Dict[str, str]:
        """获取阶段状态"""
        return self.ir.get("stages", {})

    @property
    def pillars(self) -> Dict[str, Any]:
        """获取四大支柱"""
        return self.ir.get("pillars", {})

    @property
    def user_intent(self) -> Dict[str, Any]:
        """获取用户意图"""
        return self.ir.get("userIntent", {})

    @property
    def source_video(self) -> str:
        """获取源视频路径"""
        return self.ir.get("sourceVideo", "")

    # ============================================================
    # 持久化
    # ============================================================

    def save(self) -> None:
        """保存 Film IR"""
        save_film_ir(self.job_dir, self.ir)

    def reload(self) -> None:
        """重新加载 Film IR"""
        self.ir = load_film_ir(self.job_dir)

    # ============================================================
    # 阶段控制
    # ============================================================

    def update_stage(self, stage: str, status: str) -> None:
        """
        更新阶段状态

        Args:
            stage: 阶段名
            status: 状态 (NOT_STARTED/RUNNING/SUCCESS/FAILED)
        """
        if stage in self.ir["stages"]:
            self.ir["stages"][stage] = status
            self.save()
        else:
            raise ValueError(f"Unknown stage: {stage}")

    def can_run_stage(self, stage: str) -> tuple:
        """
        检查是否可以运行指定阶段

        Returns:
            (can_run: bool, reason: str)
        """
        stages = self.stages

        dependencies = {
            "specificAnalysis": [],
            "abstraction": ["specificAnalysis"],
            # intentInjection 依赖 specificAnalysis (已包含 abstract 提取)
            # 跳过 abstraction placeholder，直接从 specificAnalysis 获取 abstract 数据
            "intentInjection": ["specificAnalysis"],
            "assetGeneration": ["intentInjection"],
            "shotRefinement": ["assetGeneration"],
            "execution": ["shotRefinement"]
        }

        if stage not in dependencies:
            return False, f"Unknown stage: {stage}"

        # 检查前置依赖
        for dep in dependencies[stage]:
            if stages.get(dep) != "SUCCESS":
                return False, f"Dependency not met: {dep} must be SUCCESS"

        # 特殊检查：意图注入需要用户输入
        if stage == "intentInjection":
            if not self.user_intent.get("rawPrompt"):
                return False, "User intent not provided"

        return True, "OK"

    def run_stage(self, stage: str) -> Dict[str, Any]:
        """
        运行指定阶段

        Args:
            stage: 阶段名

        Returns:
            运行结果
        """
        can_run, reason = self.can_run_stage(stage)
        if not can_run:
            return {"status": "error", "reason": reason}

        self.update_stage(stage, "RUNNING")

        try:
            if stage == "specificAnalysis":
                result = self._run_specific_analysis()
            elif stage == "abstraction":
                result = self._run_abstraction()
            elif stage == "intentInjection":
                result = self._run_intent_injection()
            elif stage == "assetGeneration":
                result = self._run_asset_generation()
            elif stage == "shotRefinement":
                result = self._run_shot_refinement()
            elif stage == "execution":
                result = self._run_execution()
            else:
                result = {"status": "error", "reason": f"Unknown stage: {stage}"}

            if result.get("status") == "success":
                self.update_stage(stage, "SUCCESS")
            else:
                self.update_stage(stage, "FAILED")

            return result

        except Exception as e:
            self.update_stage(stage, "FAILED")
            print(f"❌ Stage {stage} failed: {e}")
            return {"status": "error", "reason": str(e)}

    # ============================================================
    # 阶段实现 (预留接口，等待 Meta Prompts)
    # ============================================================

    def _run_specific_analysis(self) -> Dict[str, Any]:
        """
        阶段 1: 具体分析
        调用 Meta Prompts 提取四大支柱的 concrete 数据

        优化: 视频只上传一次，三个分析复用同一个文件引用
        """
        print(f"🔍 [Stage 1] Running specific analysis for {self.job_id}...")

        # 获取视频路径
        video_path = self.job_dir / self.source_video
        if not video_path.exists():
            return {"status": "error", "reason": f"Video file not found: {video_path}"}

        # ============================================================
        # 🚀 统一上传视频 (只上传一次，三个分析复用)
        # ============================================================
        print(f"📤 [Stage 1.0] Uploading video to Gemini (once for all analyses)...")
        try:
            uploaded_file, client = self._upload_video_to_gemini(video_path)
            print(f"✅ [Stage 1.0] Video uploaded and ready: {uploaded_file.name}")
        except Exception as e:
            print(f"❌ [Stage 1.0] Video upload failed: {e}")
            return {"status": "error", "reason": f"Video upload failed: {e}"}

        # ============================================================
        # Step 1: Story Theme Analysis (支柱 I) - Concrete + Abstract 融合输出
        # ============================================================
        print(f"📊 [Stage 1.1] Analyzing Story Theme...")

        try:
            story_theme_result = self._analyze_story_theme(uploaded_file, client)
            if story_theme_result:
                # 提取双层数据
                concrete_data = convert_story_theme_to_frontend(story_theme_result)
                abstract_data = extract_story_theme_abstract(story_theme_result)

                # 存储到支柱 I
                self.ir["pillars"]["I_storyTheme"]["concrete"] = concrete_data
                self.ir["pillars"]["I_storyTheme"]["abstract"] = abstract_data
                self.save()
                print(f"✅ [Stage 1.1] Story Theme analysis completed (concrete + abstract)")
            else:
                print(f"⚠️ [Stage 1.1] Story Theme analysis returned empty result")
        except Exception as e:
            print(f"❌ [Stage 1.1] Story Theme analysis failed: {e}")
            return {"status": "error", "reason": f"Story Theme analysis failed: {e}"}

        # ============================================================
        # Step 2: Narrative Extraction (支柱 II) - Concrete + Abstract 融合输出
        # ============================================================
        print(f"📝 [Stage 1.2] Extracting Narrative Template...")

        try:
            narrative_result = self._analyze_narrative(uploaded_file, client)
            if narrative_result:
                # 提取三层数据
                concrete_data = convert_narrative_to_frontend(narrative_result)
                abstract_data = extract_narrative_abstract(narrative_result)
                hidden_assets = extract_narrative_hidden_assets(narrative_result)

                # 存储到支柱 II
                self.ir["pillars"]["II_narrativeTemplate"]["concrete"] = concrete_data
                self.ir["pillars"]["II_narrativeTemplate"]["abstract"] = abstract_data
                self.ir["pillars"]["II_narrativeTemplate"]["hiddenAssets"] = hidden_assets
                self.save()
                print(f"✅ [Stage 1.2] Narrative extraction completed (concrete + abstract + hiddenAssets)")
            else:
                print(f"⚠️ [Stage 1.2] Narrative extraction returned empty result")
        except Exception as e:
            print(f"❌ [Stage 1.2] Narrative extraction failed: {e}")
            # 不阻塞流程，继续执行

        # ============================================================
        # Step 3: Shot Decomposition (支柱 III) - Concrete + Abstract 融合输出
        # ============================================================
        print(f"🎬 [Stage 1.3] Decomposing Shot Recipe...")

        try:
            shot_recipe_result = self._analyze_shot_recipe(uploaded_file, client)
            if shot_recipe_result:
                # 提取多层数据
                concrete_data = convert_shot_recipe_to_frontend(shot_recipe_result)
                abstract_data = extract_shot_recipe_abstract(shot_recipe_result)
                first_frames = extract_shot_first_frames(shot_recipe_result)
                dialogue_timeline = extract_shot_dialogue_timeline(shot_recipe_result)

                # 提取分析元数据 (包含降级信息)
                analysis_metadata = shot_recipe_result.get("shotRecipe", {}).get("_analysisMetadata", {})
                degraded_batches = analysis_metadata.get("degradedBatches", [])

                # 存储到支柱 III
                self.ir["pillars"]["III_shotRecipe"]["concrete"] = concrete_data
                self.ir["pillars"]["III_shotRecipe"]["abstract"] = abstract_data
                # 附加数据存储到 metadata
                self.ir["pillars"]["III_shotRecipe"]["firstFrames"] = first_frames
                self.ir["pillars"]["III_shotRecipe"]["dialogueTimeline"] = dialogue_timeline
                # 存储降级批次信息 (用于重试)
                self.ir["pillars"]["III_shotRecipe"]["_analysisMetadata"] = analysis_metadata

                self.save()

                # 输出分析结果摘要
                total_shots = len(concrete_data.get('shots', []))
                degraded_count = analysis_metadata.get("degradedShots", 0)
                if degraded_count > 0:
                    print(f"⚠️ [Stage 1.3] Shot Recipe completed: {total_shots} shots ({degraded_count} degraded, can retry)")
                else:
                    print(f"✅ [Stage 1.3] Shot Recipe completed ({total_shots} shots extracted)")
            else:
                print(f"⚠️ [Stage 1.3] Shot Recipe returned empty result")
        except Exception as e:
            print(f"❌ [Stage 1.3] Shot Recipe analysis failed: {e}")
            import traceback
            traceback.print_exc()
            # 不阻塞流程

        # ============================================================
        # Step 4: Character Ledger Generation (支柱 II 扩展) - 两阶段识别
        # ============================================================
        print(f"👥 [Stage 1.4] Generating Character Ledger (two-phase clustering)...")

        try:
            # 获取已分析的 shots 数据
            shots = self.ir["pillars"]["III_shotRecipe"]["concrete"].get("shots", [])
            if shots:
                ledger_result = self._generate_character_ledger(shots, client)
                if ledger_result:
                    # 存储 character ledger 到 Pillar II
                    self.ir["pillars"]["II_narrativeTemplate"]["characterLedger"] = ledger_result.get("characterLedger", [])
                    self.ir["pillars"]["II_narrativeTemplate"]["environmentLedger"] = ledger_result.get("environmentLedger", [])
                    self.ir["pillars"]["II_narrativeTemplate"]["ledgerSummary"] = ledger_result.get("clusteringSummary", {})

                    # 更新 Pillar III shots，添加 entityRefs
                    updated_shots = update_shots_with_entity_refs(shots, ledger_result)
                    self.ir["pillars"]["III_shotRecipe"]["concrete"]["shots"] = updated_shots

                    # 初始化 Pillar IV 的 identityMapping (空映射，待用户绑定)
                    self._init_identity_mapping(ledger_result)

                    self.save()
                    print(f"✅ [Stage 1.4] Character Ledger completed:")
                    print(get_ledger_display_summary(ledger_result))
                else:
                    print(f"⚠️ [Stage 1.4] Character Ledger generation returned empty result")
            else:
                print(f"⚠️ [Stage 1.4] Skipped - no shots available for clustering")
        except Exception as e:
            print(f"❌ [Stage 1.4] Character Ledger generation failed: {e}")
            import traceback
            traceback.print_exc()
            # 不阻塞流程

        return {"status": "success", "message": "Specific analysis completed"}

    def _upload_video_to_gemini(self, video_path: Path) -> tuple:
        """
        统一上传视频到 Gemini Files API

        Args:
            video_path: 视频文件路径

        Returns:
            (uploaded_file, client) 元组，供后续分析复用
        """
        import time

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())

        client = genai.Client(api_key=api_key)

        # 上传视频文件
        uploaded_file = client.files.upload(file=str(video_path))

        # 等待文件处理完成
        while uploaded_file.state.name == "PROCESSING":
            print(f"⏳ Waiting for video processing...")
            time.sleep(3)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            raise RuntimeError(f"Video processing failed: {uploaded_file.state.name}")

        return uploaded_file, client

    def _analyze_story_theme(self, uploaded_file, client) -> Optional[Dict[str, Any]]:
        """
        调用 Gemini API 分析视频主题

        Args:
            uploaded_file: 已上传的 Gemini 文件引用
            client: Gemini 客户端实例

        Returns:
            AI 分析结果 (原始格式)
        """
        # 构建 Prompt (替换 {input_content} 占位符)
        prompt = STORY_THEME_ANALYSIS_PROMPT.replace(
            "{input_content}",
            "[Video file attached - analyze the visual and audio content]"
        )

        # 调用 Gemini API (带 503 重试)
        print(f"🤖 Calling Gemini API for Story Theme analysis...")
        response = gemini_call_with_retry(
            client=client,
            model="gemini-3-flash-preview",
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 解析 JSON 响应 - 使用增强的解析器处理转义序列等问题
        result = self._parse_json_response(response.text, "Story Theme")
        print(f"✅ Story Theme analysis received")
        return result

    def _analyze_narrative(self, uploaded_file, client) -> Optional[Dict[str, Any]]:
        """
        调用 Gemini API 提取叙事模板 (Concrete + Abstract 融合输出)

        Args:
            uploaded_file: 已上传的 Gemini 文件引用
            client: Gemini 客户端实例

        Returns:
            AI 分析结果，包含 narrativeTemplate.*.concrete 和 *.abstract
        """
        # 构建 Prompt
        prompt = NARRATIVE_EXTRACTION_PROMPT.replace(
            "{input_content}",
            "[Video file attached - analyze the narrative structure, characters, and story arc]"
        )

        # 调用 Gemini API (带 503 重试)
        print(f"🤖 Calling Gemini API for Narrative extraction...")
        response = gemini_call_with_retry(
            client=client,
            model="gemini-3-flash-preview",
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 解析 JSON 响应 - 使用增强的解析器处理转义序列等问题
        result = self._parse_json_response(response.text, "Narrative")
        print(f"✅ Narrative extraction received")
        return result

    def _analyze_shot_recipe(self, uploaded_file, client, batch_size: int = 8) -> Optional[Dict[str, Any]]:
        """
        两阶段分批分析分镜 (避免 JSON 截断)

        Phase 1: 轻量级 shot 检测 (获取边界和基础 metadata)
        Phase 2: 分批提取详细 concrete/abstract 字段

        Args:
            uploaded_file: 已上传的 Gemini 文件引用
            client: Gemini 客户端实例
            batch_size: 每批处理的 shot 数量 (默认 8)

        Returns:
            合并后的 AI 分析结果，包含 shotRecipe.globalSettings 和 shots[]
            失败的批次会使用降级数据，并记录在 _analysisMetadata.degradedBatches
        """
        import time

        # ============================================================
        # Phase 1: 轻量级 Shot 检测
        # ============================================================
        print(f"🔍 [Phase 1] Lightweight shot detection...")

        phase1_prompt = SHOT_DETECTION_PROMPT.replace(
            "{input_content}",
            "[Video file attached - detect shot boundaries and extract basic metadata]"
        )

        response = gemini_call_with_retry(
            client=client,
            model="gemini-3-flash-preview",
            contents=[phase1_prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 使用增强的解析器处理转义序列等问题
        phase1_result = self._parse_json_response(response.text, "Shot Phase 1")
        shots_basic = phase1_result.get("shotRecipe", {}).get("shots", [])
        total_shots = len(shots_basic)
        print(f"✅ [Phase 1] Detected {total_shots} shots")

        if total_shots == 0:
            print(f"⚠️ No shots detected, returning Phase 1 result as-is")
            return phase1_result

        # ============================================================
        # Phase 2: 分批提取详情
        # ============================================================
        batch_results = []
        degraded_batches = []
        num_batches = (total_shots + batch_size - 1) // batch_size

        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, total_shots)

            print(f"📦 [Phase 2] Processing batch {batch_idx + 1}/{num_batches} (shots {start_idx + 1}-{end_idx})...")

            # 构建批次 prompt
            shot_boundaries = create_shot_boundaries_text(shots_basic, start_idx, end_idx)
            batch_prompt = SHOT_DETAIL_BATCH_PROMPT.replace(
                "{batch_start}", str(start_idx + 1)
            ).replace(
                "{batch_end}", str(end_idx)
            ).replace(
                "{total_shots}", str(total_shots)
            ).replace(
                "{shot_boundaries}", shot_boundaries
            ).replace(
                "{input_content}",
                "[Video file attached - extract detailed parameters for specified shots]"
            )

            # 调用 API (带 503 重试 + JSON 解析重试)
            batch_success = False
            batch_result = self._process_batch_with_fallback(
                client=client,
                uploaded_file=uploaded_file,
                batch_prompt=batch_prompt,
                shots_basic=shots_basic,
                start_idx=start_idx,
                end_idx=end_idx,
                batch_idx=batch_idx,
                total_shots=total_shots
            )

            if batch_result is not None:
                batch_results.append(batch_result)
                batch_success = True
                print(f"✅ [Phase 2] Batch {batch_idx + 1} completed")
            else:
                # 记录降级信息
                degraded_batch = {
                    "batchIndex": batch_idx,
                    "startIdx": start_idx,
                    "endIdx": end_idx,
                    "shotIds": [s.get("shotId") for s in shots_basic[start_idx:end_idx]],
                    "reason": "All retries and split attempts failed",
                    "timestamp": datetime.now().isoformat()
                }
                degraded_batches.append(degraded_batch)
                print(f"⚠️ [Phase 2] Batch {batch_idx + 1} DEGRADED - using Phase 1 data")

        # ============================================================
        # 合并结果
        # ============================================================
        merged_result = merge_batch_results(phase1_result, batch_results, degraded_batches)

        # 报告降级情况
        if degraded_batches:
            degraded_shot_count = sum(
                b["endIdx"] - b["startIdx"] for b in degraded_batches
            )
            print(f"⚠️ Shot Recipe completed with {len(degraded_batches)} degraded batch(es)")
            print(f"   {degraded_shot_count} shots using basic data (can be retried)")
        else:
            print(f"✅ Shot Recipe fully completed (all batches successful)")

        return merged_result

    def _try_fix_json(self, broken_json: str) -> Optional[dict]:
        """
        尝试修复截断的 JSON

        常见问题：
        1. JSON 在中间被截断，缺少闭合括号
        2. 最后一个元素不完整
        """
        import re

        text = broken_json.strip()

        # 如果已经是有效 JSON，直接返回
        try:
            return json.loads(text)
        except:
            pass

        # 尝试修复策略 1: 补全缺失的括号
        # 统计未闭合的括号
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        if open_braces > 0 or open_brackets > 0:
            # 删除最后一个不完整的元素（通常在逗号后面）
            # 找到最后一个完整的 } 或 ]
            last_complete_idx = max(text.rfind('}'), text.rfind(']'))
            if last_complete_idx > 0:
                text = text[:last_complete_idx + 1]

            # 重新计算
            open_braces = text.count('{') - text.count('}')
            open_brackets = text.count('[') - text.count(']')

            # 补全括号
            text += ']' * open_brackets + '}' * open_braces

            try:
                return json.loads(text)
            except:
                pass

        # 尝试修复策略 2: 提取 shots 数组
        shots_match = re.search(r'"shots"\s*:\s*\[', text)
        if shots_match:
            start_idx = shots_match.end() - 1  # 从 [ 开始
            # 找到所有完整的 shot 对象
            bracket_count = 0
            last_complete_shot_end = start_idx
            i = start_idx
            while i < len(text):
                if text[i] == '[':
                    bracket_count += 1
                elif text[i] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        last_complete_shot_end = i
                        break
                elif text[i] == '}' and bracket_count == 1:
                    # 可能是一个完整的 shot 对象结束
                    last_complete_shot_end = i
                i += 1

            if last_complete_shot_end > start_idx:
                shots_text = text[start_idx:last_complete_shot_end + 1]
                # 确保闭合
                if not shots_text.endswith(']'):
                    shots_text += ']'
                try:
                    shots = json.loads(shots_text)
                    return {"shots": shots}
                except:
                    pass

        return None

    def _process_batch_with_fallback(
        self,
        client,
        uploaded_file,
        batch_prompt: str,
        shots_basic: List[dict],
        start_idx: int,
        end_idx: int,
        batch_idx: int,
        total_shots: int
    ) -> Optional[dict]:
        """
        处理单个批次，带多层重试和拆分回退

        策略:
        1. 主批次重试 3 次
        2. 尝试 JSON 修复
        3. 如果仍失败且批次 > 4 个 shot，拆分成两半分别处理
        """
        max_retries = 3
        last_response_text = ""

        for retry in range(max_retries):
            try:
                # Rate limiting
                if batch_idx > 0 or retry > 0:
                    time.sleep(2)

                response = gemini_call_with_retry(
                    client=client,
                    model="gemini-3-flash-preview",
                    contents=[batch_prompt, uploaded_file],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                last_response_text = response.text
                batch_result = self._parse_json_response(response.text, f"Shot Batch {batch_idx + 1}")

                # Debug: 打印返回的数据结构
                if isinstance(batch_result, dict):
                    shots_in_batch = batch_result.get("shots", [])
                    if shots_in_batch and len(shots_in_batch) > 0:
                        first_shot = shots_in_batch[0]
                        has_concrete = "concrete" in first_shot
                        shot_keys = list(first_shot.keys())[:5]  # 只显示前5个键
                        print(f"   📋 Batch structure: {len(shots_in_batch)} shots, concrete_nested={has_concrete}, keys={shot_keys}")

                return batch_result

            except json.JSONDecodeError as e:
                print(f"⚠️ [Phase 2] Batch {batch_idx + 1} retry {retry + 1}/{max_retries}: JSON parse error")

                # 尝试修复 JSON
                if last_response_text:
                    fixed = self._try_fix_json(last_response_text)
                    if fixed:
                        print(f"   🔧 JSON repair successful")
                        return fixed

            except Exception as e:
                print(f"⚠️ [Phase 2] Batch {batch_idx + 1} retry {retry + 1}/{max_retries}: {e}")

        # 所有重试都失败了，尝试拆分批次
        batch_size = end_idx - start_idx
        if batch_size > 4:
            print(f"   🔀 Splitting batch {batch_idx + 1} into smaller chunks...")
            mid = start_idx + batch_size // 2

            # 处理前半部分
            first_half = self._process_single_split(
                client, uploaded_file, shots_basic, start_idx, mid, total_shots, "A"
            )

            # 处理后半部分
            second_half = self._process_single_split(
                client, uploaded_file, shots_basic, mid, end_idx, total_shots, "B"
            )

            # 合并结果
            if first_half or second_half:
                combined_shots = []
                if first_half:
                    combined_shots.extend(first_half.get("shots", []))
                if second_half:
                    combined_shots.extend(second_half.get("shots", []))

                if combined_shots:
                    print(f"   ✅ Split recovery: {len(combined_shots)} shots extracted")
                    return {"shots": combined_shots}

        return None

    def _process_single_split(
        self,
        client,
        uploaded_file,
        shots_basic: List[dict],
        start_idx: int,
        end_idx: int,
        total_shots: int,
        split_label: str
    ) -> Optional[dict]:
        """处理拆分后的小批次"""
        shot_boundaries = create_shot_boundaries_text(shots_basic, start_idx, end_idx)
        split_prompt = SHOT_DETAIL_BATCH_PROMPT.replace(
            "{batch_start}", str(start_idx + 1)
        ).replace(
            "{batch_end}", str(end_idx)
        ).replace(
            "{total_shots}", str(total_shots)
        ).replace(
            "{shot_boundaries}", shot_boundaries
        ).replace(
            "{input_content}",
            "[Video file attached - extract detailed parameters for specified shots]"
        )

        try:
            time.sleep(2)
            response = gemini_call_with_retry(
                client=client,
                model="gemini-3-flash-preview",
                contents=[split_prompt, uploaded_file],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            # 使用增强的解析器处理转义序列等问题
            result = self._parse_json_response(response.text, f"Shot Split {split_label}")
            print(f"      ✅ Split {split_label} completed ({start_idx + 1}-{end_idx})")
            return result

        except json.JSONDecodeError as e:
            print(f"      ❌ Split {split_label} JSON parse failed: {e}")
            return None

        except Exception as e:
            print(f"      ❌ Split {split_label} error: {e}")
            return None

    def _generate_character_ledger(
        self,
        shots: List[Dict[str, Any]],
        client
    ) -> Optional[Dict[str, Any]]:
        """
        分离式角色/环境识别：使用两个独立的专用提示词

        Step 1: 调用 CHARACTER_EXTRACTION_PROMPT 提取所有角色
        Step 2: 调用 ENVIRONMENT_EXTRACTION_PROMPT 提取所有环境
        Step 3: 合并结果

        Args:
            shots: Pillar III 的 concrete shots 列表
            client: Gemini 客户端实例

        Returns:
            处理后的 character ledger 数据
        """
        # 构建 shot subjects 输入
        print(f"📊 [Character Ledger] Input: {len(shots)} shots to analyze")
        shot_subjects_text = build_shot_subjects_input(shots)
        print(f"📝 [Character Ledger] Shot subjects text length: {len(shot_subjects_text)} chars")

        # 🔍 DEBUG: Print first and last shot to verify all shots are included
        if shots:
            print(f"   First shot: {shots[0].get('shotId')} - {shots[0].get('subject', 'N/A')[:50]}...")
            if len(shots) > 1:
                print(f"   Last shot: {shots[-1].get('shotId')} - {shots[-1].get('subject', 'N/A')[:50]}...")

        all_shot_ids = [shot.get("shotId") for shot in shots if shot.get("shotId")]

        # ============================================================
        # Step 1: 角色提取 (Character Extraction)
        # ============================================================
        char_prompt = CHARACTER_EXTRACTION_PROMPT.replace("{shot_subjects}", shot_subjects_text)
        print(f"🎭 [Step 1] Extracting characters...")

        char_response = gemini_call_with_retry(
            client=client,
            model="gemini-3-flash-preview",
            contents=[char_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1  # Low temperature for deterministic extraction
            )
        )

        try:
            char_result = json.loads(char_response.text)
            raw_chars = char_result.get("characters", [])
            print(f"   ✅ Found {len(raw_chars)} characters")

            # Log which shots are covered by characters
            char_shots = set()
            for c in raw_chars:
                char_shots.update(c.get("appearsInShots", []))
            print(f"   📊 Characters cover {len(char_shots)}/{len(all_shot_ids)} shots")

        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse characters JSON: {e}")
            print(f"   Raw response: {char_response.text[:300]}...")
            raw_chars = []

        # ============================================================
        # Step 2: 环境提取 (Environment Extraction)
        # ============================================================
        env_prompt = ENVIRONMENT_EXTRACTION_PROMPT.replace("{shot_subjects}", shot_subjects_text)
        print(f"🏠 [Step 2] Extracting environments...")

        env_response = gemini_call_with_retry(
            client=client,
            model="gemini-3-flash-preview",
            contents=[env_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1  # Low temperature for deterministic extraction
            )
        )

        try:
            env_result = json.loads(env_response.text)
            raw_envs = env_result.get("environments", [])
            print(f"   ✅ Found {len(raw_envs)} environments")

            # Log which shots are covered by environments
            env_shots = set()
            for e in raw_envs:
                env_shots.update(e.get("appearsInShots", []))
            print(f"   📊 Environments cover {len(env_shots)}/{len(all_shot_ids)} shots")

            # Check for missing shots
            missing = set(all_shot_ids) - env_shots
            if missing:
                print(f"   ⚠️ Missing shots: {sorted(missing)}")

        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse environments JSON: {e}")
            print(f"   Raw response: {env_response.text[:300]}...")
            raw_envs = []

        # ============================================================
        # Step 3: 合并结果并转换格式
        # ============================================================
        # Convert to legacy format for compatibility
        character_ledger = []
        for i, char in enumerate(raw_chars):
            character_ledger.append({
                "entityId": char.get("entityId", f"orig_char_{i+1:02d}"),
                "entityType": "CHARACTER",
                "importance": char.get("importance", "SECONDARY"),
                "displayName": char.get("displayName", "Unknown"),
                "visualSignature": char.get("visualDescription", "")[:100],
                "detailedDescription": char.get("visualDescription", ""),
                "appearsInShots": char.get("appearsInShots", []),
                "shotCount": len(char.get("appearsInShots", [])),
                "trackingConfidence": "HIGH",
                "visualCues": []
            })

        environment_ledger = []
        for i, env in enumerate(raw_envs):
            environment_ledger.append({
                "entityId": env.get("entityId", f"orig_env_{i+1:02d}"),
                "entityType": "ENVIRONMENT",
                "importance": env.get("importance", "SECONDARY"),
                "displayName": env.get("displayName", "Unknown"),
                "visualSignature": env.get("visualDescription", "")[:100],
                "detailedDescription": env.get("visualDescription", ""),
                "appearsInShots": env.get("appearsInShots", []),
                "shotCount": len(env.get("appearsInShots", []))
            })

        # Build combined result
        combined_result = {
            "clusteringSuccess": True,
            "characterLedger": character_ledger,
            "environmentLedger": environment_ledger,
            "clusteringSummary": {
                "totalCharacters": len(character_ledger),
                "primaryCharacters": len([c for c in character_ledger if c["importance"] == "PRIMARY"]),
                "secondaryCharacters": len([c for c in character_ledger if c["importance"] == "SECONDARY"]),
                "totalEnvironments": len(environment_ledger),
                "totalShots": len(all_shot_ids),
                "unclusteredShots": []
            }
        }

        print(f"✅ Character Ledger complete: {len(character_ledger)} characters, {len(environment_ledger)} environments")

        return process_ledger_result(combined_result, all_shot_ids)

    def _init_identity_mapping(self, ledger_result: Dict[str, Any]) -> None:
        """
        初始化 Pillar IV 的 identityMapping 矩阵

        为每个原片实体创建空的映射槽位，待用户后续绑定替换资产

        Args:
            ledger_result: character ledger 数据
        """
        identity_mapping = {}

        # 为每个角色创建映射槽位
        for char in ledger_result.get("characterLedger", []):
            entity_id = char.get("entityId")
            identity_mapping[entity_id] = {
                "entityType": "CHARACTER",
                "originalEntity": {
                    "entityId": entity_id,
                    "displayName": char.get("displayName"),
                    "visualSignature": char.get("visualSignature"),
                    "importance": char.get("importance"),
                    "appearsInShots": char.get("appearsInShots", [])
                },
                "remixedEntity": None,  # Phase 3: 由 Intent Injection 填充
                "boundAsset": None,  # 待绑定
                "bindingStatus": "UNBOUND",
                "bindingTimestamp": None,
                "isRemixed": False  # 标记是否已被 remix
            }

        # 为每个环境创建映射槽位
        for env in ledger_result.get("environmentLedger", []):
            entity_id = env.get("entityId")
            identity_mapping[entity_id] = {
                "entityType": "ENVIRONMENT",
                "originalEntity": {
                    "entityId": entity_id,
                    "displayName": env.get("displayName"),
                    "visualSignature": env.get("visualSignature"),
                    "importance": env.get("importance"),
                    "appearsInShots": env.get("appearsInShots", [])
                },
                "remixedEntity": None,  # Phase 3: 由 Intent Injection 填充
                "boundAsset": None,
                "bindingStatus": "UNBOUND",
                "bindingTimestamp": None,
                "isRemixed": False
            }

        # 存储到 Pillar IV
        self.ir["pillars"]["IV_renderStrategy"]["identityMapping"] = identity_mapping

    def _update_identity_mapping_with_remix(self, parsed_intent: Dict[str, Any]) -> None:
        """
        Phase 3: 根据解析后的意图更新 Identity Mapping

        用户选择的实体替换（subjectMapping/environmentMapping）会写入对应实体的 remixedEntity 字段
        采用 Overwrite 模式：每次调用会覆盖 remixedEntity，但保留 originalEntity 不变

        Args:
            parsed_intent: 解析后的用户意图
        """
        identity_mapping = self.ir["pillars"]["IV_renderStrategy"].get("identityMapping", {})

        # 处理主体替换 (subjectMapping)
        for subject_map in parsed_intent.get("subjectMapping", []):
            entity_id = subject_map.get("originalEntityId")

            if not entity_id:
                continue

            # 检查是否是新实体 (new_char_XX)
            if entity_id.startswith("new_"):
                # 为新实体创建映射条目
                identity_mapping[entity_id] = {
                    "entityType": "CHARACTER",
                    "originalEntity": None,  # 新实体没有原始实体
                    "remixedEntity": {
                        "entityId": entity_id,
                        "toDescription": subject_map.get("toDescription", ""),
                        "detailedDescription": subject_map.get("detailedDescription", ""),
                        "persistentAttributes": subject_map.get("persistentAttributes", []),
                        "imageReference": subject_map.get("imageReference"),
                        "affectedShots": subject_map.get("affectedShots", ["all"]),
                        "isNewEntity": True
                    },
                    "boundAsset": subject_map.get("imageReference"),  # 如果有参考图，直接绑定
                    "bindingStatus": "REMIXED_NEW" if subject_map.get("imageReference") else "UNBOUND",
                    "bindingTimestamp": datetime.utcnow().isoformat() + "Z" if subject_map.get("imageReference") else None,
                    "isRemixed": True
                }
                print(f"   ➕ New character entity created: {entity_id}")
            elif entity_id in identity_mapping:
                # 更新现有实体的 remixedEntity（Overwrite 模式）
                identity_mapping[entity_id]["remixedEntity"] = {
                    "toDescription": subject_map.get("toDescription", ""),
                    "detailedDescription": subject_map.get("detailedDescription", ""),
                    "persistentAttributes": subject_map.get("persistentAttributes", []),
                    "imageReference": subject_map.get("imageReference"),
                    "affectedShots": subject_map.get("affectedShots", ["all"]),
                    "isNewEntity": False
                }
                identity_mapping[entity_id]["isRemixed"] = True

                # 如果有参考图，更新绑定状态
                if subject_map.get("imageReference"):
                    identity_mapping[entity_id]["boundAsset"] = subject_map.get("imageReference")
                    identity_mapping[entity_id]["bindingStatus"] = "REMIXED_BOUND"
                    identity_mapping[entity_id]["bindingTimestamp"] = datetime.utcnow().isoformat() + "Z"

                print(f"   🔄 Character remixed: {entity_id} → {subject_map.get('toDescription', '')[:30]}...")
            else:
                print(f"   ⚠️ Warning: Entity {entity_id} not found in Identity Mapping")

        # 处理环境替换 (environmentMapping)
        for env_map in parsed_intent.get("environmentMapping", []):
            entity_id = env_map.get("originalEntityId")

            if not entity_id:
                continue

            if entity_id.startswith("new_"):
                # 为新环境创建映射条目
                identity_mapping[entity_id] = {
                    "entityType": "ENVIRONMENT",
                    "originalEntity": None,
                    "remixedEntity": {
                        "entityId": entity_id,
                        "toDescription": env_map.get("toDescription", ""),
                        "detailedDescription": env_map.get("detailedDescription", ""),
                        "timeOfDay": env_map.get("timeOfDay", "unchanged"),
                        "weather": env_map.get("weather", "unchanged"),
                        "affectedShots": env_map.get("affectedShots", ["all"]),
                        "isNewEntity": True
                    },
                    "boundAsset": None,
                    "bindingStatus": "REMIXED_NEW",
                    "bindingTimestamp": datetime.utcnow().isoformat() + "Z",
                    "isRemixed": True
                }
                print(f"   ➕ New environment entity created: {entity_id}")
            elif entity_id in identity_mapping:
                identity_mapping[entity_id]["remixedEntity"] = {
                    "toDescription": env_map.get("toDescription", ""),
                    "detailedDescription": env_map.get("detailedDescription", ""),
                    "timeOfDay": env_map.get("timeOfDay", "unchanged"),
                    "weather": env_map.get("weather", "unchanged"),
                    "affectedShots": env_map.get("affectedShots", ["all"]),
                    "isNewEntity": False
                }
                identity_mapping[entity_id]["isRemixed"] = True
                identity_mapping[entity_id]["bindingStatus"] = "REMIXED"
                identity_mapping[entity_id]["bindingTimestamp"] = datetime.utcnow().isoformat() + "Z"

                print(f"   🔄 Environment remixed: {entity_id} → {env_map.get('toDescription', '')[:30]}...")
            else:
                print(f"   ⚠️ Warning: Environment {entity_id} not found in Identity Mapping")

        # ============================================================
        # 全局替换检测：当用户说"所有角色"时，自动应用到未被明确 remix 的角色
        # ============================================================
        scope = parsed_intent.get("scope", "SINGLE_ELEMENT")
        style_instruction = parsed_intent.get("styleInstruction", {})
        subject_mappings = parsed_intent.get("subjectMapping", [])

        # 检测是否是全局角色替换
        # 条件：scope 是 GLOBAL 且有 artStyle 或至少有一个 subject mapping
        is_global_character_remix = (
            scope == "GLOBAL" and
            (style_instruction.get("artStyle") or len(subject_mappings) > 0)
        )

        if is_global_character_remix and subject_mappings:
            # 获取模板：使用第一个 subject mapping 作为模板
            template_mapping = subject_mappings[0]
            template_style = style_instruction.get("artStyle", "")
            template_description = template_mapping.get("detailedDescription", "")

            # 统计已被 remix 的角色 ID
            remixed_char_ids = set(
                sm.get("originalEntityId") for sm in subject_mappings
                if sm.get("originalEntityId") and not sm.get("originalEntityId", "").startswith("new_")
            )

            # 遍历所有角色实体，为未被 remix 的应用模板
            applied_count = 0
            for entity_id, mapping in identity_mapping.items():
                if mapping.get("entityType") == "CHARACTER" and entity_id not in remixed_char_ids:
                    if not mapping.get("isRemixed"):
                        # 获取原始角色信息
                        original_entity = mapping.get("originalEntity", {})
                        original_name = original_entity.get("displayName", "Unknown Character") if original_entity else "Unknown Character"

                        # 使用模板生成新描述
                        # 将模板中的描述应用到这个角色（保持角色的原始特征但应用新风格）
                        adapted_description = f"{template_style} version of {original_name}. " + template_description if template_style else template_description

                        mapping["remixedEntity"] = {
                            "toDescription": f"{template_style} {original_name}" if template_style else original_name,
                            "detailedDescription": adapted_description,
                            "persistentAttributes": template_mapping.get("persistentAttributes", []),
                            "imageReference": None,
                            "affectedShots": ["all"],
                            "isNewEntity": False,
                            "autoApplied": True  # 标记为自动应用
                        }
                        mapping["isRemixed"] = True
                        mapping["bindingStatus"] = "REMIXED_AUTO"
                        applied_count += 1

            if applied_count > 0:
                print(f"   🔁 Auto-applied global style to {applied_count} additional characters")

        # 保存更新
        self.ir["pillars"]["IV_renderStrategy"]["identityMapping"] = identity_mapping

    def _run_abstraction(self) -> Dict[str, Any]:
        """
        阶段 2: 逻辑抽象
        将 concrete 数据脱敏，生成 abstract 隐形模板

        TODO: 接入 Meta Prompt (abstractionEngine)
        """
        print(f"🔮 [Stage 2] Running abstraction for {self.job_id}...")

        meta_prompts = self.ir.get("metaPromptsRegistry", {})

        if not meta_prompts.get("abstractionEngine"):
            print("⚠️ Meta Prompt 'abstractionEngine' not configured, using placeholder")

        # 获取 concrete 数据
        story_theme_concrete = self.pillars["I_storyTheme"].get("concrete")
        narrative_concrete = self.pillars["II_narrativeTemplate"].get("concrete")
        shot_recipe_concrete = self.pillars["III_shotRecipe"].get("concrete")

        if not story_theme_concrete or not narrative_concrete or not shot_recipe_concrete:
            return {"status": "error", "reason": "Concrete data not available"}

        # TODO: 调用 AI 进行抽象化
        # abstract_result = self._call_abstraction_engine(
        #     story_theme_concrete,
        #     narrative_concrete,
        #     shot_recipe_concrete,
        #     meta_prompts["abstractionEngine"]
        # )

        return {"status": "success", "message": "Abstraction completed (placeholder)"}

    def _run_intent_injection(self) -> Dict[str, Any]:
        """
        阶段 3: 意图注入 (M4 核心)
        将用户意图注入抽象模板，生成 remixed 数据

        两步流程:
        1. Intent Parser: 解析用户自然语言 → ParsedIntent
        2. Intent Fusion: Abstract + ParsedIntent → RemixedLayer
        """
        print(f"💉 [Stage 3] Running intent injection for {self.job_id}...")

        user_prompt = self.user_intent.get("rawPrompt")
        if not user_prompt:
            return {"status": "error", "reason": "No user intent provided"}

        # 获取参考图片路径
        reference_images = self.user_intent.get("referenceImages", [])

        # 获取隐形模板 (abstract 层)
        hidden_template = self.get_hidden_template()

        if not hidden_template.get("storyTheme") and not hidden_template.get("shotRecipe"):
            return {"status": "error", "reason": "Abstract template not available"}

        # 获取 concrete 层作为参考
        concrete_reference = {
            "storyTheme": self.pillars["I_storyTheme"].get("concrete"),
            "narrative": self.pillars["II_narrativeTemplate"].get("concrete"),
            "shotRecipe": self.pillars["III_shotRecipe"].get("concrete")
        }

        # 获取 Character Ledger 和 Environment Ledger (Phase 2: Entity-Aware Intent Parsing)
        narrative_pillar = self.pillars.get("II_narrativeTemplate", {})
        character_ledger = narrative_pillar.get("characterLedger", [])
        environment_ledger = narrative_pillar.get("environmentLedger", [])

        print(f"📋 [Ledger Context] Characters: {len(character_ledger)}, Environments: {len(environment_ledger)}")

        # ============================================================
        # Step 3.1: Intent Parsing (意图解析)
        # ============================================================
        print(f"🔍 [Stage 3.1] Parsing user intent...")

        try:
            parsed_intent = self._parse_user_intent(
                user_prompt,
                reference_images,
                hidden_template,
                character_ledger,
                environment_ledger
            )

            if not parsed_intent.get("parseSuccess"):
                return {"status": "error", "reason": "Intent parsing failed"}

            # 合规检查
            is_compliant, compliance_issues = check_compliance(parsed_intent)
            if not is_compliant:
                print(f"⚠️ Compliance issues: {compliance_issues}")
                return {"status": "error", "reason": f"Compliance check failed: {compliance_issues}"}

            # 存储解析结果
            self.ir["userIntent"]["parsedIntent"] = parsed_intent

            # Phase 3: 更新 Identity Mapping (将 remix 意图绑定到实体)
            print(f"   [3.1.1] Updating Identity Mapping with remix data...")
            self._update_identity_mapping_with_remix(parsed_intent)

            self.save()

            print(f"✅ [Stage 3.1] Intent parsed: {get_intent_summary(parsed_intent)}")

        except Exception as e:
            print(f"❌ [Stage 3.1] Intent parsing failed: {e}")
            return {"status": "error", "reason": f"Intent parsing failed: {e}"}

        # ============================================================
        # Step 3.2: Intent Fusion (意图融合) - 分批处理避免 token 限制
        # ============================================================
        print(f"🔀 [Stage 3.2] Fusing intent with abstract template...")

        try:
            # 3.2.1: 先生成 Identity Anchors
            print(f"   [3.2.1] Generating identity anchors...")
            identity_anchors = self._generate_identity_anchors(
                parsed_intent,
                hidden_template,
                concrete_reference
            )
            print(f"   ✅ Generated {len(identity_anchors.get('characters', []))} character anchors, {len(identity_anchors.get('environments', []))} environment anchors")

            # 3.2.2: 分批生成 Shot Prompts (每批 8 个镜头)
            shot_recipe_concrete = concrete_reference.get("shotRecipe") or {}
            shot_recipe_abstract = hidden_template.get("shotRecipe") or {}
            concrete_shots = shot_recipe_concrete.get("shots", [])
            abstract_shots = shot_recipe_abstract.get("shotFunctions", [])

            # 如果 abstract 为空，使用 concrete 的镜头列表
            if not abstract_shots and concrete_shots:
                abstract_shots = [{"shotId": s.get("shotId"), "beatTag": s.get("beatTag", "SETUP")} for s in concrete_shots]

            total_shots = len(abstract_shots) if abstract_shots else len(concrete_shots)
            batch_size = 8
            all_remixed_shots = []

            for i in range(0, total_shots, batch_size):
                batch_start = i
                batch_end = min(i + batch_size, total_shots)
                print(f"   [3.2.2] Processing shots {batch_start+1}-{batch_end} of {total_shots}...")

                batch_shots = self._generate_shot_prompts_batch(
                    parsed_intent,
                    identity_anchors,
                    concrete_shots[batch_start:batch_end] if concrete_shots else [],
                    abstract_shots[batch_start:batch_end] if abstract_shots else [],
                    batch_start
                )
                all_remixed_shots.extend(batch_shots)
                print(f"   ✅ Batch {i//batch_size + 1} completed: {len(batch_shots)} shots")

            # 组装完整的 fusion result
            fusion_result = {
                "fusionSuccess": True,
                "fusionTimestamp": datetime.utcnow().isoformat() + "Z",
                "remixedIdentityAnchors": identity_anchors,
                "remixedShots": all_remixed_shots,
                "globalRemixSummary": {
                    "totalShots": total_shots,
                    "shotsModified": len(all_remixed_shots),
                    "primaryChanges": [
                        m.get("toDescription", "")[:50] for m in parsed_intent.get("subjectMapping", [])[:2]
                    ],
                    "styleApplied": parsed_intent.get("styleInstruction", {}).get("artStyle", "None"),
                    "moodShift": parsed_intent.get("moodTone", {}).get("targetMood", "unchanged"),
                    "preservedElements": ["camera skeleton", "narrative rhythm", "beat structure"]
                }
            }

            # 转换为 remixed 层格式
            remixed_layer = convert_to_remixed_layer(fusion_result)

            # 后处理：清理 Gemini 残留、解析占位符、规范化相机字段
            remixed_layer = post_process_remixed_layer(remixed_layer)
            print(f"   ✅ Post-processed: cleaned artifacts, resolved placeholders, normalized camera fields")

            # 存储到 userIntent.remixedLayer
            self.ir["userIntent"]["remixedLayer"] = remixed_layer

            # 同时更新各支柱的 remixed 字段
            self._distribute_remixed_to_pillars(remixed_layer)

            self.save()

            print(f"✅ [Stage 3.2] Fusion completed:\n{generate_fusion_summary(fusion_result)}")

        except Exception as e:
            print(f"❌ [Stage 3.2] Intent fusion failed: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "reason": f"Intent fusion failed: {e}"}

        return {
            "status": "success",
            "message": "Intent injection completed",
            "parsedIntent": get_intent_summary(parsed_intent),
            "remixedShots": len(remixed_layer.get("shots", []))
        }

    def _parse_user_intent(
        self,
        user_prompt: str,
        reference_images: List[str],
        source_abstract: Dict[str, Any],
        character_ledger: List[Dict[str, Any]] = None,
        environment_ledger: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调用 Gemini API 解析用户意图

        Args:
            user_prompt: 用户原始输入
            reference_images: 参考图片路径列表
            source_abstract: 源视频的 abstract 模板
            character_ledger: 角色实体登记表（用于 Entity-Aware 意图解析）
            environment_ledger: 环境实体登记表（用于 Entity-Aware 意图解析）

        Returns:
            ParsedIntent 结构（包含 originalEntityId 字段）
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())

        client = genai.Client(api_key=api_key)

        # 格式化 Character Ledger 为可读文本
        character_ledger = character_ledger or []
        char_ledger_text = self._format_ledger_for_prompt(character_ledger, "character")

        # 格式化 Environment Ledger 为可读文本
        environment_ledger = environment_ledger or []
        env_ledger_text = self._format_ledger_for_prompt(environment_ledger, "environment")

        # 构建 Prompt
        prompt = INTENT_PARSER_PROMPT.replace(
            "{user_instruction}",
            user_prompt
        ).replace(
            "{reference_images}",
            json.dumps(reference_images) if reference_images else "None"
        ).replace(
            "{source_abstract}",
            json.dumps(source_abstract, ensure_ascii=False, indent=2)
        ).replace(
            "{character_ledger}",
            char_ledger_text
        ).replace(
            "{environment_ledger}",
            env_ledger_text
        )

        # 调用 Gemini API
        print(f"🤖 Calling Gemini API for intent parsing...")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 解析 JSON 响应 (带容错处理)
        result = self._parse_json_response(response.text, "Intent parsing")
        print(f"✅ Intent parsing received")

        # 规范化结果
        return parse_intent_result(result)

    def _format_ledger_for_prompt(
        self,
        ledger: List[Dict[str, Any]],
        ledger_type: str
    ) -> str:
        """
        格式化 Ledger 数据为可读文本，用于 Intent Parser Prompt

        Args:
            ledger: Character 或 Environment Ledger 列表
            ledger_type: "character" 或 "environment"

        Returns:
            格式化的文本字符串
        """
        if not ledger:
            return f"No {ledger_type}s detected in the source video."

        lines = [f"=== {ledger_type.upper()} LEDGER ({len(ledger)} entities) ===\n"]

        for entity in ledger:
            entity_id = entity.get("entityId", "unknown")
            display_name = entity.get("displayName", "Unknown")
            visual_signature = entity.get("visualSignature", "")
            importance = entity.get("importance", "SECONDARY")

            lines.append(f"【{entity_id}】 {display_name}")
            lines.append(f"  - Importance: {importance}")
            lines.append(f"  - Visual Signature: {visual_signature}")

            # 添加出现信息（如果有）
            appearances = entity.get("appearances", [])
            if appearances:
                shot_ids = [app.get("shotId", "") for app in appearances[:5]]  # 最多显示5个
                lines.append(f"  - Appears in: {', '.join(shot_ids)}")

                # 添加一些 visualCues 作为额外匹配线索
                all_cues = []
                for app in appearances[:3]:
                    cues = app.get("visualCues", [])
                    all_cues.extend(cues[:2])  # 每个出场取2个线索
                if all_cues:
                    lines.append(f"  - Visual Cues: {', '.join(all_cues[:6])}")

            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def _fuse_intent_with_template(
        self,
        parsed_intent: Dict[str, Any],
        abstract_template: Dict[str, Any],
        concrete_reference: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用 Gemini API 执行意图融合

        Args:
            parsed_intent: 解析后的用户意图
            abstract_template: 抽象模板
            concrete_reference: 具体层参考

        Returns:
            Fusion 结果，包含 remixedIdentityAnchors 和 remixedShots
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
        api_key = api_key.strip()
        api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())

        client = genai.Client(api_key=api_key)

        # 构建 Prompt
        prompt = INTENT_FUSION_PROMPT.replace(
            "{parsed_intent}",
            json.dumps(parsed_intent, ensure_ascii=False, indent=2)
        ).replace(
            "{abstract_template}",
            json.dumps(abstract_template, ensure_ascii=False, indent=2)
        ).replace(
            "{concrete_reference}",
            json.dumps(concrete_reference, ensure_ascii=False, indent=2)
        )

        # 调用 Gemini API
        print(f"🤖 Calling Gemini API for intent fusion...")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 解析 JSON 响应 (带容错处理)
        result = self._parse_json_response(response.text, "Intent fusion")
        print(f"✅ Intent fusion received")

        return result

    def _extract_unique_subjects_and_scenes(
        self,
        concrete_reference: Dict[str, Any],
        max_subjects: int = 50,
        max_environments: int = 20
    ) -> Dict[str, List[Dict]]:
        """
        从 concrete 层提取独特的主体和场景

        Returns:
            {
                "subjects": [{"id": "subj_01", "description": "...", "shotIds": [...]}],
                "environments": [{"id": "env_01", "description": "...", "shotIds": [...]}]
            }
        """
        shot_recipe = concrete_reference.get("shotRecipe") or {}
        shots = shot_recipe.get("shots", [])

        # 提取主体和场景，并记录出现的镜头
        subject_map = {}  # description -> {"count": N, "shotIds": [...]}
        scene_map = {}

        for shot in shots:
            shot_id = shot.get("shotId", "")
            subject = shot.get("subject", "").strip()
            scene = shot.get("scene", "").strip()

            if subject:
                # 使用简化的 key（前50字符）来去重相似描述
                key = subject[:50].lower()
                if key not in subject_map:
                    subject_map[key] = {
                        "fullDescription": subject,
                        "count": 0,
                        "shotIds": []
                    }
                subject_map[key]["count"] += 1
                subject_map[key]["shotIds"].append(shot_id)

            if scene:
                key = scene[:50].lower()
                if key not in scene_map:
                    scene_map[key] = {
                        "fullDescription": scene,
                        "count": 0,
                        "shotIds": []
                    }
                scene_map[key]["count"] += 1
                scene_map[key]["shotIds"].append(shot_id)

        # 按出现频率排序，取 top N
        sorted_subjects = sorted(
            subject_map.values(),
            key=lambda x: x["count"],
            reverse=True
        )[:max_subjects]

        sorted_scenes = sorted(
            scene_map.values(),
            key=lambda x: x["count"],
            reverse=True
        )[:max_environments]

        # 构建返回结构
        subjects = [
            {
                "id": f"subj_{i+1:02d}",
                "description": item["fullDescription"],
                "shotIds": item["shotIds"],
                "frequency": item["count"]
            }
            for i, item in enumerate(sorted_subjects)
        ]

        environments = [
            {
                "id": f"scene_{i+1:02d}",
                "description": item["fullDescription"],
                "shotIds": item["shotIds"],
                "frequency": item["count"]
            }
            for i, item in enumerate(sorted_scenes)
        ]

        return {"subjects": subjects, "environments": environments}

    def _generate_identity_anchors(
        self,
        parsed_intent: Dict[str, Any],
        abstract_template: Dict[str, Any],
        concrete_reference: Dict[str, Any],
        max_character_anchors: int = 50,
        max_environment_anchors: int = 20
    ) -> Dict[str, Any]:
        """
        生成 Identity Anchors (角色和环境的详细描述)

        Phase 4 Enhancement:
        - 优先使用 parsed_intent 中的 detailedDescription（来自 Intent Parser 的 80-120 词描述）
        - 参考 Identity Mapping 中的 remixedEntity 数据
        - 为未被 remix 的实体保留原始描述
        - 支持全局替换：当 scope=GLOBAL 时，为所有角色生成 anchors

        Args:
            max_character_anchors: 最多生成几个角色 anchor（默认 50，足够覆盖大多数视频）
            max_environment_anchors: 最多生成几个环境 anchor（默认 20）
        """
        api_key = os.getenv("GEMINI_API_KEY")
        # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
        if api_key:
            api_key = api_key.strip()
            api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
        client = genai.Client(api_key=api_key)

        # 提取原始视频中的独特主体和场景
        unique_elements = self._extract_unique_subjects_and_scenes(
            concrete_reference,
            max_subjects=max_character_anchors,
            max_environments=max_environment_anchors
        )

        print(f"   📊 Found {len(unique_elements['subjects'])} unique subjects, {len(unique_elements['environments'])} unique environments")

        # Phase 4: 获取 Identity Mapping 中的 remixedEntity 数据
        identity_mapping = self.ir["pillars"]["IV_renderStrategy"].get("identityMapping", {})
        remixed_entities = {
            "characters": [],
            "environments": []
        }

        # 收集已 remix 的角色实体
        for entity_id, mapping in identity_mapping.items():
            if mapping.get("isRemixed") and mapping.get("remixedEntity"):
                remixed = mapping["remixedEntity"]
                original = mapping.get("originalEntity", {})
                entity_type = mapping.get("entityType", "CHARACTER")

                if entity_type == "CHARACTER":
                    remixed_entities["characters"].append({
                        "originalEntityId": entity_id,
                        "originalDisplayName": original.get("displayName", "") if original else "New Character",
                        "remixedDescription": remixed.get("toDescription", ""),
                        "detailedDescription": remixed.get("detailedDescription", ""),
                        "persistentAttributes": remixed.get("persistentAttributes", []),
                        "imageReference": remixed.get("imageReference"),
                        "affectedShots": remixed.get("affectedShots", ["all"]),
                        "isNewEntity": remixed.get("isNewEntity", False)
                    })
                elif entity_type == "ENVIRONMENT":
                    remixed_entities["environments"].append({
                        "originalEntityId": entity_id,
                        "originalDisplayName": original.get("displayName", "") if original else "New Environment",
                        "remixedDescription": remixed.get("toDescription", ""),
                        "detailedDescription": remixed.get("detailedDescription", ""),
                        "timeOfDay": remixed.get("timeOfDay", "unchanged"),
                        "weather": remixed.get("weather", "unchanged"),
                        "affectedShots": remixed.get("affectedShots", ["all"]),
                        "isNewEntity": remixed.get("isNewEntity", False)
                    })

        print(f"   📋 Remixed entities from Identity Mapping: {len(remixed_entities['characters'])} characters, {len(remixed_entities['environments'])} environments")

        prompt = f"""
# Task: Generate Fine-Grained Identity Anchors for Video Remix

Based on the user's remix intent and the Identity Mapping data, generate detailed visual descriptions for EACH remixed character and environment.

## 🎯 CRITICAL: Use Pre-computed Detailed Descriptions

The `detailedDescription` field in the remixed entities below has been carefully crafted with 80-120 words of VISUAL properties only (materials, textures, lighting behavior, proportions).

**YOU MUST:**
1. USE the provided `detailedDescription` AS-IS if it exists and is not empty
2. Only generate new descriptions if `detailedDescription` is empty or missing
3. NEVER replace a good detailed description with a shorter or different one

## Remixed Entities from Identity Mapping (PRE-COMPUTED):
{json.dumps(remixed_entities, ensure_ascii=False, indent=2)}

## Original Video's Unique Subjects (for reference):
{json.dumps(unique_elements['subjects'], ensure_ascii=False, indent=2)}

## Original Video's Unique Environments (for reference):
{json.dumps(unique_elements['environments'], ensure_ascii=False, indent=2)}

## Original Content Context:
- Story Theme: {json.dumps(concrete_reference.get('storyTheme', {}).get('coreTheme', {}), ensure_ascii=False)}

## Instructions:
1. For EACH remixed character, create an anchor using the provided detailedDescription
2. For EACH remixed environment, create an anchor using the provided detailedDescription
3. Map anchorId to the originalEntityId (e.g., orig_char_01 → char_01, orig_env_01 → env_01)
4. For new entities (new_char_XX, new_env_XX), use those IDs as anchorIds
5. Include which shotIds this anchor applies to (from affectedShots)

## Output Format (Strict JSON):
{{
  "characters": [
    {{
      "anchorId": "char_01",
      "originalEntityId": "orig_char_01",
      "originalDescription": "Original subject description from Ledger...",
      "anchorName": "Remixed Character Name",
      "detailedDescription": "COPY the provided 80-120 word visual description EXACTLY - materials, textures, lighting, proportions...",
      "persistentAttributes": ["attribute1", "attribute2"],
      "imageReference": null,
      "styleAdaptation": "How this character looks in the target style",
      "appliedToShots": ["shot_01", "shot_05"]
    }}
  ],
  "environments": [
    {{
      "anchorId": "env_01",
      "originalEntityId": "orig_env_01",
      "originalDescription": "Original scene description from Ledger...",
      "anchorName": "Remixed Location Name",
      "detailedDescription": "COPY the provided 80-120 word visual description EXACTLY - architectural materials, lighting angles, atmospheric density...",
      "atmosphericConditions": "time of day, weather, mood lighting (remixed)",
      "styleAdaptation": "How this environment looks in the target style",
      "appliedToShots": ["shot_02", "shot_08"]
    }}
  ]
}}

Output ONLY valid JSON. No markdown, no explanation.
"""

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        return self._parse_json_response(response.text, "Identity anchors")

    def _generate_shot_prompts_batch(
        self,
        parsed_intent: Dict[str, Any],
        identity_anchors: Dict[str, Any],
        concrete_shots: List[Dict],
        abstract_shots: List[Dict],
        batch_offset: int
    ) -> List[Dict[str, Any]]:
        """
        分批生成 Shot Prompts (T2I + I2V)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        # Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
        if api_key:
            api_key = api_key.strip()
            api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
        client = genai.Client(api_key=api_key)

        # 构建镜头信息
        shots_info = []
        for i, (concrete, abstract) in enumerate(zip(concrete_shots, abstract_shots or concrete_shots)):
            shots_info.append({
                "shotId": concrete.get("shotId", f"shot_{batch_offset + i + 1:02d}"),
                "beatTag": abstract.get("beatTag", concrete.get("beatTag", "SETUP")),
                "startTime": concrete.get("startTime", ""),
                "endTime": concrete.get("endTime", ""),
                "durationSeconds": concrete.get("durationSeconds", 3.0),
                "originalDescription": concrete.get("firstFrameDescription", concrete.get("subject", "")),
                "camera": concrete.get("camera", {}),
                "lighting": concrete.get("lighting", ""),
                "dynamics": concrete.get("dynamics", "")
            })

        prompt = f"""
# Task: Generate T2I and I2V Prompts for Video Shots

Apply the remix intent to generate Imagen 4.0 (T2I) and Veo 3.1 (I2V) prompts.

## 🎯 ABSOLUTE CAMERA PRESERVATION (CRITICAL)

The camera parameters from the original video MUST be preserved EXACTLY. This is non-negotiable.
- **shotSize**: NEVER change (CLOSE_UP stays CLOSE_UP, WIDE stays WIDE)
- **cameraAngle**: NEVER change (Eye-level stays Eye-level, High angle stays High angle)
- **cameraMovement**: NEVER change (Static stays Static, Pan stays Pan)
- **focalLengthDepth**: NEVER change

The new remixed subject MUST FIT the original camera framing. If original is CLOSE_UP, the new subject appears in CLOSE_UP.

## Identity Anchors (use detailedDescription for prompts):
{json.dumps(identity_anchors, ensure_ascii=False, indent=2)}

## User Remix Intent:
- Subject Changes: {json.dumps(parsed_intent.get('subjectMapping', []), ensure_ascii=False)}
- Environment Changes: {json.dumps(parsed_intent.get('environmentMapping', []), ensure_ascii=False)}
- Style: {parsed_intent.get('styleInstruction', {}).get('artStyle', 'realistic')}
- Mood: {parsed_intent.get('moodTone', {}).get('targetMood', 'unchanged')}

## Shots to Process:
{json.dumps(shots_info, ensure_ascii=False, indent=2)}

## Output Format (Strict JSON array):
[
  {{
    "shotId": "shot_01",
    "beatTag": "HOOK",
    "startTime": "00:00:00.000",
    "endTime": "00:00:03.000",
    "durationSeconds": 3.0,
    "cameraPreserved": {{
      "shotSize": "EXACTLY from original - NEVER modify",
      "cameraAngle": "EXACTLY from original - NEVER modify",
      "cameraMovement": "EXACTLY from original - NEVER modify",
      "focalLengthDepth": "EXACTLY from original - NEVER modify"
    }},
    "T2I_FirstFrame": "[Subject from Identity Anchor detailedDescription], [pose matching original], [environment], [style], [lighting], [EXACT camera specs from cameraPreserved], high detail, cinematic --ar 16:9",
    "I2V_VideoGen": "[EXACT camera movement from cameraPreserved], [action], [physics details], maintaining exact composition and lighting from the first frame, cinematic, [duration]s",
    "remixNotes": "Brief change description",
    "appliedAnchors": {{"characters": ["char_01"], "environments": ["env_01"]}}
  }}
]

## CRITICAL RULES:
1. T2I prompt MUST end with --ar 16:9
2. I2V prompt MUST include "maintaining exact composition and lighting from the first frame"
3. **cameraPreserved MUST COPY EXACTLY from the original shot's camera field** - DO NOT INVENT NEW VALUES
4. T2I prompt MUST include the camera's shotSize (e.g., "medium shot", "close-up", "wide shot")
5. I2V prompt MUST start with the exact camera movement (e.g., "camera holds steady", "camera pans left")
6. Use the detailedDescription from Identity Anchors (80-120 words of visual properties)
7. Keep prompts concise but specific (50-80 words each)

Output ONLY valid JSON array. No markdown.
"""

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        result = self._parse_json_response(response.text, f"Shot prompts batch")

        # 确保返回列表
        if isinstance(result, dict) and "remixedShots" in result:
            return result["remixedShots"]
        elif isinstance(result, list):
            return result
        else:
            return []

    def _parse_json_response(self, text: str, context: str = "API") -> Dict[str, Any]:
        """
        解析 JSON 响应，带容错处理

        Args:
            text: 原始响应文本
            context: 上下文描述 (用于错误消息)

        Returns:
            解析后的 JSON 对象
        """
        import re

        if not text:
            raise ValueError(f"{context}: Empty response")

        s = text.strip()

        # 移除 markdown code blocks
        if s.startswith("```"):
            lines = s.split('\n')
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = '\n'.join(lines).strip()

        # 尝试直接解析
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            print(f"⚠️ {context}: Initial JSON parse failed, attempting fixes...")
            print(f"   Error: {e.msg} at line {e.lineno}")

        # 修复常见问题
        # 1. 移除尾部逗号
        s = re.sub(r',\s*]', ']', s)
        s = re.sub(r',\s*}', '}', s)

        # 2. 移除注释
        s = re.sub(r'//.*?\n', '\n', s)
        s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)

        # 3. 修复无效的转义序列（如 \N, \n 在不该出现的地方）
        # 先保护合法的转义序列
        s = s.replace('\\\\', '<<<DOUBLE_BACKSLASH>>>')
        s = s.replace('\\"', '<<<ESCAPED_QUOTE>>>')
        s = s.replace('\\n', '<<<NEWLINE>>>')
        s = s.replace('\\t', '<<<TAB>>>')
        s = s.replace('\\r', '<<<CR>>>')
        # 移除其他无效的反斜杠（在 JSON 字符串中不合法的转义）
        s = re.sub(r'\\([^"\\nrtbfu/])', r'\1', s)
        # 恢复合法的转义序列
        s = s.replace('<<<DOUBLE_BACKSLASH>>>', '\\\\')
        s = s.replace('<<<ESCAPED_QUOTE>>>', '\\"')
        s = s.replace('<<<NEWLINE>>>', '\\n')
        s = s.replace('<<<TAB>>>', '\\t')
        s = s.replace('<<<CR>>>', '\\r')

        # 3. 修复字符串内的换行
        def fix_string_newlines(text):
            result = []
            in_string = False
            escape_next = False
            for char in text:
                if escape_next:
                    result.append(char)
                    escape_next = False
                    continue
                if char == '\\':
                    result.append(char)
                    escape_next = True
                    continue
                if char == '"':
                    in_string = not in_string
                    result.append(char)
                    continue
                if char == '\n' and in_string:
                    result.append('\\n')
                    continue
                result.append(char)
            return ''.join(result)

        s = fix_string_newlines(s)

        # 再次尝试解析
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            print(f"⚠️ {context}: JSON parse failed, attempting truncation repair...")

            # 尝试修复截断的 JSON
            repaired = self._try_repair_truncated_json(s)
            if repaired:
                print(f"   🔧 JSON repair successful")
                return repaired

            # 打印错误上下文
            lines = s.split('\n')
            error_line = e.lineno - 1
            start = max(0, error_line - 2)
            end = min(len(lines), error_line + 3)
            print(f"❌ {context}: JSON parse failed after all fixes")
            print(f"   Error: {e.msg} at line {e.lineno}, col {e.colno}")
            print(f"   Error context (lines {start+1}-{end}):")
            for i in range(start, end):
                marker = ">>> " if i == error_line else "    "
                line_preview = lines[i][:80] + "..." if len(lines[i]) > 80 else lines[i]
                print(f"   {marker}{i+1}: {line_preview}")
            raise

    def _try_repair_truncated_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        尝试修复截断的 JSON

        常见问题：
        1. JSON 在中间被截断，缺少闭合括号
        2. 最后一个元素不完整
        """
        s = text.strip()

        # 如果已经是有效 JSON，直接返回
        try:
            return json.loads(s)
        except:
            pass

        # 尝试找到最后一个完整的 } 或 ]
        # 然后补全缺失的括号
        open_braces = s.count('{') - s.count('}')
        open_brackets = s.count('[') - s.count(']')

        if open_braces > 0 or open_brackets > 0:
            # 删除最后一个不完整的元素（通常在逗号后面）
            # 找到最后一个完整的 } 或 ]
            last_complete_idx = max(s.rfind('}'), s.rfind(']'))
            if last_complete_idx > 0:
                s = s[:last_complete_idx + 1]

            # 重新计算
            open_braces = s.count('{') - s.count('}')
            open_brackets = s.count('[') - s.count(']')

            # 补全括号
            s += ']' * open_brackets + '}' * open_braces

            try:
                return json.loads(s)
            except:
                pass

        # 尝试提取第一个完整的顶层对象
        brace_count = 0
        start_idx = s.find('{')
        if start_idx >= 0:
            for i in range(start_idx, len(s)):
                if s[i] == '{':
                    brace_count += 1
                elif s[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return json.loads(s[start_idx:i + 1])
                        except:
                            break

        return None

    def _distribute_remixed_to_pillars(self, remixed_layer: Dict[str, Any]) -> None:
        """
        将 remixed 结果分发到各支柱的 remixed 字段

        Args:
            remixed_layer: 融合后的 remixed 层数据
        """
        # 提取 Identity Anchors 到 Pillar IV
        identity_anchors = remixed_layer.get("identityAnchors", {})
        if identity_anchors:
            # 转换为 Pillar IV 格式
            char_anchors = []
            for char in identity_anchors.get("characters", []):
                char_anchors.append({
                    "anchorId": char.get("anchorId"),
                    "role": "remixed",
                    "name": char.get("anchorName", ""),
                    "description": char.get("detailedDescription", ""),
                    "visualDNA": {
                        "hair": "",
                        "clothing": "",
                        "features": char.get("styleAdaptation", ""),
                        "bodyType": "",
                        "accessories": ", ".join(char.get("persistentAttributes", []))
                    },
                    "threeViews": {"front": None, "side": None, "back": None},
                    "status": "NOT_STARTED"
                })

            env_anchors = []
            for env in identity_anchors.get("environments", []):
                env_anchors.append({
                    "anchorId": env.get("anchorId"),
                    "type": "remixed",
                    "name": env.get("anchorName", ""),
                    "description": env.get("detailedDescription", ""),
                    "referenceImage": None,
                    "status": "NOT_STARTED"
                })

            self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["characters"] = char_anchors
            self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["environments"] = env_anchors

        # 提取 T2I/I2V prompts 到 shotRenderRecipes
        shots = remixed_layer.get("shots", [])
        render_recipes = []
        for shot in shots:
            # 处理 appliedAnchors 可能是 list 或 dict 的情况
            applied_anchors = shot.get("appliedAnchors", {})
            if isinstance(applied_anchors, dict):
                ref_chars = applied_anchors.get("characters", [])
                ref_envs = applied_anchors.get("environments", [])
            elif isinstance(applied_anchors, list):
                # 如果是 list，尝试提取其中的引用
                ref_chars = []
                ref_envs = []
                for anchor in applied_anchors:
                    if isinstance(anchor, str):
                        # 简单字符串形式的 anchor ID
                        if anchor.startswith("char_"):
                            ref_chars.append(anchor)
                        elif anchor.startswith("env_"):
                            ref_envs.append(anchor)
                        else:
                            ref_chars.append(anchor)  # 默认当作角色
                    elif isinstance(anchor, dict):
                        # dict 形式，尝试获取 id
                        anchor_id = anchor.get("id", anchor.get("anchorId", ""))
                        if "char" in anchor_id.lower() or anchor.get("type") == "character":
                            ref_chars.append(anchor_id)
                        else:
                            ref_envs.append(anchor_id)
            else:
                ref_chars = []
                ref_envs = []

            render_recipes.append({
                "shotId": shot.get("shotId"),
                "textToImagePrompt": shot.get("T2I_FirstFrame", ""),
                "imageToVideoPrompt": shot.get("I2V_VideoGen", ""),
                "referenceAnchors": ref_chars + ref_envs,
                "executionType": "I2V",
                "status": "NOT_STARTED"
            })

        self.ir["pillars"]["IV_renderStrategy"]["shotRenderRecipes"] = render_recipes

    def _run_asset_generation(self) -> Dict[str, Any]:
        """
        阶段 4: 资产生成
        使用 Gemini 3 Pro Image 生成角色三视图和环境参考图

        流程:
        1. 从 Pillar IV 获取 Identity Anchors
        2. 为每个角色生成三视图 (front/side/back)
        3. 为每个环境生成参考图
        4. 更新 film_ir.json 中的资产路径
        """
        print(f"🎨 [Stage 4] Running asset generation for {self.job_id}...")

        try:
            from core.asset_generator import AssetGenerator, AssetStatus

            # 初始化资产生成器
            generator = AssetGenerator(self.job_id, str(self.project_dir))

            # 获取 Identity Anchors
            identity_anchors = self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]
            characters = identity_anchors.get("characters", [])
            environments = identity_anchors.get("environments", [])

            if not characters and not environments:
                print("⚠️ No identity anchors found. Run intent injection (M4) first.")
                return {"status": "skipped", "message": "No identity anchors to generate"}

            # 获取用户参考图（如果有）
            user_reference_images = self.ir.get("userIntent", {}).get("referenceImages", [])

            total_assets = len(characters) * 3 + len(environments)
            generated_count = 0
            failed_count = 0

            print(f"   📊 Total assets to generate: {total_assets} ({len(characters)} characters × 3 views + {len(environments)} environments)")

            # 进度回调
            def on_progress(anchor_id, view, status, path=None, error=None):
                nonlocal generated_count, failed_count
                if status == "SUCCESS":
                    generated_count += 1
                elif status == "FAILED":
                    failed_count += 1

            # 生成角色三视图
            for i, char in enumerate(characters):
                anchor_id = char.get("anchorId", f"char_{i+1:02d}")
                anchor_name = char.get("name", "Unknown Character")
                description = char.get("description", "")

                print(f"\n   👤 [{i+1}/{len(characters)}] Generating character: {anchor_name}")

                # 查找该角色的参考图（如果用户提供了）
                user_ref_path = None
                if user_reference_images:
                    # 简单策略：第一个参考图给第一个角色
                    if i < len(user_reference_images):
                        user_ref_path = user_reference_images[i]

                # 从 visualDNA 提取持久属性
                visual_dna = char.get("visualDNA", {})
                persistent_attrs = []
                if visual_dna.get("hair"):
                    persistent_attrs.append(f"hair: {visual_dna['hair']}")
                if visual_dna.get("clothing"):
                    persistent_attrs.append(f"clothing: {visual_dna['clothing']}")
                if visual_dna.get("accessories"):
                    persistent_attrs.append(f"accessories: {visual_dna['accessories']}")
                if visual_dna.get("features"):
                    persistent_attrs.append(f"features: {visual_dna['features']}")

                # 生成三视图
                results = generator.generate_character_assets(
                    anchor_id=anchor_id,
                    anchor_name=anchor_name,
                    detailed_description=description,
                    style_adaptation=visual_dna.get("features", ""),
                    persistent_attributes=persistent_attrs if persistent_attrs else None,
                    user_reference_path=user_ref_path,
                    on_progress=on_progress
                )

                # 更新 IR 中的三视图路径
                self._update_character_asset_paths(anchor_id, results)

            # 生成环境参考图
            for i, env in enumerate(environments):
                anchor_id = env.get("anchorId", f"env_{i+1:02d}")
                anchor_name = env.get("name", "Unknown Environment")
                description = env.get("description", "")

                print(f"\n   🏞️ [{i+1}/{len(environments)}] Generating environment: {anchor_name}")

                # 生成环境参考图
                result = generator.generate_environment_asset(
                    anchor_id=anchor_id,
                    anchor_name=anchor_name,
                    detailed_description=description,
                    atmospheric_conditions="",  # 从描述中已包含
                    style_adaptation="",
                    on_progress=on_progress
                )

                # 更新 IR 中的环境参考图路径
                self._update_environment_asset_path(anchor_id, result)

            # 保存更新后的 IR
            self.save()

            # 生成摘要
            success_rate = (generated_count / total_assets * 100) if total_assets > 0 else 0
            print(f"\n✅ [Stage 4] Asset generation completed:")
            print(f"   Generated: {generated_count}/{total_assets} ({success_rate:.1f}%)")
            if failed_count > 0:
                print(f"   Failed: {failed_count}")

            return {
                "status": "success" if failed_count == 0 else "partial",
                "message": f"Generated {generated_count}/{total_assets} assets",
                "generated": generated_count,
                "failed": failed_count,
                "total": total_assets,
                "assets_dir": str(generator.assets_dir)
            }

        except Exception as e:
            print(f"❌ [Stage 4] Asset generation failed: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "failed", "message": str(e)}

    def _update_character_asset_paths(self, anchor_id: str, results: Dict) -> None:
        """
        更新角色的三视图路径到 IR

        Args:
            anchor_id: 角色锚点 ID
            results: 生成结果 {view: GeneratedAsset}
        """
        characters = self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["characters"]

        for char in characters:
            if char.get("anchorId") == anchor_id:
                # 更新三视图路径
                three_views = char.get("threeViews", {"front": None, "side": None, "back": None})

                for view_name, asset in results.items():
                    if asset.status.value == "SUCCESS" and asset.file_path:
                        three_views[view_name] = asset.file_path

                char["threeViews"] = three_views

                # 更新状态
                if all(three_views.get(v) for v in ["front", "side", "back"]):
                    char["status"] = "SUCCESS"
                elif any(three_views.get(v) for v in ["front", "side", "back"]):
                    char["status"] = "PARTIAL"
                else:
                    char["status"] = "FAILED"

                break

    def _update_environment_asset_path(self, anchor_id: str, result) -> None:
        """
        更新环境的参考图路径到 IR

        Args:
            anchor_id: 环境锚点 ID
            result: GeneratedAsset
        """
        environments = self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["environments"]

        for env in environments:
            if env.get("anchorId") == anchor_id:
                if result.status.value == "SUCCESS" and result.file_path:
                    env["referenceImage"] = result.file_path
                    env["status"] = "SUCCESS"
                else:
                    env["status"] = "FAILED"
                break

    def _run_shot_refinement(self) -> Dict[str, Any]:
        """
        阶段 5: 分镜精修
        生成每一镜的 T2I/I2V Prompt

        TODO: 接入 Meta Prompts (t2iPromptComposer, i2vPromptComposer)
        """
        print(f"✨ [Stage 5] Running shot refinement for {self.job_id}...")

        meta_prompts = self.ir.get("metaPromptsRegistry", {})

        if not meta_prompts.get("t2iPromptComposer"):
            print("⚠️ Meta Prompt 't2iPromptComposer' not configured")

        if not meta_prompts.get("i2vPromptComposer"):
            print("⚠️ Meta Prompt 'i2vPromptComposer' not configured")

        # TODO: 生成渲染配方

        return {"status": "success", "message": "Shot refinement completed (placeholder)"}

    def _run_execution(self) -> Dict[str, Any]:
        """
        阶段 6: 执行视频生成
        调用 Imagen + Veo 生成最终视频
        """
        print(f"🎬 [Stage 6] Running video execution for {self.job_id}...")

        # TODO: 调用视频生成管线

        return {"status": "success", "message": "Execution completed (placeholder)"}

    # ============================================================
    # 意图处理
    # ============================================================

    def set_user_intent(
        self,
        raw_prompt: str,
        reference_images: Optional[List[str]] = None
    ) -> None:
        """
        设置用户意图

        Args:
            raw_prompt: 用户原始输入
            reference_images: 参考图片路径列表 (可选)
        """
        # 如果之前有意图，先保存到历史记录
        prev_prompt = self.ir["userIntent"].get("rawPrompt")
        prev_parsed = self.ir["userIntent"].get("parsedIntent")
        if prev_prompt and prev_parsed:
            # 确保 intentHistory 存在
            if "intentHistory" not in self.ir["userIntent"]:
                self.ir["userIntent"]["intentHistory"] = []

            # 追加到历史记录
            self.ir["userIntent"]["intentHistory"].append({
                "rawPrompt": prev_prompt,
                "parsedIntent": prev_parsed,
                "referenceImages": self.ir["userIntent"].get("referenceImages", []),
                "injectedAt": self.ir["userIntent"].get("injectedAt"),
                "archivedAt": datetime.utcnow().isoformat() + "Z",
                "historyIndex": len(self.ir["userIntent"]["intentHistory"])
            })
            print(f"   📜 Previous intent archived to history (index: {len(self.ir['userIntent']['intentHistory']) - 1})")

        # 设置新的意图
        self.ir["userIntent"]["rawPrompt"] = raw_prompt
        self.ir["userIntent"]["referenceImages"] = reference_images or []
        self.ir["userIntent"]["injectedAt"] = datetime.utcnow().isoformat() + "Z"
        # 清除之前的解析结果（但保留历史）
        self.ir["userIntent"]["parsedIntent"] = None
        self.ir["userIntent"]["remixedLayer"] = None
        self.save()

    def get_remixed_layer(self) -> Optional[Dict[str, Any]]:
        """
        获取 remixed 层数据

        Returns:
            remixedLayer 或 None
        """
        return self.ir["userIntent"].get("remixedLayer")

    def get_intent_history(self) -> List[Dict[str, Any]]:
        """
        获取意图修改历史记录

        Returns:
            意图历史列表，每条记录包含:
            - rawPrompt: 原始用户输入
            - parsedIntent: 解析后的意图
            - referenceImages: 参考图片
            - injectedAt: 注入时间
            - archivedAt: 归档时间
            - historyIndex: 历史索引
        """
        return self.ir["userIntent"].get("intentHistory", [])

    def get_current_intent_with_history(self) -> Dict[str, Any]:
        """
        获取当前意图及其历史记录，用于前端展示

        Returns:
            包含当前意图和历史记录的字典
        """
        return {
            "current": {
                "rawPrompt": self.ir["userIntent"].get("rawPrompt"),
                "parsedIntent": self.ir["userIntent"].get("parsedIntent"),
                "referenceImages": self.ir["userIntent"].get("referenceImages", []),
                "injectedAt": self.ir["userIntent"].get("injectedAt"),
                "isRemixed": self.ir["userIntent"].get("remixedLayer") is not None
            },
            "history": self.get_intent_history(),
            "totalModifications": len(self.get_intent_history()) + (1 if self.ir["userIntent"].get("rawPrompt") else 0)
        }

    def get_remix_diff_for_frontend(self) -> List[Dict[str, Any]]:
        """
        获取 concrete vs remixed 的差异，用于前端 Diff View

        Returns:
            每个镜头的差异列表
        """
        from core.meta_prompts import get_remix_diff

        concrete = self.pillars["III_shotRecipe"].get("concrete", {})
        remixed_layer = self.get_remixed_layer()

        if not remixed_layer:
            return []

        return get_remix_diff(concrete, remixed_layer)

    def get_hidden_template(self) -> Dict[str, Any]:
        """
        获取隐形模板 (所有支柱的 abstract 层)
        """
        return {
            "storyTheme": self.pillars["I_storyTheme"].get("abstract"),
            "narrativeTemplate": self.pillars["II_narrativeTemplate"].get("abstract"),
            "shotRecipe": self.pillars["III_shotRecipe"].get("abstract")
        }

    # ============================================================
    # 支柱数据操作
    # ============================================================

    def update_pillar(self, pillar: str, layer: str, data: Dict[str, Any]) -> None:
        """
        更新支柱数据

        Args:
            pillar: 支柱名 (I_storyTheme/II_narrativeTemplate/III_shotRecipe/IV_renderStrategy)
            layer: 层级 (concrete/abstract/remixed)
            data: 数据
        """
        if pillar not in self.pillars:
            raise ValueError(f"Unknown pillar: {pillar}")

        if pillar == "IV_renderStrategy":
            self.ir["pillars"][pillar].update(data)
        else:
            if layer not in ["concrete", "abstract", "remixed"]:
                raise ValueError(f"Unknown layer: {layer}")
            self.ir["pillars"][pillar][layer] = data

        self.save()

    def get_active_layer(self, pillar: str) -> Optional[Dict[str, Any]]:
        """
        获取支柱的活跃层数据
        优先级: remixed > concrete > None
        """
        if pillar not in self.pillars:
            raise ValueError(f"Unknown pillar: {pillar}")

        pillar_data = self.pillars[pillar]

        if pillar == "IV_renderStrategy":
            return pillar_data

        if pillar_data.get("remixed"):
            return pillar_data["remixed"]
        return pillar_data.get("concrete")

    # ============================================================
    # 前端数据输出
    # ============================================================

    def get_story_theme_for_frontend(self) -> Optional[Dict[str, Any]]:
        """获取前端 StoryThemeAnalysis 格式数据"""
        return convert_to_frontend_story_theme(self.ir)

    def get_script_analysis_for_frontend(self) -> Optional[Dict[str, Any]]:
        """获取前端 ScriptAnalysis 格式数据"""
        return convert_to_frontend_script_analysis(self.ir)

    def get_storyboard_for_frontend(self, base_url: str = "") -> list:
        """获取前端 StoryboardShot[] 格式数据"""
        return convert_to_frontend_storyboard(self.ir, base_url)

    def get_full_analysis_for_frontend(self, base_url: str = "") -> Dict[str, Any]:
        """
        获取完整的前端分析结果

        Returns:
            对应前端 RemixAnalysisResult 结构
        """
        return {
            "storyTheme": self.get_story_theme_for_frontend(),
            "scriptAnalysis": self.get_script_analysis_for_frontend(),
            "storyboard": self.get_storyboard_for_frontend(base_url)
        }

    # ============================================================
    # 资产锚点操作
    # ============================================================

    def add_character_anchor(self, character_data: Dict[str, Any]) -> str:
        """添加角色锚点"""
        anchors = self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["characters"]

        anchor_id = f"char_{len(anchors) + 1:02d}"
        character_data["anchorId"] = anchor_id
        character_data["status"] = character_data.get("status", "NOT_STARTED")

        anchors.append(character_data)
        self.save()

        return anchor_id

    def add_environment_anchor(self, env_data: Dict[str, Any]) -> str:
        """添加场景锚点"""
        anchors = self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["environments"]

        anchor_id = f"env_{len(anchors) + 1:02d}"
        env_data["anchorId"] = anchor_id
        env_data["status"] = env_data.get("status", "NOT_STARTED")

        anchors.append(env_data)
        self.save()

        return anchor_id

    def update_anchor_status(self, anchor_id: str, status: str) -> None:
        """更新锚点状态"""
        for char in self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["characters"]:
            if char.get("anchorId") == anchor_id:
                char["status"] = status
                self.save()
                return

        for env in self.ir["pillars"]["IV_renderStrategy"]["identityAnchors"]["environments"]:
            if env.get("anchorId") == anchor_id:
                env["status"] = status
                self.save()
                return

    # ============================================================
    # Meta Prompts 配置
    # ============================================================

    def set_meta_prompt(self, key: str, prompt: str) -> None:
        """
        设置 Meta Prompt

        Args:
            key: Prompt 键名
            prompt: Prompt 内容
        """
        valid_keys = [
            "storyThemeAnalysis", "narrativeExtraction", "shotDecomposition",
            "abstractionEngine", "intentFusion",
            "characterAnchorGen", "environmentAnchorGen",
            "t2iPromptComposer", "i2vPromptComposer"
        ]

        if key not in valid_keys:
            raise ValueError(f"Invalid meta prompt key: {key}. Valid keys: {valid_keys}")

        self.ir["metaPromptsRegistry"][key] = prompt
        self.save()

    def load_meta_prompts_from_config(self, config_path: Path) -> None:
        """
        从配置文件加载所有 Meta Prompts

        Args:
            config_path: 配置文件路径 (JSON)
        """
        import json

        with open(config_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)

        for key, prompt in prompts.items():
            if key in self.ir["metaPromptsRegistry"]:
                self.ir["metaPromptsRegistry"][key] = prompt

        self.save()
        print(f"✅ Loaded {len(prompts)} meta prompts from {config_path}")
