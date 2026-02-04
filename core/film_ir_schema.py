# core/film_ir_schema.py
"""
Film IR Schema 定义
=====================
电影逻辑中间层的数据结构定义，与前端 TypeScript 类型精确对齐。

四大支柱 (Four Pillars):
- I. Story Theme (灵魂层) - 对应前端 StoryThemeAnalysis
- II. Narrative Template (骨架层) - 对应前端 ScriptAnalysis
- III. Shot Recipe (肌肉层) - 分镜配方
- IV. Render Strategy (执行层) - 资产锚点 + 生成配置
"""

from typing import TypedDict, List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 阶段状态枚举
# ============================================================

class StageStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


# ============================================================
# 支柱 I: Story Theme (灵魂层)
# 对应前端 StoryThemeAnalysis 九维表格
# ============================================================

class BasicInfo(TypedDict):
    """基本信息"""
    title: str
    type: str
    duration: str
    creator: str
    background: str


class CoreTheme(TypedDict):
    """核心主题"""
    summary: str
    keywords: str


class Narrative(TypedDict):
    """叙事内容 (起承转合)"""
    startingPoint: str
    coreConflict: str
    climax: str
    ending: str


class NarrativeStructure(TypedDict):
    """叙事结构"""
    narrativeMethod: str
    timeStructure: str


class CharacterAnalysis(TypedDict):
    """人物分析"""
    protagonist: str
    characterChange: str
    relationships: str


class AudioVisual(TypedDict):
    """视听语言"""
    visualStyle: str
    cameraLanguage: str
    soundDesign: str


class Symbolism(TypedDict):
    """象征与隐喻"""
    repeatingImagery: str
    symbolicMeaning: str


class ThematicStance(TypedDict):
    """主题立场"""
    creatorAttitude: str
    emotionalTone: str


class RealWorldSignificance(TypedDict):
    """现实意义"""
    socialEmotionalValue: str
    audienceInterpretation: str


class StoryThemeConcrete(TypedDict):
    """支柱 I: 具体层 - 含专有名词的原始分析"""
    basicInfo: BasicInfo
    coreTheme: CoreTheme
    narrative: Narrative
    narrativeStructure: NarrativeStructure
    characterAnalysis: CharacterAnalysis
    audioVisual: AudioVisual
    symbolism: Symbolism
    thematicStance: ThematicStance
    realWorldSignificance: RealWorldSignificance


class StoryThemeAbstract(TypedDict):
    """支柱 I: 抽象层 - 脱敏后的通用模板"""
    archetype: str  # 故事原型 (英雄之旅/成长蜕变/复仇救赎)
    universalTheme: str  # 普世主题 (爱/勇气/自由/身份认同)
    emotionalArc: str  # 情感弧线模板
    targetResonance: str  # 目标共鸣点


class StoryThemePillar(TypedDict):
    """支柱 I 完整结构"""
    concrete: Optional[StoryThemeConcrete]
    abstract: Optional[StoryThemeAbstract]
    remixed: Optional[StoryThemeConcrete]  # 注入意图后的结果


# ============================================================
# 支柱 II: Narrative Template (骨架层)
# 对应前端 ScriptAnalysis
# ============================================================

class ScriptBasicInfo(TypedDict):
    """剧本基本信息"""
    scriptName: str
    typeStyle: str
    length: str
    creativeBackground: str


class ThemeIntent(TypedDict):
    """主题意图"""
    coreTheme: str
    subTheme: str
    valueStance: str


class StoryStructure(TypedDict):
    """故事结构"""
    storyWorld: str
    threeActStructure: str
    plotPoints: str
    endingType: str


class CharacterSystem(TypedDict):
    """人物系统"""
    protagonist: str
    antagonist: str
    supportingRoles: str
    relationships: str


class CharacterArc(TypedDict):
    """人物弧光"""
    initialState: str
    actionChanges: str
    finalState: str


class ConflictDesign(TypedDict):
    """冲突设计"""
    externalConflict: str
    internalConflict: str
    conflictEscalation: str


class PlotRhythm(TypedDict):
    """情节节奏"""
    sceneArrangement: str
    rhythmControl: str
    suspenseSetting: str


class DialogueAction(TypedDict):
    """对白与行为"""
    dialogueFunction: str
    subtext: str
    behaviorLogic: str


class SymbolMetaphor(TypedDict):
    """符号与隐喻"""
    coreImagery: str
    symbolicMeaning: str


class GenreStyle(TypedDict):
    """类型风格"""
    genreRules: str
    narrativeStyle: str


class VisualPotential(TypedDict):
    """视觉潜力"""
    visualSense: str
    audioVisualSpace: str


class OverallEvaluation(TypedDict):
    """整体评估"""
    strengths: str
    weaknesses: str
    revisionDirection: str


class NarrativeTemplateConcrete(TypedDict):
    """支柱 II: 具体层 - 对应前端 ScriptAnalysis"""
    basicInfo: ScriptBasicInfo
    themeIntent: ThemeIntent
    storyStructure: StoryStructure
    characterSystem: CharacterSystem
    characterArc: CharacterArc
    conflictDesign: ConflictDesign
    plotRhythm: PlotRhythm
    dialogueAction: DialogueAction
    symbolMetaphor: SymbolMetaphor
    genreStyle: GenreStyle
    visualPotential: VisualPotential
    overallEvaluation: OverallEvaluation


class BeatSheetItem(TypedDict):
    """节拍表项"""
    beatId: str  # HOOK/SETUP/CATALYST/TURN/CLIMAX/RESOLUTION
    function: str  # 叙事功能描述
    durationRatio: float  # 时长占比 (0-1)


class CharacterArchetypes(TypedDict):
    """人物原型"""
    protagonistType: str  # 普通人/反英雄/天选之人
    antagonistType: str  # 内心恐惧/外部势力/命运
    dynamic: str  # 核心动态关系


class NarrativeTemplateAbstract(TypedDict):
    """支柱 II: 抽象层 - 叙事逻辑模板"""
    structureTemplate: str  # 结构模板代号 (3ACT/5ACT/CIRCULAR)
    beatSheet: List[BeatSheetItem]  # 节拍表
    characterArchetypes: CharacterArchetypes  # 人物原型
    conflictPattern: str  # 冲突模式
    rhythmSignature: str  # 节奏特征


class HiddenAssets(TypedDict):
    """隐藏资产 - 用于 Stage 3 资产生成"""
    protagonist_detail: str  # 主角详细描述 (80-120 words)
    antagonist_detail: str  # 对手详细描述 (50-80 words)
    props_detail: str  # 关键道具描述


class NarrativeTemplatePillar(TypedDict):
    """支柱 II 完整结构"""
    concrete: Optional[NarrativeTemplateConcrete]
    abstract: Optional[NarrativeTemplateAbstract]
    remixed: Optional[NarrativeTemplateConcrete]
    hiddenAssets: Optional[HiddenAssets]  # 隐藏资产，不显示在前端表格


# ============================================================
# 支柱 III: Shot Recipe (肌肉层)
# 分镜配方 - 8 个核心字段
# ============================================================

class GlobalVisualLanguage(TypedDict):
    """全局视觉语言"""
    visualStyle: str
    colorPalette: str
    lightingDesign: str
    cameraPhilosophy: str


class GlobalSoundDesign(TypedDict):
    """全局声音设计"""
    musicStyle: str
    soundAtmosphere: str
    rhythmPattern: str


class ShotCinematography(TypedDict):
    """分镜摄影参数 - 对应前端 StoryboardShot"""
    shotSize: str  # 景别
    cameraAngle: str  # 角度
    cameraMovement: str  # 运镜
    focalLengthDepth: str  # 焦距与景深


class ShotAudio(TypedDict):
    """分镜音频"""
    soundDesign: str  # 声音设计 (环境音效)
    music: str  # BGM 描述
    dialogue: str  # 对白说明 (说话者/情绪)
    dialogueText: str  # 对白原文转录 (用于 Lip-sync)


class ShotRecipeItem(TypedDict):
    """单个分镜配方 - 核心字段"""
    shotId: str
    beatTag: str  # HOOK/SETUP/CATALYST/RISING/TURN/CLIMAX/FALLING/RESOLUTION
    startTime: str
    endTime: str
    durationSeconds: float
    representativeTimestamp: Optional[float]  # 🎯 AI 语义锚点 - 代表帧时间戳 (秒)
    longTake: bool  # 是否为长镜头 (>5s)

    # 核心字段
    firstFrameDescription: str  # 首帧描述 (Imagen 4.0 关键输入)
    subject: str  # 主体描述 (动作轨迹/情绪)
    scene: str  # 场景描述 (时间/地点/光影/氛围)
    camera: ShotCinematography  # 镜头语言
    lighting: str  # 光影配方
    dynamics: str  # 环境动态与物理特效
    audio: ShotAudio  # 声音/BGM/对白
    style: str  # 视觉风格与质感
    negative: str  # 负面约束

    # 资产路径
    assets: Dict[str, Optional[str]]


class ShotFunctionAbstract(TypedDict):
    """分镜功能抽象"""
    shotIndex: int
    narrativeFunction: str  # 叙事功能 (建立/推进/转折/释放)
    visualFunction: str  # 视觉功能 (展示/隐藏/对比/呼应)
    subjectPlaceholder: str  # [SUBJECT_A]/[SUBJECT_B]/[ENVIRONMENT]
    actionTemplate: str  # 动作模板 ([SUBJECT] moves toward [TARGET])
    cinematography: ShotCinematography  # 摄影参数 (必须保留)


class VisualGrammarTemplate(TypedDict):
    """视觉语法模板"""
    styleCategory: str  # REALISTIC/STYLIZED/MIXED
    moodBoardTags: List[str]
    referenceAesthetics: str


class ShotRecipeConcrete(TypedDict):
    """支柱 III: 具体层"""
    globalVisualLanguage: GlobalVisualLanguage
    globalSoundDesign: GlobalSoundDesign
    symbolism: Symbolism
    shots: List[ShotRecipeItem]


class ShotRecipeAbstract(TypedDict):
    """支柱 III: 抽象层"""
    visualGrammarTemplate: VisualGrammarTemplate
    shotFunctions: List[ShotFunctionAbstract]


class FirstFrameData(TypedDict):
    """首帧数据 - 用于 Imagen 4.0 生成"""
    shotId: str
    firstFrameDescription: str
    camera: ShotCinematography
    lighting: str
    style: str
    negative: str


class DialogueTimelineItem(TypedDict):
    """对白时间线项 - 用于 Lip-sync"""
    shotId: str
    startTime: str
    endTime: str
    durationSeconds: float
    dialogueText: str
    dialogueDelivery: str


class ShotRecipePillar(TypedDict):
    """支柱 III 完整结构"""
    concrete: Optional[ShotRecipeConcrete]
    abstract: Optional[ShotRecipeAbstract]
    remixed: Optional[ShotRecipeConcrete]
    firstFrames: Optional[List[FirstFrameData]]  # Imagen 4.0 首帧数据
    dialogueTimeline: Optional[List[DialogueTimelineItem]]  # Lip-sync 对白时间线


# ============================================================
# 支柱 IV: Render Strategy (执行层)
# 资产锚点 + 模型配置 + 生成链路
# ============================================================

class ThreeViews(TypedDict):
    """三视图资产"""
    front: Optional[str]
    side: Optional[str]
    back: Optional[str]


class VisualDNA(TypedDict):
    """角色视觉 DNA"""
    hair: str
    clothing: str
    features: str
    bodyType: str
    accessories: str


class CharacterAnchor(TypedDict):
    """角色锚点"""
    anchorId: str
    role: str  # protagonist/antagonist/supporting
    name: str
    description: str
    visualDNA: VisualDNA
    threeViews: ThreeViews
    status: str  # NOT_STARTED/GENERATING/SUCCESS/FAILED


class EnvironmentAnchor(TypedDict):
    """场景锚点"""
    anchorId: str
    type: str  # interior/exterior/abstract
    name: str
    description: str
    referenceImage: Optional[str]
    status: str


class IdentityAnchors(TypedDict):
    """身份锚点集合"""
    characters: List[CharacterAnchor]
    environments: List[EnvironmentAnchor]


class ModelConfig(TypedDict):
    """模型配置"""
    imageModel: str  # imagen-4.0
    videoModel: str  # veo-3.1
    upscaleEnabled: bool


class RetryPolicy(TypedDict):
    """重试策略"""
    maxAttempts: int
    fallbackModel: Optional[str]


class GenerationPipeline(TypedDict):
    """生成管线"""
    strategy: str  # PARALLEL/SEQUENTIAL
    retryPolicy: RetryPolicy


class ShotRenderRecipe(TypedDict):
    """单镜渲染配方"""
    shotId: str
    textToImagePrompt: str  # T2I Prompt
    imageToVideoPrompt: str  # I2V Prompt
    referenceAnchors: List[str]  # anchor_id 引用
    executionType: str  # I2V/LIP_SYNC
    status: str


class RenderStrategyPillar(TypedDict):
    """支柱 IV 完整结构"""
    identityAnchors: IdentityAnchors
    modelConfig: ModelConfig
    generationPipeline: GenerationPipeline
    shotRenderRecipes: List[ShotRenderRecipe]


# ============================================================
# 用户意图 (M4: Intent Injection)
# ============================================================

class SubjectMapping(TypedDict):
    """主体映射 - 1:1 或 1:N 替换"""
    fromPlaceholder: str  # [PROTAGONIST_A], [SUBJECT], etc.
    fromDescription: str  # 原始主体描述
    toDescription: str  # 新主体详细描述 (50-80 words)
    persistentAttributes: List[str]  # 持久属性 (红色披风, 金属外壳)
    imageReference: Optional[str]  # 参考图片路径
    affectedShots: List[str]  # ["all"] 或 ["shot_01", "shot_05"]


class EnvironmentMapping(TypedDict):
    """环境映射"""
    fromPlaceholder: str  # [SETTING]
    fromDescription: str  # 原始环境
    toDescription: str  # 新环境详细描述 (50-80 words)
    timeOfDay: str  # dawn | day | dusk | night | unchanged
    weather: str  # clear | rainy | snowy | foggy | unchanged
    affectedShots: List[str]


class StyleInstruction(TypedDict):
    """风格指令"""
    artStyle: Optional[str]  # LEGO, 赛博朋克, 水彩
    materialImplications: str  # 材质/纹理描述
    lightingImplications: str  # 光影设置
    colorPalette: Optional[str]


class MoodTone(TypedDict):
    """情绪基调"""
    originalMood: str
    targetMood: str
    intensityShift: str  # increase | decrease | maintain
    genreShift: Optional[str]


class PlotRestructure(TypedDict):
    """剧情重构"""
    enabled: bool
    themePreserved: bool
    newConflict: Optional[str]
    newClimax: Optional[str]
    newResolution: Optional[str]
    narrativeNotes: str


class PreservedElements(TypedDict):
    """保留元素"""
    beatTagsPreserved: bool
    cameraPreserved: bool
    rhythmPreserved: bool
    overrideReason: Optional[str]


class ComplianceCheck(TypedDict):
    """合规检查"""
    passedSafetyCheck: bool
    flaggedContent: List[str]
    aspectRatioLocked: str  # 16:9


class ParsedIntent(TypedDict):
    """解析后的意图 - M4 Intent Parser 输出"""
    parseSuccess: bool
    intentType: str  # ELEMENT_SWAP | STYLE_TRANSFER | PLOT_RESTRUCTURE | HYBRID
    scope: str  # GLOBAL | PARTIAL | SINGLE_ELEMENT

    subjectMapping: List[SubjectMapping]
    environmentMapping: List[EnvironmentMapping]
    styleInstruction: StyleInstruction
    moodTone: MoodTone
    plotRestructure: PlotRestructure
    preservedElements: PreservedElements
    complianceCheck: ComplianceCheck

    parsingConfidence: float
    ambiguities: List[str]


# ============================================================
# Remixed Identity Anchors (M4: Fusion 输出)
# ============================================================

class RemixedCharacterAnchor(TypedDict):
    """Remixed 角色锚点 - Stage 4 资产生成的唯一文本源"""
    anchorId: str  # char_01, char_02
    originalPlaceholder: str  # [PROTAGONIST_A]
    anchorName: str  # 人类可读名称
    detailedDescription: str  # 80-120 字极致细节描述
    persistentAttributes: List[str]
    imageReference: Optional[str]
    styleAdaptation: str  # 在目标风格下的外观


class RemixedEnvironmentAnchor(TypedDict):
    """Remixed 环境锚点"""
    anchorId: str  # env_01, env_02
    originalPlaceholder: str  # [SETTING]
    anchorName: str
    detailedDescription: str  # 80-120 字极致细节描述
    atmosphericConditions: str  # 光照/天气/时间
    styleAdaptation: str


class RemixedIdentityAnchors(TypedDict):
    """Remixed 身份锚点集合"""
    characters: List[RemixedCharacterAnchor]
    environments: List[RemixedEnvironmentAnchor]


# ============================================================
# Remixed Shot (M4: Fusion 输出)
# ============================================================

class RemixedShot(TypedDict):
    """Remixed 分镜 - 包含 T2I 和 I2V prompts"""
    shotId: str
    beatTag: str
    startTime: str
    endTime: str
    durationSeconds: float

    cameraPreserved: ShotCinematography  # 保留的摄影骨架

    T2I_FirstFrame: str  # Imagen 4.0 首帧生成 prompt (以 --ar 16:9 结尾)
    I2V_VideoGen: str  # Veo 3.1 视频生成 prompt (包含首帧继承条款)

    remixNotes: str  # 改动说明
    appliedAnchors: Dict[str, List[str]]  # {characters: [], environments: []}


class RemixedSummary(TypedDict):
    """Remix 摘要"""
    totalShots: int
    shotsModified: int
    primaryChanges: List[str]
    styleApplied: str
    moodShift: str
    preservedElements: List[str]


class RemixedLayer(TypedDict):
    """Remixed 层 - 存储融合结果"""
    identityAnchors: RemixedIdentityAnchors
    shots: List[RemixedShot]
    summary: RemixedSummary
    fusionTimestamp: str
    fusionSuccess: bool


class UserIntent(TypedDict):
    """用户意图 - M4 完整结构"""
    rawPrompt: Optional[str]  # 用户原始输入
    referenceImages: List[str]  # 参考图片路径列表
    parsedIntent: Optional[ParsedIntent]  # 解析后的结构化意图
    remixedLayer: Optional[RemixedLayer]  # 融合后的 remixed 数据
    injectedAt: Optional[str]  # ISO timestamp


# ============================================================
# Meta Prompts 注册表
# ============================================================

class MetaPromptsRegistry(TypedDict):
    """Meta Prompts 注册表 - 9 个核心 Prompt"""
    storyThemeAnalysis: Optional[str]  # 支柱 I 分析
    narrativeExtraction: Optional[str]  # 支柱 II 分析
    shotDecomposition: Optional[str]  # 支柱 III 分析
    abstractionEngine: Optional[str]  # 抽象化引擎
    intentFusion: Optional[str]  # 意图融合
    characterAnchorGen: Optional[str]  # 角色锚点生成
    environmentAnchorGen: Optional[str]  # 场景锚点生成
    t2iPromptComposer: Optional[str]  # T2I Prompt 组装
    i2vPromptComposer: Optional[str]  # I2V Prompt 组装


# ============================================================
# 阶段状态
# ============================================================

class FilmIRStages(TypedDict):
    """Film IR 阶段状态"""
    specificAnalysis: str  # 具体分析
    abstraction: str  # 逻辑抽象
    intentInjection: str  # 意图注入
    assetGeneration: str  # 资产生成
    shotRefinement: str  # 分镜精修
    execution: str  # 视频生成


# ============================================================
# 四大支柱聚合
# ============================================================

class FilmIRPillars(TypedDict):
    """四大支柱"""
    I_storyTheme: StoryThemePillar
    II_narrativeTemplate: NarrativeTemplatePillar
    III_shotRecipe: ShotRecipePillar
    IV_renderStrategy: RenderStrategyPillar


# ============================================================
# Film IR 完整结构
# ============================================================

class FilmIR(TypedDict):
    """Film IR 完整结构 - 电影逻辑中间层"""
    version: str
    jobId: str
    sourceVideo: str
    createdAt: str
    updatedAt: str

    stages: FilmIRStages
    pillars: FilmIRPillars
    userIntent: UserIntent
    metaPromptsRegistry: MetaPromptsRegistry


# ============================================================
# 工厂函数
# ============================================================

def create_empty_film_ir(job_id: str, source_video: str = "") -> Dict[str, Any]:
    """创建空的 Film IR 结构"""
    from datetime import datetime

    now = datetime.utcnow().isoformat() + "Z"

    return {
        "version": "1.0.0",
        "jobId": job_id,
        "sourceVideo": source_video,
        "createdAt": now,
        "updatedAt": now,

        "stages": {
            "specificAnalysis": "NOT_STARTED",
            "abstraction": "NOT_STARTED",
            "intentInjection": "NOT_STARTED",
            "assetGeneration": "NOT_STARTED",
            "shotRefinement": "NOT_STARTED",
            "execution": "NOT_STARTED"
        },

        "pillars": {
            "I_storyTheme": {
                "concrete": None,
                "abstract": None,
                "remixed": None
            },
            "II_narrativeTemplate": {
                "concrete": None,
                "abstract": None,
                "remixed": None,
                "hiddenAssets": None
            },
            "III_shotRecipe": {
                "concrete": None,
                "abstract": None,
                "remixed": None,
                "firstFrames": None,
                "dialogueTimeline": None
            },
            "IV_renderStrategy": {
                "identityAnchors": {
                    "characters": [],
                    "environments": []
                },
                "modelConfig": {
                    "imageModel": "imagen-4.0",
                    "videoModel": "veo-3.1",
                    "upscaleEnabled": False
                },
                "generationPipeline": {
                    "strategy": "SEQUENTIAL",
                    "retryPolicy": {
                        "maxAttempts": 3,
                        "fallbackModel": None
                    }
                },
                "shotRenderRecipes": []
            }
        },

        "userIntent": {
            "rawPrompt": None,
            "referenceImages": [],
            "parsedIntent": None,
            "remixedLayer": None,
            "injectedAt": None,
            "intentHistory": []  # 多轮意图修改历史记录
        },

        "metaPromptsRegistry": {
            "storyThemeAnalysis": None,
            "narrativeExtraction": None,
            "shotDecomposition": None,
            "abstractionEngine": None,
            "intentFusion": None,
            "characterAnchorGen": None,
            "environmentAnchorGen": None,
            "t2iPromptComposer": None,
            "i2vPromptComposer": None
        }
    }
