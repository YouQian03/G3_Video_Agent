"use client"

import React from "react"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  User,
  MapPin,
  Upload,
  Check,
  X,
  ImageIcon,
  CheckCircle,
  Sparkles,
  Loader2
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { CharacterView, SceneView } from "@/lib/types/remix"
import {
  uploadEntityView,
  updateEntityDescription,
  generateEntityViews,
  pollGenerateViewsStatus,
  getEntityState,
  type EntityState,
} from "@/lib/api"

// Character/Environment Entity from Character Ledger (Video Analysis)
interface LedgerEntity {
  entityId: string;
  entityType: string;
  importance: "PRIMARY" | "SECONDARY" | "BACKGROUND";
  displayName: string;
  visualSignature: string;
  detailedDescription: string;
  appearsInShots: string[];
  shotCount: number;
}

// Identity Anchor from Remix (overrides)
interface IdentityAnchor {
  anchorId: string;
  anchorName?: string;
  name?: string;
  detailedDescription?: string;
  originalPlaceholder?: string;  // Maps to original entityId
  styleAdaptation?: string;
  atmosphericConditions?: string;
}

interface CharacterSceneViewsProps {
  jobId: string
  // Data from Video Analysis (Character Ledger) - provides complete list
  characterLedger: LedgerEntity[]
  environmentLedger: LedgerEntity[]
  // Data from Remix (Identity Anchors) - provides overrides
  characterAnchors: IdentityAnchor[]
  environmentAnchors: IdentityAnchor[]
  characters: CharacterView[]
  scenes: SceneView[]
  onCharactersChange: (characters: CharacterView[]) => void
  onScenesChange: (scenes: SceneView[]) => void
  onConfirm: () => void
  onBack: () => void
}

function ViewUploadSlot({
  label,
  imageUrl,
  isLoading,
  onUpload,
  disabled
}: {
  label: string
  imageUrl?: string | null
  isLoading?: boolean
  onUpload: (file: File) => void
  disabled?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleClick = () => {
    if (!disabled && !isLoading) {
      inputRef.current?.click()
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onUpload(file)
    }
    // Reset input
    if (inputRef.current) {
      inputRef.current.value = ""
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || isLoading}
        className={cn(
          "w-24 h-32 rounded-lg border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-all",
          imageUrl
            ? "border-accent bg-accent/10"
            : "border-border hover:border-accent hover:bg-secondary/50",
          (disabled || isLoading) && "opacity-50 cursor-not-allowed"
        )}
      >
        {isLoading ? (
          <Loader2 className="w-6 h-6 text-accent animate-spin" />
        ) : imageUrl ? (
          <img
            src={imageUrl}
            alt={label}
            className="w-full h-full object-cover rounded-lg"
          />
        ) : (
          <>
            <ImageIcon className="w-6 h-6 text-muted-foreground" />
            <Upload className="w-4 h-4 text-muted-foreground" />
          </>
        )}
      </button>
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={handleChange}
        className="hidden"
      />
    </div>
  )
}

function CharacterCard({
  jobId,
  anchorId,
  character,
  onUpdate,
}: {
  jobId: string
  anchorId: string
  character: CharacterView
  onUpdate: (updates: Partial<CharacterView>) => void
}) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [uploadingView, setUploadingView] = useState<string | null>(null)
  const [isSavingDescription, setIsSavingDescription] = useState(false)
  const [localDescription, setLocalDescription] = useState(character.description)

  // Sync local description when character changes
  useEffect(() => {
    setLocalDescription(character.description)
  }, [character.description])

  const handleImageUpload = async (view: 'front' | 'side' | 'back', file: File) => {
    setUploadingView(view)
    try {
      const result = await uploadEntityView(jobId, anchorId, view, file)
      // Map backend view names to frontend property names
      const viewMap: Record<string, string> = {
        front: 'frontView',
        side: 'sideView',
        back: 'backView'
      }
      onUpdate({ [viewMap[view]]: result.url })
    } catch (error) {
      console.error("Upload failed:", error)
    } finally {
      setUploadingView(null)
    }
  }

  const handleDescriptionBlur = async () => {
    if (localDescription !== character.description) {
      setIsSavingDescription(true)
      try {
        await updateEntityDescription(jobId, anchorId, localDescription)
        onUpdate({ description: localDescription })
      } catch (error) {
        console.error("Failed to save description:", error)
      } finally {
        setIsSavingDescription(false)
      }
    }
  }

  const handleAIGenerate = async (forceRegenerate: boolean = false) => {
    setIsGenerating(true)
    try {
      // Always save description first (ensures latest description is used)
      await updateEntityDescription(jobId, anchorId, localDescription)
      onUpdate({ description: localDescription })

      // Trigger AI generation (with force if regenerating)
      const result = await generateEntityViews(jobId, anchorId, forceRegenerate)

      if (result.status === "already_complete" && !forceRegenerate) {
        onUpdate({ confirmed: true })
        setIsGenerating(false)
        return
      }

      // Poll for completion
      await pollGenerateViewsStatus(
        jobId,
        anchorId,
        (status) => {
          console.log("Generation status:", status.status)
        },
        3000,
        40
      )

      // Fetch updated state (add cache buster to get fresh images)
      const updatedState = await getEntityState(jobId, anchorId)
      const cacheBuster = `?t=${Date.now()}`
      onUpdate({
        frontView: updatedState.threeViews.front?.url ? updatedState.threeViews.front.url + cacheBuster : undefined,
        sideView: updatedState.threeViews.side?.url ? updatedState.threeViews.side.url + cacheBuster : undefined,
        backView: updatedState.threeViews.back?.url ? updatedState.threeViews.back.url + cacheBuster : undefined,
        confirmed: true
      })
    } catch (error) {
      console.error("AI generation failed:", error)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleConfirm = () => {
    onUpdate({ confirmed: true })
  }

  const allViewsFilled = character.frontView && character.sideView && character.backView

  return (
    <Card className={cn(
      "bg-card border-border transition-all",
      character.confirmed && "border-accent/50"
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <User className="w-5 h-5 text-accent" />
            <CardTitle className="text-base text-foreground">{character.name}</CardTitle>
            {character.confirmed && (
              <CheckCircle className="w-4 h-4 text-accent" />
            )}
          </div>
          <span className="text-xs text-muted-foreground font-mono">{anchorId}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Three View Slots */}
        <div className="flex justify-center gap-4">
          <ViewUploadSlot
            label="Front"
            imageUrl={character.frontView}
            isLoading={uploadingView === 'front'}
            disabled={isGenerating}
            onUpload={(file) => handleImageUpload('front', file)}
          />
          <ViewUploadSlot
            label="Side"
            imageUrl={character.sideView}
            isLoading={uploadingView === 'side'}
            disabled={isGenerating}
            onUpload={(file) => handleImageUpload('side', file)}
          />
          <ViewUploadSlot
            label="Back"
            imageUrl={character.backView}
            isLoading={uploadingView === 'back'}
            disabled={isGenerating}
            onUpload={(file) => handleImageUpload('back', file)}
          />
        </div>

        {/* Description */}
        <Textarea
          value={localDescription}
          onChange={(e) => setLocalDescription(e.target.value)}
          onBlur={handleDescriptionBlur}
          placeholder="Character description for AI generation..."
          className="bg-secondary border-border text-foreground min-h-[80px] text-sm"
          disabled={isGenerating}
        />

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleAIGenerate(!!allViewsFilled)}
            disabled={isGenerating || !localDescription.trim()}
            className="border-accent text-accent hover:bg-accent/10 bg-transparent"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                Generating...
              </>
            ) : allViewsFilled ? (
              <>
                <Sparkles className="w-4 h-4 mr-1" />
                Regenerate
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-1" />
                AI Generate
              </>
            )}
          </Button>
          {allViewsFilled && !character.confirmed && (
            <Button
              size="sm"
              onClick={handleConfirm}
              className="bg-accent text-accent-foreground hover:bg-accent/90"
            >
              <Check className="w-4 h-4 mr-1" />
              Confirm
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function SceneCard({
  jobId,
  anchorId,
  scene,
  onUpdate,
}: {
  jobId: string
  anchorId: string
  scene: SceneView
  onUpdate: (updates: Partial<SceneView>) => void
}) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [uploadingView, setUploadingView] = useState<string | null>(null)
  const [isSavingDescription, setIsSavingDescription] = useState(false)
  const [localDescription, setLocalDescription] = useState(scene.description)

  // Sync local description when scene changes
  useEffect(() => {
    setLocalDescription(scene.description)
  }, [scene.description])

  const handleImageUpload = async (view: 'wide' | 'detail' | 'alt', file: File) => {
    setUploadingView(view)
    try {
      const result = await uploadEntityView(jobId, anchorId, view, file)
      // Map backend view names to frontend property names
      const viewMap: Record<string, string> = {
        wide: 'establishingShot',
        detail: 'detailView',
        alt: 'alternateAngle'
      }
      onUpdate({ [viewMap[view]]: result.url })
    } catch (error) {
      console.error("Upload failed:", error)
    } finally {
      setUploadingView(null)
    }
  }

  const handleDescriptionBlur = async () => {
    if (localDescription !== scene.description) {
      setIsSavingDescription(true)
      try {
        await updateEntityDescription(jobId, anchorId, localDescription)
        onUpdate({ description: localDescription })
      } catch (error) {
        console.error("Failed to save description:", error)
      } finally {
        setIsSavingDescription(false)
      }
    }
  }

  const handleAIGenerate = async (forceRegenerate: boolean = false) => {
    setIsGenerating(true)
    try {
      // Always save description first (ensures latest description is used)
      await updateEntityDescription(jobId, anchorId, localDescription)
      onUpdate({ description: localDescription })

      // Trigger AI generation (with force if regenerating)
      const result = await generateEntityViews(jobId, anchorId, forceRegenerate)

      if (result.status === "already_complete" && !forceRegenerate) {
        onUpdate({ confirmed: true })
        setIsGenerating(false)
        return
      }

      // Poll for completion
      await pollGenerateViewsStatus(
        jobId,
        anchorId,
        (status) => {
          console.log("Generation status:", status.status)
        },
        3000,
        40
      )

      // Fetch updated state (add cache buster to get fresh images)
      const updatedState = await getEntityState(jobId, anchorId)
      const cacheBuster = `?t=${Date.now()}`
      onUpdate({
        establishingShot: updatedState.threeViews.wide?.url ? updatedState.threeViews.wide.url + cacheBuster : undefined,
        detailView: updatedState.threeViews.detail?.url ? updatedState.threeViews.detail.url + cacheBuster : undefined,
        alternateAngle: updatedState.threeViews.alt?.url ? updatedState.threeViews.alt.url + cacheBuster : undefined,
        confirmed: true
      })
    } catch (error) {
      console.error("AI generation failed:", error)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleConfirm = () => {
    onUpdate({ confirmed: true })
  }

  const allViewsFilled = scene.establishingShot && scene.detailView && scene.alternateAngle

  return (
    <Card className={cn(
      "bg-card border-border transition-all",
      scene.confirmed && "border-accent/50"
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-accent" />
            <CardTitle className="text-base text-foreground">{scene.name}</CardTitle>
            {scene.confirmed && (
              <CheckCircle className="w-4 h-4 text-accent" />
            )}
          </div>
          <span className="text-xs text-muted-foreground font-mono">{anchorId}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Three View Slots */}
        <div className="flex justify-center gap-4">
          <ViewUploadSlot
            label="Wide"
            imageUrl={scene.establishingShot}
            isLoading={uploadingView === 'wide'}
            disabled={isGenerating}
            onUpload={(file) => handleImageUpload('wide', file)}
          />
          <ViewUploadSlot
            label="Detail"
            imageUrl={scene.detailView}
            isLoading={uploadingView === 'detail'}
            disabled={isGenerating}
            onUpload={(file) => handleImageUpload('detail', file)}
          />
          <ViewUploadSlot
            label="Alt"
            imageUrl={scene.alternateAngle}
            isLoading={uploadingView === 'alt'}
            disabled={isGenerating}
            onUpload={(file) => handleImageUpload('alt', file)}
          />
        </div>

        {/* Description */}
        <Textarea
          value={localDescription}
          onChange={(e) => setLocalDescription(e.target.value)}
          onBlur={handleDescriptionBlur}
          placeholder="Scene description for AI generation..."
          className="bg-secondary border-border text-foreground min-h-[80px] text-sm"
          disabled={isGenerating}
        />

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleAIGenerate(!!allViewsFilled)}
            disabled={isGenerating || !localDescription.trim()}
            className="border-accent text-accent hover:bg-accent/10 bg-transparent"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                Generating...
              </>
            ) : allViewsFilled ? (
              <>
                <Sparkles className="w-4 h-4 mr-1" />
                Regenerate
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-1" />
                AI Generate
              </>
            )}
          </Button>
          {allViewsFilled && !scene.confirmed && (
            <Button
              size="sm"
              onClick={handleConfirm}
              className="bg-accent text-accent-foreground hover:bg-accent/90"
            >
              <Check className="w-4 h-4 mr-1" />
              Confirm
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// Helper function to find matching anchor for a ledger entity
function findMatchingAnchor(
  entity: LedgerEntity,
  anchors: IdentityAnchor[]
): IdentityAnchor | undefined {
  // First try to match by originalPlaceholder -> entityId
  const byPlaceholder = anchors.find(
    (anchor) => anchor.originalPlaceholder === entity.entityId
  )
  if (byPlaceholder) return byPlaceholder

  // Fallback: match by name similarity (case-insensitive contains)
  const entityNameLower = entity.displayName.toLowerCase()
  const byName = anchors.find((anchor) => {
    const anchorName = (anchor.anchorName || anchor.name || "").toLowerCase()
    return (
      anchorName.includes(entityNameLower) ||
      entityNameLower.includes(anchorName) ||
      anchorName === entityNameLower
    )
  })
  return byName
}

export function CharacterSceneViews({
  jobId,
  characterLedger,
  environmentLedger,
  characterAnchors,
  environmentAnchors,
  characters,
  scenes,
  onCharactersChange,
  onScenesChange,
  onConfirm,
  onBack,
}: CharacterSceneViewsProps) {
  // Initialize characters: Ledger (complete list) + Anchors (overrides)
  // Merge logic: All entities from ledger are shown, anchors provide description updates
  useEffect(() => {
    if (characters.length === 0 && characterLedger.length > 0) {
      const initialChars: CharacterView[] = characterLedger.map((entity) => {
        // Check if there's a matching anchor with updated description
        const matchingAnchor = findMatchingAnchor(entity, characterAnchors)

        // Use anchor's description if available (remix override), otherwise use ledger's
        const description = matchingAnchor?.detailedDescription
          || entity.detailedDescription
          || entity.visualSignature
          || ""

        // Use anchor's name if available (for renamed characters)
        const displayName = matchingAnchor?.anchorName
          || matchingAnchor?.name
          || entity.displayName

        // Use anchor ID if matched, otherwise use entity ID
        const id = matchingAnchor?.anchorId || entity.entityId

        return {
          id,
          name: displayName,
          description,
          frontView: undefined,
          sideView: undefined,
          backView: undefined,
          confirmed: false,
        }
      })
      onCharactersChange(initialChars)
    }
  }, [characterLedger, characterAnchors, characters.length, onCharactersChange])

  // Initialize scenes: Ledger (complete list) + Anchors (overrides)
  // Merge logic: All environments from ledger are shown, anchors provide style/description updates
  useEffect(() => {
    if (scenes.length === 0 && environmentLedger.length > 0) {
      const initialScenes: SceneView[] = environmentLedger.map((entity) => {
        // Check if there's a matching anchor with updated description
        const matchingAnchor = findMatchingAnchor(entity, environmentAnchors)

        // For environments, anchors may have styleAdaptation or atmosphericConditions
        // Combine these with the original description if present
        let description = entity.detailedDescription || entity.visualSignature || ""

        if (matchingAnchor) {
          // If anchor has a detailed description, use it as the primary description
          if (matchingAnchor.detailedDescription) {
            description = matchingAnchor.detailedDescription
          }
          // Append style adaptation if present
          if (matchingAnchor.styleAdaptation) {
            description = `${description}\n\nStyle: ${matchingAnchor.styleAdaptation}`
          }
          // Append atmospheric conditions if present
          if (matchingAnchor.atmosphericConditions) {
            description = `${description}\n\nAtmosphere: ${matchingAnchor.atmosphericConditions}`
          }
        }

        // Use anchor's name if available
        const displayName = matchingAnchor?.anchorName
          || matchingAnchor?.name
          || entity.displayName

        // Use anchor ID if matched, otherwise use entity ID
        const id = matchingAnchor?.anchorId || entity.entityId

        return {
          id,
          name: displayName,
          description: description.trim(),
          establishingShot: undefined,
          detailView: undefined,
          alternateAngle: undefined,
          confirmed: false,
        }
      })
      onScenesChange(initialScenes)
    }
  }, [environmentLedger, environmentAnchors, scenes.length, onScenesChange])

  const updateCharacter = (id: string, updates: Partial<CharacterView>) => {
    onCharactersChange(
      characters.map((c) => (c.id === id ? { ...c, ...updates } : c))
    )
  }

  const updateScene = (id: string, updates: Partial<SceneView>) => {
    onScenesChange(
      scenes.map((s) => (s.id === id ? { ...s, ...updates } : s))
    )
  }

  const allConfirmed =
    characters.length > 0 &&
    characters.every((c) => c.confirmed) &&
    (scenes.length === 0 || scenes.every((s) => s.confirmed))

  const hasAnyContent = characters.length > 0 || scenes.length > 0

  return (
    <div className="space-y-8">
      {/* Introduction */}
      <Card className="bg-accent/10 border-accent">
        <CardContent className="py-4">
          <p className="text-sm text-foreground">
            Upload or AI-generate three-view reference images for characters and scenes.
            You can upload your own images, or click &quot;AI Generate&quot; to create them automatically.
            Missing views will be generated based on uploaded images and descriptions.
          </p>
        </CardContent>
      </Card>

      {/* Characters Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <User className="w-5 h-5 text-accent" />
            Character Three-Views
            <span className="text-sm font-normal text-muted-foreground">
              ({characters.filter(c => c.confirmed).length}/{characters.length} confirmed)
            </span>
          </h3>
        </div>

        {characters.length === 0 ? (
          <Card className="bg-card border-border border-dashed">
            <CardContent className="py-8 flex flex-col items-center justify-center text-center">
              <User className="w-12 h-12 text-muted-foreground mb-3" />
              <p className="text-muted-foreground">No characters from remix</p>
              <p className="text-xs text-muted-foreground mt-1">
                Characters will appear here after remix script generation
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {characters.map((character) => (
              <CharacterCard
                key={character.id}
                jobId={jobId}
                anchorId={character.id}
                character={character}
                onUpdate={(updates) => updateCharacter(character.id, updates)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Scenes Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <MapPin className="w-5 h-5 text-accent" />
            Scene Three-Views
            <span className="text-sm font-normal text-muted-foreground">
              ({scenes.filter(s => s.confirmed).length}/{scenes.length} confirmed)
            </span>
          </h3>
        </div>

        {scenes.length === 0 ? (
          <Card className="bg-card border-border border-dashed">
            <CardContent className="py-8 flex flex-col items-center justify-center text-center">
              <MapPin className="w-12 h-12 text-muted-foreground mb-3" />
              <p className="text-muted-foreground">No scenes from remix</p>
              <p className="text-xs text-muted-foreground mt-1">
                Scenes will appear here after remix script generation
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {scenes.map((scene) => (
              <SceneCard
                key={scene.id}
                jobId={jobId}
                anchorId={scene.id}
                scene={scene}
                onUpdate={(updates) => updateScene(scene.id, updates)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-border">
        <Button
          variant="outline"
          onClick={onBack}
          className="border-border text-foreground hover:bg-secondary bg-transparent"
        >
          Back to Script
        </Button>
        <div className="flex-1" />
        {!allConfirmed && hasAnyContent && (
          <Button
            variant="outline"
            onClick={onConfirm}
            className="border-border text-foreground hover:bg-secondary bg-transparent"
          >
            Skip & Generate Storyboard
          </Button>
        )}
        <Button
          onClick={onConfirm}
          disabled={!hasAnyContent}
          className="bg-accent text-accent-foreground hover:bg-accent/90"
        >
          <Check className="w-4 h-4 mr-2" />
          {allConfirmed ? "Confirm & Generate Storyboard" : "Confirm Views"}
        </Button>
      </div>
    </div>
  )
}
