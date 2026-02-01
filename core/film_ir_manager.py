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
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from google import genai
from google.genai import types

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
    STORY_THEME_ANALYSIS_PROMPT,
    convert_story_theme_to_frontend
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
            "intentInjection": ["abstraction"],
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

        当前实现: storyThemeAnalysis (支柱 I)
        """
        print(f"🔍 [Stage 1] Running specific analysis for {self.job_id}...")

        # 获取视频路径
        video_path = self.job_dir / self.source_video
        if not video_path.exists():
            return {"status": "error", "reason": f"Video file not found: {video_path}"}

        # ============================================================
        # Step 1: Story Theme Analysis (支柱 I)
        # ============================================================
        print(f"📊 [Stage 1.1] Analyzing Story Theme...")

        try:
            story_theme_result = self._analyze_story_theme(video_path)
            if story_theme_result:
                # 转换为前端格式并存储
                frontend_format = convert_story_theme_to_frontend(story_theme_result)
                self.ir["pillars"]["I_storyTheme"]["concrete"] = frontend_format
                self.save()
                print(f"✅ [Stage 1.1] Story Theme analysis completed")
            else:
                print(f"⚠️ [Stage 1.1] Story Theme analysis returned empty result")
        except Exception as e:
            print(f"❌ [Stage 1.1] Story Theme analysis failed: {e}")
            return {"status": "error", "reason": f"Story Theme analysis failed: {e}"}

        # ============================================================
        # Step 2: Narrative Extraction (支柱 II) - 待接入
        # ============================================================
        print(f"📝 [Stage 1.2] Narrative Extraction - waiting for Meta Prompt")

        # ============================================================
        # Step 3: Shot Decomposition (支柱 III) - 已在初始化时完成基础版本
        # ============================================================
        print(f"🎬 [Stage 1.3] Shot Recipe - using initialized data")

        return {"status": "success", "message": "Specific analysis completed"}

    def _analyze_story_theme(self, video_path: Path) -> Optional[Dict[str, Any]]:
        """
        调用 Gemini API 分析视频主题

        Args:
            video_path: 视频文件路径

        Returns:
            AI 分析结果 (原始格式)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        client = genai.Client(api_key=api_key)

        # 上传视频文件
        print(f"📤 Uploading video to Gemini...")
        uploaded_file = client.files.upload(file=str(video_path))

        # 等待文件处理完成
        import time
        while uploaded_file.state.name == "PROCESSING":
            print(f"⏳ Waiting for video processing...")
            time.sleep(3)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            raise RuntimeError(f"Video processing failed: {uploaded_file.state.name}")

        print(f"✅ Video uploaded and ready")

        # 构建 Prompt (替换 {input_content} 占位符)
        prompt = STORY_THEME_ANALYSIS_PROMPT.replace(
            "{input_content}",
            "[Video file attached - analyze the visual and audio content]"
        )

        # 调用 Gemini API
        print(f"🤖 Calling Gemini API for Story Theme analysis...")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 解析 JSON 响应
        try:
            result = json.loads(response.text)
            print(f"✅ Story Theme analysis received")
            return result
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response: {e}")
            print(f"Raw response: {response.text[:500]}...")
            raise

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
        阶段 3: 意图注入
        将用户意图注入抽象模板，生成 remixed 数据

        TODO: 接入 Meta Prompt (intentFusion)
        """
        print(f"💉 [Stage 3] Running intent injection for {self.job_id}...")

        user_prompt = self.user_intent.get("rawPrompt")
        if not user_prompt:
            return {"status": "error", "reason": "No user intent provided"}

        # 获取隐形模板
        hidden_template = self.get_hidden_template()

        if not hidden_template.get("storyTheme") or not hidden_template.get("narrativeTemplate"):
            return {"status": "error", "reason": "Abstract template not available"}

        meta_prompts = self.ir.get("metaPromptsRegistry", {})

        if not meta_prompts.get("intentFusion"):
            print("⚠️ Meta Prompt 'intentFusion' not configured, using placeholder")

        # TODO: 调用 AI 进行意图融合
        # remixed_result = self._call_intent_fusion(
        #     hidden_template,
        #     user_prompt,
        #     meta_prompts["intentFusion"]
        # )

        return {"status": "success", "message": "Intent injection completed (placeholder)"}

    def _run_asset_generation(self) -> Dict[str, Any]:
        """
        阶段 4: 资产生成
        生成角色和场景的三视图资产

        TODO: 接入 Meta Prompts (characterAnchorGen, environmentAnchorGen)
        """
        print(f"🎨 [Stage 4] Running asset generation for {self.job_id}...")

        meta_prompts = self.ir.get("metaPromptsRegistry", {})

        if not meta_prompts.get("characterAnchorGen"):
            print("⚠️ Meta Prompt 'characterAnchorGen' not configured")

        if not meta_prompts.get("environmentAnchorGen"):
            print("⚠️ Meta Prompt 'environmentAnchorGen' not configured")

        # TODO: 生成三视图资产

        return {"status": "success", "message": "Asset generation completed (placeholder)"}

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

    def set_user_intent(self, raw_prompt: str) -> None:
        """
        设置用户意图

        Args:
            raw_prompt: 用户原始输入
        """
        self.ir["userIntent"]["rawPrompt"] = raw_prompt
        self.ir["userIntent"]["injectedAt"] = datetime.utcnow().isoformat() + "Z"
        self.save()

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
