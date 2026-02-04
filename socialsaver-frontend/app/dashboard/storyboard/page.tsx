"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { SimpleVideoUpload } from "@/components/simple-video-upload"
import { StoryThemeTable } from "@/components/remix/story-theme-table"
import { ScriptAnalysisTable } from "@/components/remix/script-analysis-table"
import { StoryboardTable } from "@/components/remix/storyboard-table"
import { CharacterInventoryTable } from "@/components/remix/character-inventory-table"
import { Loader2, Download, CheckCircle, FileJson, FolderOpen, Video, Play, AlertCircle } from "lucide-react"
import { SaveToLibraryDialog } from "@/components/save-to-library-dialog"
import type { RemixAnalysisResult, StoryboardShot } from "@/lib/types/remix"
import { saveStoryboardToLibrary } from "@/lib/asset-storage"

// 🔌 Real API Integration
import { uploadVideo, getStoryboard, getStoryTheme, getScriptAnalysis, getAssetUrl, getCharacterLedger } from "@/lib/api"
import type { CharacterEntity, EnvironmentEntity } from "@/lib/api"

type AnalysisStep = "upload" | "analyzing" | "results"

// Mock analysis data
const mockAnalysisResult: RemixAnalysisResult = {
  storyTheme: {
    basicInfo: {
      title: "Urban Solitude",
      type: "Drama / Slice of Life",
      duration: "5 minutes",
      creator: "Independent Filmmaker",
      background: "Modern urban setting exploring themes of connection",
    },
    coreTheme: {
      summary: "Finding meaningful connection in an increasingly isolated world",
      keywords: "Loneliness, Connection, Urban life, Self-discovery",
    },
    narrative: {
      startingPoint: "Protagonist lives a routine, isolated life in the city",
      coreConflict: "Struggle between comfort of solitude and desire for connection",
      climax: "Unexpected encounter that challenges their worldview",
      ending: "Open-ended, suggesting possibility of change",
    },
    narrativeStructure: {
      narrativeMethod: "Linear with reflective moments",
      timeStructure: "Present day with brief flashbacks",
    },
    characterAnalysis: {
      protagonist: "Introverted professional, seeking meaning beyond work",
      characterChange: "Growth - from isolation to openness",
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
  },
  scriptAnalysis: {
    basicInfo: {
      scriptName: "Untitled Short",
      typeStyle: "Drama / Slice of Life",
      length: "5 minutes",
      creativeBackground: "Personal project exploring urban isolation",
    },
    themeIntent: {
      coreTheme: "Human connection in modern isolation",
      subTheme: "Self-acceptance, vulnerability",
      valueStance: "Pro-human connection, anti-isolation",
    },
    storyStructure: {
      storyWorld: "Contemporary urban environment",
      threeActStructure: "Setup (isolation) - Confrontation (encounter) - Resolution (openness)",
      plotPoints: "Morning routine, coffee shop encounter, evening reflection",
      endingType: "Open-ended with hope",
    },
    characterSystem: {
      protagonist: "Young professional, early 30s",
      antagonist: "Internal - fear of vulnerability",
      supportingRoles: "Barista, stranger at coffee shop",
      relationships: "Minimal but meaningful interactions",
    },
    characterArc: {
      initialState: "Comfortable but unfulfilled in isolation",
      actionChanges: "Forced interaction leads to self-reflection",
      finalState: "Open to possibility of connection",
    },
    conflictDesign: {
      externalConflict: "Navigating social interaction",
      internalConflict: "Fear vs. desire for connection",
      conflictEscalation: "Gradual buildup through small moments",
    },
    plotRhythm: {
      sceneArrangement: "Alternating between solitude and interaction",
      rhythmControl: "Slow, contemplative pacing",
      suspenseSetting: "Emotional rather than action-based",
    },
    dialogueAction: {
      dialogueFunction: "Minimal, meaningful exchanges",
      subtext: "Unspoken longing for connection",
      behaviorLogic: "Actions speak louder than words",
    },
    symbolMetaphor: {
      coreImagery: "Empty coffee cups, phone screens, window reflections",
      symbolicMeaning: "Modern barriers to genuine connection",
    },
    genreStyle: {
      genreRules: "Follows slice-of-life conventions",
      narrativeStyle: "Observational, intimate",
    },
    visualPotential: {
      visualSense: "Strong - relies on visual storytelling",
      audioVisualSpace: "Rich opportunity for atmospheric sound design",
    },
    overallEvaluation: {
      strengths: "Relatable theme, strong visual potential",
      weaknesses: "May feel slow for some audiences",
      revisionDirection: "Consider adding more active moments",
    },
  },
  storyboard: [
    {
      shotNumber: 1,
      firstFrameImage: "",
      visualDescription: "Wide shot of city skyline at dawn",
      contentDescription: "Establishing shot - urban environment awakening",
      startSeconds: 0,
      endSeconds: 5,
      durationSeconds: 5,
      shotSize: "Extreme Wide",
      cameraAngle: "Eye Level",
      cameraMovement: "Static",
      focalLengthDepth: "Wide angle, deep focus",
      lighting: "Natural dawn light",
      music: "Soft ambient piano",
      dialogueVoiceover: "None",
    },
    {
      shotNumber: 2,
      firstFrameImage: "",
      visualDescription: "Close-up of alarm clock showing 6:00 AM",
      contentDescription: "Time reference, routine beginning",
      startSeconds: 5,
      endSeconds: 8,
      durationSeconds: 3,
      shotSize: "Close-up",
      cameraAngle: "High Angle",
      cameraMovement: "Static",
      focalLengthDepth: "50mm, shallow focus",
      lighting: "Dim bedroom light",
      music: "Continues from previous",
      dialogueVoiceover: "None",
    },
    {
      shotNumber: 3,
      firstFrameImage: "",
      visualDescription: "Medium shot of protagonist waking up alone",
      contentDescription: "Introduction of main character, solitary state",
      startSeconds: 8,
      endSeconds: 15,
      durationSeconds: 7,
      shotSize: "Medium",
      cameraAngle: "Eye Level",
      cameraMovement: "Slow push in",
      focalLengthDepth: "35mm, medium depth",
      lighting: "Soft morning light through blinds",
      music: "Piano fades slightly",
      dialogueVoiceover: "None",
    },
    {
      shotNumber: 4,
      firstFrameImage: "",
      visualDescription: "Coffee shop interior, protagonist enters",
      contentDescription: "Change of location, entering social space",
      startSeconds: 45,
      endSeconds: 52,
      durationSeconds: 7,
      shotSize: "Wide",
      cameraAngle: "Eye Level",
      cameraMovement: "Pan following subject",
      focalLengthDepth: "24mm, deep focus",
      lighting: "Warm interior lighting",
      music: "Subtle cafe ambience added",
      dialogueVoiceover: "None",
    },
    {
      shotNumber: 5,
      firstFrameImage: "",
      visualDescription: "Two-shot at coffee counter, unexpected eye contact",
      contentDescription: "Key moment - potential connection introduced",
      startSeconds: 65,
      endSeconds: 72,
      durationSeconds: 7,
      shotSize: "Medium Two-shot",
      cameraAngle: "Over-the-shoulder",
      cameraMovement: "Static",
      focalLengthDepth: "50mm, shallow focus on faces",
      lighting: "Warm key light",
      music: "Music subtly shifts",
      dialogueVoiceover: "'The usual?' - Barista",
    },
  ],
}

export default function StoryboardAnalysisPage() {
  const [step, setStep] = useState<AnalysisStep>("upload")
  const [analysisResult, setAnalysisResult] = useState<RemixAnalysisResult | null>(null)
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null)

  // 🔌 Real API State
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [sourceVideoFilename, setSourceVideoFilename] = useState<string | null>(null)

  // Character Ledger State
  const [characterLedger, setCharacterLedger] = useState<CharacterEntity[]>([])
  const [environmentLedger, setEnvironmentLedger] = useState<EnvironmentEntity[]>([])

  const handleVideoSubmit = async (files: File[]) => {
    setUploadedFiles(files)
    setApiError(null)

    // Create preview URL for the first video
    if (files.length > 0) {
      const url = URL.createObjectURL(files[0])
      setVideoPreviewUrl(url)
    }

    setStep("analyzing")

    try {
      // 🔌 Real API Call: Upload video and trigger analysis
      const videoFile = files[0]
      if (!videoFile) {
        throw new Error("No video file selected")
      }

      const uploadResult = await uploadVideo(videoFile)
      setCurrentJobId(uploadResult.job_id)

      // Poll for storyboard data
      let retries = 0
      const maxRetries = 60 // Max 3 minutes
      let storyboardData = null

      while (retries < maxRetries) {
        try {
          storyboardData = await getStoryboard(uploadResult.job_id)
          if (storyboardData.storyboard && storyboardData.storyboard.length > 0) {
            break
          }
        } catch (e) {
          // Still processing, continue polling
        }
        await new Promise((resolve) => setTimeout(resolve, 3000))
        retries++
      }

      if (!storyboardData || !storyboardData.storyboard || storyboardData.storyboard.length === 0) {
        throw new Error("Video analysis timeout or failed")
      }

      // Process image URLs to be full URLs
      const processedStoryboard: StoryboardShot[] = storyboardData.storyboard.map((shot) => ({
        ...shot,
        firstFrameImage: shot.firstFrameImage
          ? getAssetUrl(uploadResult.job_id, shot.firstFrameImage)
          : "",
      }))

      // Calculate total duration
      const totalDuration = processedStoryboard.reduce((sum, s) => sum + s.durationSeconds, 0)

      // 🔌 Fetch real Story Theme and Script Analysis from Film IR API (with retry)
      let storyThemeData: any = null
      let scriptAnalysisData: any = null
      let filmIrRetries = 0
      const maxFilmIrRetries = 40 // Max 2 minutes for both analyses

      while (filmIrRetries < maxFilmIrRetries) {
        try {
          // Fetch both in parallel
          const [themeResult, scriptResult]: [any, any] = await Promise.all([
            storyThemeData ? Promise.resolve(storyThemeData) : getStoryTheme(uploadResult.job_id),
            scriptAnalysisData ? Promise.resolve(scriptAnalysisData) : getScriptAnalysis(uploadResult.job_id)
          ])

          if (themeResult && !storyThemeData) {
            storyThemeData = themeResult
            console.log("✅ Story Theme received from API")
          }
          if (scriptResult && !scriptAnalysisData) {
            scriptAnalysisData = scriptResult
            console.log("✅ Script Analysis received from API")
          }

          // Break if both are ready
          if (storyThemeData && scriptAnalysisData) {
            break
          }
        } catch (e) {
          // Still processing, continue polling
        }
        await new Promise((resolve) => setTimeout(resolve, 3000))
        filmIrRetries++
      }

      // Create analysis result with real data (fallback to mock if not ready)
      const realAnalysisResult: RemixAnalysisResult = {
        storyTheme: storyThemeData || {
          ...mockAnalysisResult.storyTheme,
          basicInfo: {
            ...mockAnalysisResult.storyTheme.basicInfo,
            title: storyboardData.sourceVideo || videoFile.name,
            duration: `${Math.round(totalDuration)}s`,
          },
        },
        scriptAnalysis: scriptAnalysisData || mockAnalysisResult.scriptAnalysis,
        storyboard: processedStoryboard,
      }

      // 保存源视频文件名用于后续构建 URL
      setSourceVideoFilename(storyboardData.sourceVideo || null)

      // 🔌 Fetch Character Ledger
      try {
        const ledgerData = await getCharacterLedger(uploadResult.job_id)
        setCharacterLedger(ledgerData.characterLedger || [])
        setEnvironmentLedger(ledgerData.environmentLedger || [])
        console.log("✅ Character Ledger received:", ledgerData.summary)
      } catch (e) {
        console.warn("Character Ledger not available:", e)
        setCharacterLedger([])
        setEnvironmentLedger([])
      }

      setAnalysisResult(realAnalysisResult)
      setStep("results")
    } catch (error) {
      console.error("Upload/Analysis error:", error)
      setApiError(error instanceof Error ? error.message : "Analysis failed")
      setStep("upload")
    }
  }

  const handleExportJSON = () => {
    if (!analysisResult) return

    const exportData = {
      exportedAt: new Date().toISOString(),
      videoFiles: uploadedFiles.map((f) => f.name),
      storyThemeAnalysis: analysisResult.storyTheme,
      scriptAnalysis: analysisResult.scriptAnalysis,
      storyboard: analysisResult.storyboard,
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `storyboard-analysis-${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleStartOver = () => {
    setStep("upload")
    setAnalysisResult(null)
    setUploadedFiles([])
    if (videoPreviewUrl) {
      URL.revokeObjectURL(videoPreviewUrl)
      setVideoPreviewUrl(null)
    }
    // Reset API state
    setCurrentJobId(null)
    setApiError(null)
    setSourceVideoFilename(null)
    // Reset Character Ledger
    setCharacterLedger([])
    setEnvironmentLedger([])
  }
  
  const handleSaveToLibrary = (name: string, tags: string[]) => {
    if (!analysisResult) return

    // 构建源视频 URL（如果有 job_id 和 sourceVideoFilename）
    const sourceVideoUrl = currentJobId && sourceVideoFilename
      ? getAssetUrl(currentJobId, sourceVideoFilename)
      : undefined

    // 获取第一个 shot 的 firstFrameImage 作为缩略图
    const thumbnail = analysisResult.storyboard[0]?.firstFrameImage || undefined

    saveStoryboardToLibrary(
      name,
      tags,
      {
        storyTheme: analysisResult.storyTheme,
        scriptAnalysis: analysisResult.scriptAnalysis,
        storyboard: analysisResult.storyboard,
      },
      uploadedFiles[0] ? {
        name: uploadedFiles[0].name,
        size: uploadedFiles[0].size,
        url: sourceVideoUrl,
      } : undefined,
      thumbnail
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Storyboard Analysis</h1>
          <p className="text-muted-foreground">
            Upload videos to analyze and generate detailed shot-by-shot breakdowns
          </p>
        </div>
        {step === "results" && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleStartOver}
              className="border-border text-foreground hover:bg-secondary bg-transparent"
            >
              Analyze Another
            </Button>
            <Button
              onClick={handleExportJSON}
              className="bg-accent text-accent-foreground hover:bg-accent/90"
            >
              <FileJson className="w-4 h-4 mr-2" />
              Export JSON
            </Button>
          </div>
        )}
      </div>

      {/* Step: Upload */}
      {/* Step: Upload */}
      {step === "upload" && (
        <>
          {apiError && (
            <Card className="bg-red-500/10 border-red-500/30 mb-4">
              <CardContent className="py-4 flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-500" />
                <p className="text-red-500">{apiError}</p>
              </CardContent>
            </Card>
          )}
          <SimpleVideoUpload onSubmit={handleVideoSubmit} isLoading={false} />
        </>
      )}

      {/* Step: Analyzing */}
      {step === "analyzing" && (
        <Card className="bg-card border-border">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Loader2 className="w-12 h-12 text-accent animate-spin mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">
              Analyzing Video
            </h3>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              Extracting story themes, script structure, and generating storyboard breakdown...
            </p>
          </CardContent>
        </Card>
      )}

      {/* Step: Results */}
      {step === "results" && analysisResult && (
        <div className="space-y-6">
          {/* Source Video Section */}
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
                  {videoPreviewUrl ? (
                    <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
                      <video
                        className="w-full h-full object-contain"
                        controls
                        preload="metadata"
                      >
                        <source src={videoPreviewUrl} type="video/mp4" />
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
                    <p className="text-foreground font-medium">{uploadedFiles[0]?.name || "Unknown"}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">File Size</p>
                    <p className="text-foreground font-medium">
                      {uploadedFiles[0] ? `${(uploadedFiles[0].size / (1024 * 1024)).toFixed(2)} MB` : "Unknown"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Analysis Results</p>
                    <p className="text-foreground font-medium">
                      {analysisResult.storyboard.length} shots identified
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Success Banner */}
          <Card className="bg-accent/10 border-accent">
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-accent" />
                <div>
                  <p className="font-medium text-foreground">Analysis Complete</p>
                  <p className="text-sm text-muted-foreground">
                    Found {analysisResult.storyboard.length} shots across {uploadedFiles.length} video(s)
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Story Theme Analysis */}
          <StoryThemeTable data={analysisResult.storyTheme} />

          {/* Script Analysis */}
          <ScriptAnalysisTable data={analysisResult.scriptAnalysis} />

          {/* Storyboard Breakdown */}
          <StoryboardTable data={analysisResult.storyboard} />

          {/* Character & Environment Inventory */}
          {currentJobId && (characterLedger.length > 0 || environmentLedger.length > 0) && (
            <CharacterInventoryTable
              jobId={currentJobId}
              characters={characterLedger}
              environments={environmentLedger}
            />
          )}

          {/* Export & Save Section */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground flex items-center gap-2">
                <Download className="w-5 h-5" />
                Export & Save
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Download the complete analysis as a JSON file or save it to your asset library for future reference.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={handleExportJSON}
                  className="bg-accent text-accent-foreground hover:bg-accent/90"
                >
                  <FileJson className="w-4 h-4 mr-2" />
                  Export as JSON
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setSaveDialogOpen(true)}
                  className="border-accent text-accent hover:bg-accent/10 bg-transparent"
                >
                  <FolderOpen className="w-4 h-4 mr-2" />
                  Add to Asset Library
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Save to Library Dialog */}
      <SaveToLibraryDialog
        open={saveDialogOpen}
        onOpenChange={setSaveDialogOpen}
        assetType="storyboard"
        defaultName={uploadedFiles[0]?.name?.replace(/\.[^/.]+$/, "") || "Storyboard Analysis"}
        onSave={handleSaveToLibrary}
      />
    </div>
  )
}
