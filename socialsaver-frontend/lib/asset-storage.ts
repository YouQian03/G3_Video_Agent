// lib/asset-storage.ts
// Asset Library localStorage persistence

import type { Asset, AssetType, StoryThemeAnalysis, ScriptAnalysis, StoryboardShot } from "./types/remix"

const STORAGE_KEY = "socialsaver_asset_library"

/**
 * Get all assets from localStorage
 */
export function getAssets(): Asset[] {
  if (typeof window === "undefined") return []

  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    return JSON.parse(stored)
  } catch (e) {
    console.error("Failed to load assets from localStorage:", e)
    return []
  }
}

/**
 * Save all assets to localStorage
 */
export function saveAssets(assets: Asset[]): void {
  if (typeof window === "undefined") return

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(assets))
  } catch (e) {
    console.error("Failed to save assets to localStorage:", e)
  }
}

/**
 * Add a new asset to the library
 */
export function addAsset(asset: Omit<Asset, "id" | "createdAt" | "updatedAt">): Asset {
  const assets = getAssets()

  const newAsset: Asset = {
    ...asset,
    id: `asset_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  } as Asset

  assets.unshift(newAsset) // Add to beginning
  saveAssets(assets)

  return newAsset
}

/**
 * Update an existing asset
 */
export function updateAsset(id: string, updates: Partial<Asset>): Asset | null {
  const assets = getAssets()
  const index = assets.findIndex(a => a.id === id)

  if (index === -1) return null

  assets[index] = {
    ...assets[index],
    ...updates,
    updatedAt: new Date().toISOString(),
  }

  saveAssets(assets)
  return assets[index]
}

/**
 * Delete an asset
 */
export function deleteAsset(id: string): boolean {
  const assets = getAssets()
  const filtered = assets.filter(a => a.id !== id)

  if (filtered.length === assets.length) return false

  saveAssets(filtered)
  return true
}

/**
 * Get a single asset by ID
 */
export function getAssetById(id: string): Asset | null {
  const assets = getAssets()
  return assets.find(a => a.id === id) || null
}

/**
 * Helper: Save a storyboard analysis result to library
 */
export function saveStoryboardToLibrary(
  name: string,
  tags: string[],
  data: {
    storyTheme?: StoryThemeAnalysis
    scriptAnalysis?: ScriptAnalysis
    storyboard?: StoryboardShot[]
  },
  sourceVideo?: { name: string; size: number; url?: string }
): Asset {
  return addAsset({
    name,
    type: "storyboard",
    tags,
    data,
    sourceVideo,
  } as Omit<Asset, "id" | "createdAt" | "updatedAt">)
}

/**
 * Helper: Save a single storyboard shot to library
 */
export function saveShotToLibrary(
  name: string,
  tags: string[],
  shot: StoryboardShot,
  sourceVideo?: { name: string; size: number; url?: string }
): Asset {
  return addAsset({
    name,
    type: "storyboard",
    tags,
    data: shot,
    sourceVideo,
    thumbnail: shot.firstFrameImage,
  } as Omit<Asset, "id" | "createdAt" | "updatedAt">)
}

/**
 * Helper: Save a theme analysis to library
 */
export function saveThemeToLibrary(
  name: string,
  tags: string[],
  data: StoryThemeAnalysis,
  sourceVideo?: { name: string; size: number; url?: string }
): Asset {
  return addAsset({
    name,
    type: "theme",
    tags,
    data,
    sourceVideo,
  } as Omit<Asset, "id" | "createdAt" | "updatedAt">)
}

/**
 * Helper: Save a script analysis to library
 */
export function saveScriptToLibrary(
  name: string,
  tags: string[],
  data: ScriptAnalysis,
  sourceVideo?: { name: string; size: number; url?: string }
): Asset {
  return addAsset({
    name,
    type: "script",
    tags,
    data,
    sourceVideo,
  } as Omit<Asset, "id" | "createdAt" | "updatedAt">)
}

/**
 * Helper: Save a generated video to library
 */
export function saveVideoToLibrary(
  name: string,
  tags: string[],
  videoData: { url: string; duration: number; format: string; resolution: string },
  sourceVideo?: { name: string; size: number; url?: string }
): Asset {
  return addAsset({
    name,
    type: "video",
    tags,
    data: videoData,
    sourceVideo,
    thumbnail: undefined, // Could add video thumbnail later
  } as Omit<Asset, "id" | "createdAt" | "updatedAt">)
}
