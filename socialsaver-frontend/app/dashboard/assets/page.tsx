"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Search,
  Filter,
  Grid3X3,
  List,
  Film,
  User,
  FileText,
  Palette,
  Video,
  MoreVertical,
  Download,
  Trash2,
  Eye,
  FolderOpen,
  ArrowLeft,
  Play,
} from "lucide-react"
import { StoryThemeTable } from "@/components/remix/story-theme-table"
import { ScriptAnalysisTable } from "@/components/remix/script-analysis-table"
import { StoryboardTable } from "@/components/remix/storyboard-table"
import type { Asset, AssetType, StoryThemeAnalysis, ScriptAnalysis, StoryboardShot } from "@/lib/types/remix"
import { getAssets, saveAssets, deleteAsset as deleteAssetFromStorage } from "@/lib/asset-storage"

// Mock data for demonstration - includes full analysis data
const mockThemeData: StoryThemeAnalysis = {
  basicInfo: {
    title: "Finding Connection",
    type: "Drama / Slice of Life",
    duration: "5 minutes",
    creator: "Studio XYZ",
    background: "Modern urban setting",
  },
  coreTheme: {
    summary: "The journey from isolation to meaningful human connection",
    keywords: "Loneliness, Connection, Growth, Urban life",
  },
  narrative: {
    startingPoint: "Protagonist living in emotional isolation",
    coreConflict: "Fear of vulnerability vs. desire for connection",
    climax: "Taking the risk to reach out",
    ending: "First genuine connection made",
  },
  narrativeStructure: {
    narrativeMethod: "Linear with internal monologue",
    timeStructure: "Present day with brief flashbacks",
  },
  characterAnalysis: {
    protagonist: "Introverted professional, seeking meaning beyond work",
    characterChange: "Growth from isolation to openness",
    relationships: "Mirror relationship with secondary character",
  },
  audioVisual: {
    visualStyle: "Muted colors, urban landscapes, intimate framing",
    cameraLanguage: "Close-ups for emotion, wide shots for isolation",
    soundDesign: "Ambient city sounds, minimal dialogue, piano score",
  },
  symbolism: {
    repeatingImagery: "Windows, reflections, empty chairs",
    symbolicMeaning: "Barriers between self and others, self-reflection",
  },
  thematicStance: {
    creatorAttitude: "Sympathetic, hopeful",
    emotionalTone: "Melancholic but ultimately uplifting",
  },
  realWorldSignificance: {
    socialEmotionalValue: "Addresses modern loneliness epidemic",
    audienceInterpretation: "Relatable to urban professionals",
  },
}

const mockScriptData: ScriptAnalysis = {
  basicInfo: {
    scriptName: "Urban Loneliness Script v2",
    typeStyle: "Drama / Slice of Life",
    length: "5 minutes",
    creativeBackground: "Inspired by modern urban isolation themes",
  },
  themeIntent: {
    coreTheme: "Finding meaningful connection in an isolated world",
    subTheme: "Self-discovery through vulnerability",
    valueStance: "Human connection is essential for wellbeing",
  },
  storyStructure: {
    storyWorld: "Contemporary urban environment",
    threeActStructure: "Setup: Isolation | Confrontation: Attempted connection | Resolution: Breakthrough",
    plotPoints: "Morning routine, chance encounter, internal struggle, decision to reach out",
    endingType: "Hopeful / Open",
  },
  characterSystem: {
    protagonist: "Xiaobai - Introverted professional, seeking meaning beyond work",
    antagonist: "Internal fears and social anxiety",
    supportingRoles: "Neighbor, coworker, café regular",
    relationships: "Parallel journeys of isolated individuals",
  },
  characterArc: {
    initialState: "Emotionally closed off, routine-driven",
    actionChanges: "Small acts of courage, opening up",
    finalState: "Beginning of transformation, first connection",
  },
  conflictDesign: {
    externalConflict: "Social barriers, missed opportunities",
    internalConflict: "Fear of rejection vs. longing for connection",
    conflictEscalation: "Accumulating loneliness leading to breaking point",
  },
  plotRhythm: {
    sceneArrangement: "Alternating between isolation and glimpses of potential connection",
    rhythmControl: "Slow, contemplative pacing with moments of tension",
    suspenseSetting: "Will protagonist take the risk to connect?",
  },
  dialogueAction: {
    dialogueFunction: "Minimal external dialogue, rich internal monologue",
    subtext: "Unspoken desires and fears",
    behaviorLogic: "Small gestures reveal inner state",
  },
  symbolMetaphor: {
    coreImagery: "Windows, reflections, empty seats",
    symbolicMeaning: "Barriers, self-reflection, potential for togetherness",
  },
  genreStyle: {
    genreRules: "Slice of life drama conventions",
    narrativeStyle: "Observational, intimate",
  },
  visualPotential: {
    visualSense: "High - rich urban landscapes and intimate moments",
    audioVisualSpace: "Ambient soundscape, piano score, visual metaphors",
  },
  overallEvaluation: {
    strengths: "Relatable theme, strong visual potential, emotional depth",
    weaknesses: "Pacing may feel slow for some audiences",
    revisionDirection: "Consider adding more external conflict points",
  },
}

const mockStoryboardData: StoryboardShot[] = [
  {
    shotNumber: 1,
    firstFrameImage: "/images/shot-1.jpg",
    visualDescription: "Wide establishing shot of city skyline at dawn",
    contentDescription: "Introduction to the story world, setting the tone of urban isolation",
    startSeconds: 0,
    endSeconds: 5,
    durationSeconds: 5,
    shotSize: "Extreme Wide Shot",
    cameraAngle: "Eye Level",
    cameraMovement: "Static",
    focalLengthDepth: "Deep focus, 24mm",
    lighting: "Natural dawn light, golden hour",
    music: "Ambient orchestral, soft piano",
    dialogueVoiceover: "None",
  },
  {
    shotNumber: 2,
    firstFrameImage: "/images/shot-2.jpg",
    visualDescription: "Interior apartment, protagonist sitting alone at table",
    contentDescription: "Xiaobai begins morning routine, coffee growing cold",
    startSeconds: 5,
    endSeconds: 12,
    durationSeconds: 7,
    shotSize: "Medium Shot",
    cameraAngle: "Slightly High Angle",
    cameraMovement: "Slow dolly in",
    focalLengthDepth: "Shallow focus on protagonist, 50mm",
    lighting: "Soft window light, muted colors",
    music: "Piano melody continues",
    dialogueVoiceover: "Internal monologue: Another day...",
  },
  {
    shotNumber: 3,
    firstFrameImage: "/images/shot-3.jpg",
    visualDescription: "Close-up of window reflection showing city outside",
    contentDescription: "Symbolizing the barrier between protagonist and the world",
    startSeconds: 12,
    endSeconds: 16,
    durationSeconds: 4,
    shotSize: "Close-Up",
    cameraAngle: "Eye Level",
    cameraMovement: "Static with subtle rack focus",
    focalLengthDepth: "Rack focus from reflection to window, 85mm",
    lighting: "Backlit, silhouette effect",
    music: "Music swells slightly",
    dialogueVoiceover: "None",
  },
]

const mockAssets: Asset[] = [
  {
    id: "1",
    name: "Opening Shot - City Skyline",
    type: "storyboard",
    createdAt: "2026-01-20T10:30:00Z",
    updatedAt: "2026-01-20T10:30:00Z",
    tags: ["urban", "establishing", "morning"],
    thumbnail: "/images/storyboard-placeholder.jpg",
    data: mockStoryboardData[0],
    sourceVideo: {
      name: "urban-story-raw.mp4",
      size: 125000000,
      url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    },
  },
  {
    id: "2",
    name: "Xiaobai - Main Character",
    type: "character",
    createdAt: "2026-01-19T14:20:00Z",
    updatedAt: "2026-01-21T09:15:00Z",
    tags: ["protagonist", "young", "determined"],
    thumbnail: "/images/character-placeholder.jpg",
    data: {
      name: "Xiaobai",
      description: "A young professional navigating life in a bustling city, seeking meaningful connections",
      traits: ["Introverted", "Creative", "Resilient", "Empathetic"],
      relationships: "Isolated at start, gradually builds connections",
      imageUrl: "/images/xiaobai.jpg",
    },
  },
  {
    id: "3",
    name: "Urban Loneliness Script v2",
    type: "script",
    createdAt: "2026-01-18T08:00:00Z",
    updatedAt: "2026-01-22T16:45:00Z",
    tags: ["drama", "slice-of-life", "final"],
    data: mockScriptData,
    sourceVideo: {
      name: "urban-story-raw.mp4",
      size: 125000000,
      url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    },
  },
  {
    id: "4",
    name: "Finding Connection Theme",
    type: "theme",
    createdAt: "2026-01-17T11:00:00Z",
    updatedAt: "2026-01-17T11:00:00Z",
    tags: ["emotional", "growth", "urban"],
    data: mockThemeData,
    sourceVideo: {
      name: "urban-story-raw.mp4",
      size: 125000000,
      url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    },
  },
  {
    id: "5",
    name: "Remix Output - Instagram Reel",
    type: "video",
    createdAt: "2026-01-22T18:30:00Z",
    updatedAt: "2026-01-22T18:30:00Z",
    tags: ["instagram", "vertical", "remix"],
    thumbnail: "/images/video-placeholder.jpg",
    data: {
      url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
      duration: 60,
      format: "MP4 (H.264)",
      resolution: "1080x1920 (9:16)",
    },
  },
  {
    id: "6",
    name: "Complete Storyboard Analysis",
    type: "storyboard",
    createdAt: "2026-01-21T15:00:00Z",
    updatedAt: "2026-01-21T15:00:00Z",
    tags: ["complete", "analyzed", "urban"],
    data: {
      storyTheme: mockThemeData,
      scriptAnalysis: mockScriptData,
      storyboard: mockStoryboardData,
    },
    sourceVideo: {
      name: "urban-story-raw.mp4",
      size: 125000000,
      url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    },
  },
]

const assetTypeConfig: Record<AssetType, { icon: typeof Film; label: string; color: string }> = {
  storyboard: { icon: Film, label: "Storyboard", color: "bg-blue-500/20 text-blue-400" },
  character: { icon: User, label: "Character", color: "bg-purple-500/20 text-purple-400" },
  script: { icon: FileText, label: "Script", color: "bg-green-500/20 text-green-400" },
  theme: { icon: Palette, label: "Theme", color: "bg-orange-500/20 text-orange-400" },
  video: { icon: Video, label: "Video", color: "bg-red-500/20 text-red-400" },
}

export default function AssetLibraryPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedType, setSelectedType] = useState<AssetType | "all">("all")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [assets, setAssets] = useState<Asset[]>([])
  const [showDetailView, setShowDetailView] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Load assets from localStorage on mount
  useEffect(() => {
    const storedAssets = getAssets()
    // If no stored assets, use mock data as initial demo data
    if (storedAssets.length === 0) {
      setAssets(mockAssets)
      saveAssets(mockAssets)
    } else {
      setAssets(storedAssets)
    }
    setIsLoading(false)
  }, [])

  const filteredAssets = assets.filter((asset) => {
    const matchesSearch =
      asset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      asset.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesType = selectedType === "all" || asset.type === selectedType
    return matchesSearch && matchesType
  })

  const handleDeleteAsset = (id: string) => {
    deleteAssetFromStorage(id)
    setAssets(assets.filter((a) => a.id !== id))
    if (selectedAsset?.id === id) {
      setSelectedAsset(null)
      setShowDetailView(false)
    }
  }

  const handleExportAsset = (asset: Asset) => {
    const dataStr = JSON.stringify(asset, null, 2)
    const blob = new Blob([dataStr], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${asset.name.replace(/\s+/g, "-").toLowerCase()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleViewDetails = (asset: Asset) => {
    setSelectedAsset(asset)
    setShowDetailView(true)
  }

  const handleBackToList = () => {
    setShowDetailView(false)
    setSelectedAsset(null)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  const formatFileSize = (bytes: number) => {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  // Render Detail View
  if (showDetailView && selectedAsset) {
    const config = assetTypeConfig[selectedAsset.type]
    const sourceVideo = (selectedAsset as Asset & { sourceVideo?: { name: string; size: number; url?: string } }).sourceVideo

    return (
      <div className="space-y-6">
        {/* Back Button Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            onClick={handleBackToList}
            className="gap-2 border-border bg-transparent"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Library
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <config.icon className="w-6 h-6" />
              {selectedAsset.name}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge className={config.color} variant="secondary">
                {config.label}
              </Badge>
              {selectedAsset.tags.map((tag) => (
                <Badge key={tag} variant="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => handleExportAsset(selectedAsset)}
              className="gap-2 border-border bg-transparent"
            >
              <Download className="w-4 h-4" />
              Export JSON
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleDeleteAsset(selectedAsset.id)}
              className="gap-2"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </Button>
          </div>
        </div>

        {/* Source Video Section */}
        {sourceVideo && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-foreground flex items-center gap-2">
                <Video className="w-5 h-5" />
                Source Video
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col lg:flex-row gap-6">
                {/* Video Preview */}
                <div className="lg:w-1/2">
                  {sourceVideo.url ? (
                    <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
                      <video
                        className="w-full h-full object-contain"
                        controls
                        preload="metadata"
                      >
                        <source src={sourceVideo.url} type="video/mp4" />
                        Your browser does not support the video tag.
                      </video>
                    </div>
                  ) : (
                    <div className="aspect-video bg-secondary rounded-lg flex items-center justify-center">
                      <Play className="w-12 h-12 text-muted-foreground" />
                    </div>
                  )}
                </div>
                
                {/* Video Info */}
                <div className="lg:w-1/2 space-y-4">
                  <div>
                    <p className="text-sm text-muted-foreground">File Name</p>
                    <p className="text-foreground font-medium">{sourceVideo.name}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">File Size</p>
                    <p className="text-foreground font-medium">{formatFileSize(sourceVideo.size)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Saved</p>
                    <p className="text-foreground font-medium">{formatDate(selectedAsset.createdAt)}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Asset Content based on type */}
        {selectedAsset.type === "theme" && (
          <StoryThemeTable data={selectedAsset.data as StoryThemeAnalysis} showSaveButton={false} />
        )}

        {selectedAsset.type === "script" && (
          <ScriptAnalysisTable data={selectedAsset.data as ScriptAnalysis} showSaveButton={false} />
        )}

        {selectedAsset.type === "storyboard" && (
          <>
            {/* Check if it's a complete analysis or single shot */}
            {(selectedAsset.data as { storyTheme?: StoryThemeAnalysis }).storyTheme ? (
              // Complete analysis with all tables
              <div className="space-y-6">
                <StoryThemeTable 
                  data={(selectedAsset.data as { storyTheme: StoryThemeAnalysis }).storyTheme} 
                  showSaveButton={false} 
                />
                {(selectedAsset.data as { scriptAnalysis?: ScriptAnalysis }).scriptAnalysis && (
                  <ScriptAnalysisTable 
                    data={(selectedAsset.data as { scriptAnalysis: ScriptAnalysis }).scriptAnalysis} 
                    showSaveButton={false} 
                  />
                )}
                {(selectedAsset.data as { storyboard?: StoryboardShot[] }).storyboard && (
                  <StoryboardTable 
                    data={(selectedAsset.data as { storyboard: StoryboardShot[] }).storyboard}
                    showSaveButtons={false}
                  />
                )}
              </div>
            ) : (
              // Single storyboard shot
              <StoryboardTable 
                data={[selectedAsset.data as StoryboardShot]}
                showSaveButtons={false}
              />
            )}
          </>
        )}

        {selectedAsset.type === "character" && (
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Character Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Name</p>
                    <p className="text-foreground font-medium">
                      {(selectedAsset.data as { name: string }).name}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Description</p>
                    <p className="text-foreground">
                      {(selectedAsset.data as { description: string }).description}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Traits</p>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {(selectedAsset.data as { traits: string[] }).traits.map((trait) => (
                        <Badge key={trait} variant="outline">{trait}</Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Relationships</p>
                    <p className="text-foreground">
                      {(selectedAsset.data as { relationships: string }).relationships}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-center">
                  <div className="w-48 h-48 bg-secondary rounded-lg flex items-center justify-center">
                    <User className="w-16 h-16 text-muted-foreground" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {selectedAsset.type === "video" && (
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Video Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="aspect-video bg-black rounded-lg overflow-hidden">
                <video
                  className="w-full h-full object-contain"
                  controls
                  preload="metadata"
                >
                  <source src={(selectedAsset.data as { url: string }).url} type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-secondary/50 rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Duration</p>
                  <p className="text-foreground font-medium">
                    {(selectedAsset.data as { duration: number }).duration} seconds
                  </p>
                </div>
                <div className="bg-secondary/50 rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Format</p>
                  <p className="text-foreground font-medium">
                    {(selectedAsset.data as { format: string }).format}
                  </p>
                </div>
                <div className="bg-secondary/50 rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Resolution</p>
                  <p className="text-foreground font-medium">
                    {(selectedAsset.data as { resolution: string }).resolution}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Meta info */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground text-base">Asset Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Type</p>
                <p className="text-foreground font-medium">{config.label}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Created</p>
                <p className="text-foreground font-medium">{formatDate(selectedAsset.createdAt)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Last Updated</p>
                <p className="text-foreground font-medium">{formatDate(selectedAsset.updatedAt)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">ID</p>
                <p className="text-foreground font-medium font-mono text-xs">{selectedAsset.id}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Render List View
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Asset Library</h1>
        <p className="text-muted-foreground mt-1">
          Manage your saved storyboards, characters, scripts, and more
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search assets by name or tag..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-card border-border"
          />
        </div>

        {/* Filter by type */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2 border-border bg-transparent">
              <Filter className="w-4 h-4" />
              {selectedType === "all" ? "All Types" : assetTypeConfig[selectedType].label}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSelectedType("all")}>
              All Types
            </DropdownMenuItem>
            {Object.entries(assetTypeConfig).map(([type, config]) => (
              <DropdownMenuItem key={type} onClick={() => setSelectedType(type as AssetType)}>
                <config.icon className="w-4 h-4 mr-2" />
                {config.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* View mode toggle */}
        <div className="flex gap-1 bg-card rounded-lg p-1 border border-border">
          <Button
            variant={viewMode === "grid" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setViewMode("grid")}
            className="px-3"
          >
            <Grid3X3 className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === "list" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setViewMode("list")}
            className="px-3"
          >
            <List className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Asset counts */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(assetTypeConfig).map(([type, config]) => {
          const count = assets.filter((a) => a.type === type).length
          return (
            <Badge
              key={type}
              variant="outline"
              className={`cursor-pointer ${selectedType === type ? config.color : "hover:bg-secondary"}`}
              onClick={() => setSelectedType(selectedType === type ? "all" : (type as AssetType))}
            >
              <config.icon className="w-3 h-3 mr-1" />
              {config.label}: {count}
            </Badge>
          )
        })}
      </div>

      {/* Assets Grid/List */}
      {filteredAssets.length === 0 ? (
        <Card className="bg-card border-border">
          <CardContent className="py-16 text-center">
            <FolderOpen className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">No assets found</h3>
            <p className="text-muted-foreground">
              {searchQuery || selectedType !== "all"
                ? "Try adjusting your search or filter criteria"
                : "Start by saving storyboards, characters, or scripts from your projects"}
            </p>
          </CardContent>
        </Card>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredAssets.map((asset) => {
            const config = assetTypeConfig[asset.type]
            return (
              <Card
                key={asset.id}
                className="bg-card border-border hover:border-accent/50 transition-colors cursor-pointer group"
                onClick={() => handleViewDetails(asset)}
              >
                <CardContent className="p-4">
                  {/* Thumbnail */}
                  <div className="aspect-video bg-secondary rounded-lg mb-3 flex items-center justify-center overflow-hidden">
                    <config.icon className="w-8 h-8 text-muted-foreground" />
                  </div>

                  {/* Info */}
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-medium text-foreground line-clamp-1">{asset.name}</h3>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8 p-0"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleViewDetails(asset) }}>
                            <Eye className="w-4 h-4 mr-2" />
                            View Details
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleExportAsset(asset) }}>
                            <Download className="w-4 h-4 mr-2" />
                            Export JSON
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={(e) => { e.stopPropagation(); handleDeleteAsset(asset.id) }}
                            className="text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    <Badge className={config.color} variant="secondary">
                      <config.icon className="w-3 h-3 mr-1" />
                      {config.label}
                    </Badge>

                    <div className="flex flex-wrap gap-1">
                      {asset.tags.slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>

                    <p className="text-xs text-muted-foreground">
                      Updated {formatDate(asset.updatedAt)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : (
        <Card className="bg-card border-border">
          <CardContent className="p-0">
            <div className="divide-y divide-border">
              {filteredAssets.map((asset) => {
                const config = assetTypeConfig[asset.type]
                return (
                  <div
                    key={asset.id}
                    className="flex items-center gap-4 p-4 hover:bg-secondary/50 transition-colors cursor-pointer group"
                    onClick={() => handleViewDetails(asset)}
                  >
                    <div className="w-12 h-12 bg-secondary rounded-lg flex items-center justify-center shrink-0">
                      <config.icon className="w-6 h-6 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-foreground truncate">{asset.name}</h3>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={config.color} variant="secondary">
                          {config.label}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          Updated {formatDate(asset.updatedAt)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleExportAsset(asset) }}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleDeleteAsset(asset.id) }}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
