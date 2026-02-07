// lib/api.ts
// SocialSaver 前端 API 配置与调用函数

// 后端 API 基础 URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://g3videoagent-production.up.railway.app";

// ============================================================
// 类型定义
// ============================================================

export interface UploadResponse {
  status: string;
  job_id: string;
}

export interface JobStatus {
  jobId: string;
  totalShots: number;
  stylizedCount: number;
  videoGeneratedCount: number;
  runningCount: number;
  canMerge: boolean;
  globalStages: Record<string, string>;
  globalStyle: string;
}

export interface SocialSaverStoryboard {
  jobId: string;
  sourceVideo: string;
  globalStyle: string;
  storyboard: SocialSaverShot[];
  status: {
    analyze: string;
    stylize: string;
    videoGen: string;
    merge: string;
  };
}

export interface SocialSaverShot {
  shotNumber: number;
  firstFrameImage: string;
  visualDescription: string;
  contentDescription: string;
  startSeconds: number;
  endSeconds: number;
  durationSeconds: number;
  shotSize: string;
  cameraAngle: string;
  cameraMovement: string;
  focalLengthDepth: string;
  lighting: string;
  music: string;
  dialogueVoiceover: string;
}

export interface AgentChatResponse {
  action: any;
  result: {
    status: string;
    affected_shots?: number;
  };
}

// ============================================================
// API 调用函数
// ============================================================

/**
 * 上传视频并触发 AI 分析
 */
export async function uploadVideo(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

/**
 * 获取 SocialSaver 格式的分镜表
 */
export async function getStoryboard(jobId: string): Promise<SocialSaverStoryboard> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/storyboard`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch storyboard" }));
    throw new Error(error.detail || "Failed to fetch storyboard");
  }

  return response.json();
}

/**
 * 获取作业状态
 */
export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/status`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch status" }));
    throw new Error(error.detail || "Failed to fetch status");
  }

  return response.json();
}

/**
 * 获取原始 workflow（ReTake 格式）
 */
export async function getWorkflow(jobId?: string): Promise<any> {
  const url = jobId
    ? `${API_BASE_URL}/api/workflow?job_id=${jobId}`
    : `${API_BASE_URL}/api/workflow`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch workflow" }));
    throw new Error(error.detail || "Failed to fetch workflow");
  }

  return response.json();
}

/**
 * 发送 Agent 聊天消息（修改分镜、风格等）
 */
export async function sendAgentChat(message: string, jobId: string): Promise<AgentChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      job_id: jobId,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Chat request failed" }));
    throw new Error(error.detail || "Chat request failed");
  }

  return response.json();
}

/**
 * 运行任务节点（stylize, video_generate, merge）
 */
export async function runTask(
  nodeType: "stylize" | "video_generate" | "merge",
  jobId: string,
  shotId?: string
): Promise<{ status: string; job_id: string; file?: string }> {
  const params = new URLSearchParams();
  params.append("job_id", jobId);
  if (shotId) {
    params.append("shot_id", shotId);
  }

  const response = await fetch(`${API_BASE_URL}/api/run/${nodeType}?${params.toString()}`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Task failed" }));
    throw new Error(error.detail || "Task failed");
  }

  return response.json();
}

/**
 * 更新单个分镜
 */
export async function updateShot(
  jobId: string,
  shotId: string,
  description: string
): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/shot/update`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      job_id: jobId,
      shot_id: shotId,
      description,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Update failed" }));
    throw new Error(error.detail || "Update failed");
  }

  return response.json();
}

/**
 * 获取资源完整 URL
 */
export function getAssetUrl(jobId: string, assetPath: string): string {
  if (!assetPath) return "";
  // 如果已经是完整 URL，直接返回
  if (assetPath.startsWith("http")) return assetPath;
  // 构建完整 URL
  return `${API_BASE_URL}/assets/${jobId}/${assetPath}`;
}

/**
 * 获取 Film IR Story Theme 分析结果
 */
export async function getStoryTheme(jobId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/film_ir/story_theme`);

  if (!response.ok) {
    if (response.status === 404) {
      return null; // Story theme not ready yet
    }
    const error = await response.json().catch(() => ({ detail: "Failed to fetch story theme" }));
    throw new Error(error.detail || "Failed to fetch story theme");
  }

  return response.json();
}

/**
 * 获取 Film IR Narrative/Script Analysis 分析结果
 */
export async function getScriptAnalysis(jobId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/film_ir/narrative`);

  if (!response.ok) {
    if (response.status === 404) {
      return null; // Script analysis not ready yet
    }
    const error = await response.json().catch(() => ({ detail: "Failed to fetch script analysis" }));
    throw new Error(error.detail || "Failed to fetch script analysis");
  }

  return response.json();
}

/**
 * 轮询作业状态直到完成
 */
export async function pollJobStatus(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  intervalMs: number = 3000,
  maxAttempts: number = 200
): Promise<JobStatus> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await getJobStatus(jobId);
    onUpdate(status);

    // 检查是否所有任务都完成
    const allDone = status.runningCount === 0 &&
      (status.globalStages.analyze === "SUCCESS" || status.globalStages.analyze === "FAILED");

    if (allDone) {
      return status;
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error("Polling timeout");
}

// ============================================================
// M4: Intent Injection (Remix) API
// ============================================================

export interface RemixResponse {
  status: string;
  jobId: string;
  message: string;
  userPrompt: string;
  referenceImages: string[];
}

export interface RemixStatusResponse {
  jobId: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface RemixDiffEntry {
  shotId: string;
  beatTag: string;
  changes: { type: string; description: string }[];
  originalFirstFrame: string;
  remixedFirstFrame: string;
  remixNotes: string;
}

export interface RemixDiffResponse {
  jobId: string;
  hasDiff: boolean;
  diff: RemixDiffEntry[];
  summary: {
    totalShots: number;
    shotsModified: number;
    primaryChanges: string[];
    styleApplied: string | null;
    moodShift: string | null;
    preservedElements: string[];
  };
}

export interface T2IPrompt {
  shotId: string;
  prompt: string;
  cameraPreserved: {
    shotSize: string;
    cameraAngle: string;
    cameraMovement: string;
    focalLengthDepth: string;
  };
  appliedAnchors: {
    characters: string[];
    environments: string[];
  };
}

export interface I2VPrompt {
  shotId: string;
  prompt: string;
  durationSeconds: number;
  cameraPreserved: {
    shotSize: string;
    cameraAngle: string;
    cameraMovement: string;
    focalLengthDepth: string;
  };
  firstFrameInheritance: boolean;
}

export interface IdentityAnchor {
  anchorId: string;
  anchorName: string;
  detailedDescription: string;
  originalPlaceholder?: string;
  persistentAttributes?: string[];
  imageReference?: string | null;
  styleAdaptation?: string;
  atmosphericConditions?: string;
}

export interface RemixPromptsResponse {
  jobId: string;
  t2iPrompts: T2IPrompt[];
  i2vPrompts: I2VPrompt[];
  identityAnchors: {
    characters: IdentityAnchor[];
    environments: IdentityAnchor[];
  };
}

/**
 * 触发 Intent Injection (M4 Remix)
 */
export async function triggerRemix(
  jobId: string,
  prompt: string,
  referenceImages?: string[]
): Promise<RemixResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/remix`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt,
      reference_images: referenceImages || [],
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Remix failed" }));
    throw new Error(error.detail || "Remix failed");
  }

  return response.json();
}

/**
 * 获取 Remix 状态
 */
export async function getRemixStatus(jobId: string): Promise<RemixStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/remix/status`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch remix status" }));
    throw new Error(error.detail || "Failed to fetch remix status");
  }

  return response.json();
}

/**
 * 获取 Remix Diff (concrete vs remixed)
 */
export async function getRemixDiff(jobId: string): Promise<RemixDiffResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/remix/diff`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch remix diff" }));
    throw new Error(error.detail || "Failed to fetch remix diff");
  }

  return response.json();
}

/**
 * 获取 Remix Prompts (T2I/I2V)
 */
export async function getRemixPrompts(jobId: string): Promise<RemixPromptsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/remix/prompts`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch remix prompts" }));
    throw new Error(error.detail || "Failed to fetch remix prompts");
  }

  return response.json();
}

/**
 * 轮询 Remix 状态直到完成
 */
export async function pollRemixStatus(
  jobId: string,
  onUpdate: (status: RemixStatusResponse) => void,
  intervalMs: number = 2000,
  maxAttempts: number = 60
): Promise<RemixStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await getRemixStatus(jobId);
    onUpdate(status);

    if (status.status === "completed" || status.status === "failed") {
      return status;
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error("Remix polling timeout");
}

// ============================================================
// M5: Asset Generation API
// ============================================================

export interface AssetGenerationResponse {
  status: string;
  jobId: string;
  message: string;
  assetsToGenerate?: {
    characters: number;
    characterViews: number;
    environments: number;
    total: number;
  };
}

export interface AssetGenerationStatusResponse {
  jobId: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  result?: {
    status: string;
    message: string;
    generated: number;
    failed: number;
    total: number;
    assets_dir: string;
  };
  error?: string;
}

export interface CharacterAsset {
  anchorId: string;
  name: string;
  status: string;
  threeViews: {
    front: string | null;
    side: string | null;
    back: string | null;
  };
}

export interface EnvironmentAsset {
  anchorId: string;
  name: string;
  status: string;
  referenceImage: string | null;
}

export interface GeneratedAssetsResponse {
  jobId: string;
  assets: {
    characters: CharacterAsset[];
    environments: EnvironmentAsset[];
  };
  assetsDir: string;
}

/**
 * 触发资产生成 (M5)
 */
export async function triggerAssetGeneration(jobId: string): Promise<AssetGenerationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/generate-assets`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Asset generation failed" }));
    throw new Error(error.detail || "Asset generation failed");
  }

  return response.json();
}

/**
 * 获取资产生成状态
 */
export async function getAssetGenerationStatus(jobId: string): Promise<AssetGenerationStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/assets/status`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch asset status" }));
    throw new Error(error.detail || "Failed to fetch asset status");
  }

  return response.json();
}

/**
 * 获取已生成的资产
 */
export async function getGeneratedAssets(jobId: string): Promise<GeneratedAssetsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/assets`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch assets" }));
    throw new Error(error.detail || "Failed to fetch assets");
  }

  return response.json();
}

/**
 * 轮询资产生成状态直到完成
 */
export async function pollAssetGeneration(
  jobId: string,
  onUpdate: (status: AssetGenerationStatusResponse) => void,
  intervalMs: number = 3000,
  maxAttempts: number = 40
): Promise<AssetGenerationStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await getAssetGenerationStatus(jobId);
    onUpdate(status);

    if (status.status === "completed" || status.status === "failed" || status.status === "partial") {
      return status;
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error("Asset generation polling timeout");
}

// ============================================================
// Character Ledger API (角色清单)
// ============================================================

export interface CharacterEntity {
  entityId: string;
  entityType: string;
  importance: "PRIMARY" | "SECONDARY" | "BACKGROUND";
  displayName: string;
  visualSignature: string;
  detailedDescription: string;
  appearsInShots: string[];
  shotCount: number;
  trackingConfidence?: string;
  visualCues?: string[];
  bindingStatus?: "BOUND" | "UNBOUND";
  boundAsset?: {
    assetId: string;
    name: string;
    imageUrl?: string;
  } | null;
}

export interface EnvironmentEntity {
  entityId: string;
  entityType: string;
  importance: "PRIMARY" | "SECONDARY";
  displayName: string;
  visualSignature: string;
  detailedDescription: string;
  appearsInShots: string[];
  shotCount: number;
  bindingStatus?: "BOUND" | "UNBOUND";
  boundAsset?: {
    assetId: string;
    name: string;
    imageUrl?: string;
  } | null;
}

export interface CharacterLedgerResponse {
  jobId: string;
  characterLedger: CharacterEntity[];
  environmentLedger: EnvironmentEntity[];
  summary: {
    totalCharacters: number;
    primaryCharacters: number;
    secondaryCharacters: number;
    totalEnvironments: number;
  };
}

/**
 * 获取角色清单 (Character Ledger)
 */
export async function getCharacterLedger(jobId: string): Promise<CharacterLedgerResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/character-ledger`);

  if (!response.ok) {
    if (response.status === 404) {
      return {
        jobId,
        characterLedger: [],
        environmentLedger: [],
        summary: {
          totalCharacters: 0,
          primaryCharacters: 0,
          secondaryCharacters: 0,
          totalEnvironments: 0,
        },
      };
    }
    const error = await response.json().catch(() => ({ detail: "Failed to fetch character ledger" }));
    throw new Error(error.detail || "Failed to fetch character ledger");
  }

  return response.json();
}

/**
 * 绑定资产到实体
 */
export async function bindAssetToEntity(
  jobId: string,
  entityId: string,
  assetName: string,
  detailedDescription?: string,
  assetPath?: string
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/bind-asset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      entityId,
      assetType: assetPath ? "uploaded" : "generated",
      assetPath: assetPath || null,
      anchorId: `anchor_${entityId}`,
      anchorName: assetName,
      detailedDescription: detailedDescription || assetName,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to bind asset" }));
    throw new Error(error.detail || "Failed to bind asset");
  }

  return response.json();
}

/**
 * 解绑资产
 */
export async function unbindAsset(
  jobId: string,
  entityId: string
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/bind-asset/${entityId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to unbind asset" }));
    throw new Error(error.detail || "Failed to unbind asset");
  }

  return response.json();
}

// ============================================================
// M5.1: Single Entity Asset Management API (槽位级别操作)
// ============================================================

export interface EntityThreeViewSlot {
  url: string | null;
  status: "empty" | "uploaded" | "generating";
}

export interface EntityState {
  jobId: string;
  anchorId: string;
  name: string;
  description: string;
  entityType: "character" | "environment";
  threeViews: {
    [key: string]: EntityThreeViewSlot;
  };
}

export interface GenerateViewsResponse {
  status: string;
  anchorId: string;
  entityType?: string;
  missingViews?: string[];
  existingViews?: string[];
  message?: string;
}

export interface GenerateViewsStatusResponse {
  anchorId: string;
  status: "not_started" | "running" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  missing_views?: string[];
  results?: {
    [view: string]: {
      status: string;
      path: string | null;
    };
  };
  error?: string;
}

/**
 * 获取单个实体的状态（描述 + 三槽位）
 */
export async function getEntityState(jobId: string, anchorId: string): Promise<EntityState> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/entity/${anchorId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch entity state" }));
    throw new Error(error.detail || "Failed to fetch entity state");
  }

  return response.json();
}

/**
 * 更新实体描述
 */
export async function updateEntityDescription(
  jobId: string,
  anchorId: string,
  description: string
): Promise<{ status: string; anchorId: string; description: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/entity/${anchorId}/description`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ description }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to update description" }));
    throw new Error(error.detail || "Failed to update description");
  }

  return response.json();
}

/**
 * 上传图片到特定槽位
 */
export async function uploadEntityView(
  jobId: string,
  anchorId: string,
  view: string,
  file: File
): Promise<{ status: string; anchorId: string; view: string; filePath: string; url: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/upload-view/${anchorId}/${view}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to upload view" }));
    throw new Error(error.detail || "Failed to upload view");
  }

  return response.json();
}

/**
 * AI 生成缺失的槽位
 */
export async function generateEntityViews(
  jobId: string,
  anchorId: string,
  force: boolean = false
): Promise<GenerateViewsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/generate-views/${anchorId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ force }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to generate views" }));
    throw new Error(error.detail || "Failed to generate views");
  }

  return response.json();
}

/**
 * 获取生成状态
 */
export async function getGenerateViewsStatus(
  jobId: string,
  anchorId: string
): Promise<GenerateViewsStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/generate-views/${anchorId}/status`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch generation status" }));
    throw new Error(error.detail || "Failed to fetch generation status");
  }

  return response.json();
}

/**
 * 轮询生成状态直到完成
 */
export async function pollGenerateViewsStatus(
  jobId: string,
  anchorId: string,
  onUpdate: (status: GenerateViewsStatusResponse) => void,
  intervalMs: number = 3000,
  maxAttempts: number = 40
): Promise<GenerateViewsStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await getGenerateViewsStatus(jobId, anchorId);
    onUpdate(status);

    if (status.status === "completed" || status.status === "failed") {
      return status;
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error("Generation polling timeout");
}

// ============================================================
// Visual Style API (视觉风格配置)
// ============================================================

export interface VisualStyleConfig {
  artStyle: string;
  colorPalette: string;
  lightingMood: string;
  cameraStyle: string;
  referenceImages: string[];
  confirmed: boolean;
}

export interface VisualStyleResponse {
  jobId: string;
  visualStyle: VisualStyleConfig;
}

/**
 * 获取视觉风格配置
 */
export async function getVisualStyle(jobId: string): Promise<VisualStyleResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/visual-style`);

  if (!response.ok) {
    if (response.status === 404) {
      // Return default empty config if not found
      return {
        jobId,
        visualStyle: {
          artStyle: "",
          colorPalette: "",
          lightingMood: "",
          cameraStyle: "",
          referenceImages: [],
          confirmed: false,
        },
      };
    }
    const error = await response.json().catch(() => ({ detail: "Failed to fetch visual style" }));
    throw new Error(error.detail || "Failed to fetch visual style");
  }

  return response.json();
}

/**
 * 保存视觉风格配置
 */
export async function saveVisualStyle(
  jobId: string,
  config: Partial<VisualStyleConfig>
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/visual-style`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to save visual style" }));
    throw new Error(error.detail || "Failed to save visual style");
  }

  return response.json();
}

/**
 * 上传视觉参考图片
 */
export async function uploadReferenceImage(
  jobId: string,
  file: File
): Promise<{ status: string; url: string; index: number }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/visual-style/reference`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to upload reference image" }));
    throw new Error(error.detail || "Failed to upload reference image");
  }

  const result = await response.json();
  // Convert relative URL to full URL
  if (result.url && result.url.startsWith("/")) {
    result.url = `${API_BASE_URL}${result.url}`;
  }
  return result;
}

/**
 * 删除视觉参考图片
 */
export async function deleteReferenceImage(
  jobId: string,
  index: number
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/visual-style/reference/${index}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to delete reference image" }));
    throw new Error(error.detail || "Failed to delete reference image");
  }

  return response.json();
}

// ============================================================
// Product Three-Views API (产品三视图)
// ============================================================

export interface ProductThreeViews {
  front: string | null;
  side: string | null;
  back: string | null;
}

export interface ProductAnchor {
  anchorId: string;
  name: string;
  description: string;
  threeViews: ProductThreeViews;
  status: "NOT_STARTED" | "GENERATING" | "SUCCESS" | "FAILED";
}

export interface ProductsResponse {
  jobId: string;
  products: ProductAnchor[];
}

export interface ProductStateResponse {
  jobId: string;
  anchorId: string;
  name: string;
  description: string;
  threeViews: {
    front: { url: string | null; status: string };
    side: { url: string | null; status: string };
    back: { url: string | null; status: string };
  };
  generationStatus: string;
}

export interface ProductGenerationStatusResponse {
  anchorId: string;
  status: "not_started" | "running" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  results?: {
    [view: string]: {
      status: string;
      path: string | null;
    };
  };
  error?: string;
}

/**
 * 获取所有产品列表
 */
export async function getProducts(jobId: string): Promise<ProductsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products`);

  if (!response.ok) {
    if (response.status === 404) {
      return { jobId, products: [] };
    }
    const error = await response.json().catch(() => ({ detail: "Failed to fetch products" }));
    throw new Error(error.detail || "Failed to fetch products");
  }

  return response.json();
}

/**
 * 创建新产品
 */
export async function createProduct(
  jobId: string,
  name: string,
  description: string
): Promise<{ status: string; product: ProductAnchor }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name, description }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to create product" }));
    throw new Error(error.detail || "Failed to create product");
  }

  return response.json();
}

/**
 * 更新产品信息
 */
export async function updateProduct(
  jobId: string,
  anchorId: string,
  data: { name?: string; description?: string }
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products/${anchorId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to update product" }));
    throw new Error(error.detail || "Failed to update product");
  }

  return response.json();
}

/**
 * 删除产品
 */
export async function deleteProduct(
  jobId: string,
  anchorId: string
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products/${anchorId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to delete product" }));
    throw new Error(error.detail || "Failed to delete product");
  }

  return response.json();
}

/**
 * 获取产品详细状态
 */
export async function getProductState(jobId: string, anchorId: string): Promise<ProductStateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products/${anchorId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch product state" }));
    throw new Error(error.detail || "Failed to fetch product state");
  }

  return response.json();
}

/**
 * 上传产品视图图片
 */
export async function uploadProductView(
  jobId: string,
  anchorId: string,
  view: "front" | "side" | "back",
  file: File
): Promise<{ status: string; anchorId: string; view: string; filePath: string; url: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products/${anchorId}/upload/${view}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to upload product view" }));
    throw new Error(error.detail || "Failed to upload product view");
  }

  const result = await response.json();
  // Convert relative URL to full URL
  if (result.url && result.url.startsWith("/")) {
    result.url = `${API_BASE_URL}${result.url}`;
  }
  return result;
}

/**
 * AI 生成产品三视图
 */
export async function generateProductViews(
  jobId: string,
  anchorId: string,
  force: boolean = false
): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/products/${anchorId}/generate-views`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ force }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to generate product views" }));
    throw new Error(error.detail || "Failed to generate product views");
  }

  return response.json();
}

/**
 * 获取产品生成状态 (使用通用的生成状态端点)
 */
export async function getProductGenerationStatus(
  jobId: string,
  anchorId: string
): Promise<ProductGenerationStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/generate-views/${anchorId}/status`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to fetch product generation status" }));
    throw new Error(error.detail || "Failed to fetch product generation status");
  }

  return response.json();
}

/**
 * 轮询产品生成状态直到完成
 */
export async function pollProductGenerationStatus(
  jobId: string,
  anchorId: string,
  onUpdate: (status: ProductGenerationStatusResponse) => void,
  intervalMs: number = 3000,
  maxAttempts: number = 40
): Promise<ProductGenerationStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await getProductGenerationStatus(jobId, anchorId);
    onUpdate(status);

    if (status.status === "completed" || status.status === "failed") {
      return status;
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error("Product generation polling timeout");
}

// ============================================================
// M6: Remix Storyboard API
// ============================================================

export interface RemixStoryboardShot {
  shotNumber: number;
  shotId: string;
  firstFrameImage: string;
  visualDescription: string;
  contentDescription: string;
  startSeconds: number;
  endSeconds: number;
  durationSeconds: number;
  shotSize: string;
  cameraAngle: string;
  cameraMovement: string;
  focalLengthDepth: string;
  lighting: string;
  music: string;
  dialogueVoiceover: string;
  i2vPrompt: string;
  appliedAnchors: {
    characters: string[];
    environments: string[];
  };
}

export interface RemixStoryboardResponse {
  jobId: string;
  storyboard: RemixStoryboardShot[];
  totalDuration: number;
  remixContext: {
    identityAnchors: {
      characters: IdentityAnchor[];
      environments: IdentityAnchor[];
    };
    visualStyle: VisualStyleConfig;
    shotCount: number;
  };
}

export interface StoryboardChatResponse {
  updatedStoryboard: RemixStoryboardShot[];
  affectedShots: number[];
  response: string;
  action: "parameter_change" | "regenerate_prompt" | "info_query";
  totalDuration: number;
}

/**
 * 生成 Remix Storyboard
 */
export async function generateRemixStoryboard(jobId: string): Promise<RemixStoryboardResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/generate-remix-storyboard`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to generate remix storyboard" }));
    throw new Error(error.detail || "Failed to generate remix storyboard");
  }

  return response.json();
}

/**
 * Storyboard AI Chat - 自然语言修改分镜
 */
export async function storyboardChat(
  jobId: string,
  message: string,
  currentStoryboard: RemixStoryboardShot[]
): Promise<StoryboardChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/storyboard/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      currentStoryboard,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Storyboard chat failed" }));
    throw new Error(error.detail || "Storyboard chat failed");
  }

  return response.json();
}

export interface RegenerateFramesResponse {
  jobId: string;
  regeneratedShots: RemixStoryboardShot[];
  count: number;
}

/**
 * 重新生成指定分镜的首帧图片
 */
export async function regenerateStoryboardFrames(
  jobId: string,
  shots: RemixStoryboardShot[]
): Promise<RegenerateFramesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/job/${jobId}/storyboard/regenerate-frames`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ shots }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Frame regeneration failed" }));
    throw new Error(error.detail || "Frame regeneration failed");
  }

  return response.json();
}
