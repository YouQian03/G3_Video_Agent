"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { VideoUpload } from "@/components/remix/video-upload"
import { StoryThemeTable } from "@/components/remix/story-theme-table"
import { ScriptAnalysisTable } from "@/components/remix/script-analysis-table"
import { StoryboardTable } from "@/components/remix/storyboard-table"
import { GeneratedScriptCard } from "@/components/remix/generated-script"
import { StoryboardChat } from "@/components/remix/storyboard-chat"
import { StepIndicator } from "@/components/remix/step-indicator"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, Sparkles, ArrowLeft, Video, Play, Download, Share2, Layers } from "lucide-react"
import { CharacterSceneViews } from "@/components/remix/character-scene-views"
import type {
  AnalysisStep,
  RemixAnalysisResult,
  GeneratedScript,
  StoryboardShot,
  CharacterView,
  SceneView,
} from "@/lib/types/remix"

// 🔌 Real API Integration
import {
  uploadVideo,
  getStoryboard,
  getJobStatus,
  sendAgentChat,
  runTask,
  getAssetUrl,
  type SocialSaverStoryboard,
} from "@/lib/api"

// Step definitions - now with 5 steps including character/scene views
const WORKFLOW_STEPS = [
  { id: "analysis", label: "Video Analysis", description: "Analyze story theme, script, and storyboard" },
  { id: "script", label: "Generate Remix Script", description: "Create customized script based on your requirements" },
  { id: "views", label: "Character & Scene Views", description: "Confirm character and scene three-view references" },
  { id: "storyboard", label: "Generate Storyboard", description: "Generate storyboard from confirmed script" },
  { id: "video", label: "Generate Video", description: "Create final remix video from storyboard" },
]

// Mock data for demonstration
const mockAnalysisResult: RemixAnalysisResult = {
  storyTheme: {
    basicInfo: {
      title: "Sample Video",
      type: "Short Film / Drama",
      duration: "5:32",
      creator: "Unknown Creator",
      background: "Modern urban setting",
    },
    coreTheme: {
      summary: "A story about finding connection in an increasingly disconnected world",
      keywords: "Connection, Loneliness, Technology, Human Relationships",
    },
    narrative: {
      startingPoint: "Protagonist living isolated life in big city",
      coreConflict: "Desire for connection vs fear of vulnerability",
      climax: "Unexpected encounter leads to breakthrough moment",
      ending: "Open ending suggesting hope for change",
    },
    narrativeStructure: {
      narrativeMethod: "Linear with brief flashbacks",
      timeStructure: "Present day with memory sequences",
    },
    characterAnalysis: {
      protagonist: "Jack - Introverted professional, seeking meaning beyond work",
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
      creativeBackground: "Contemporary urban setting",
    },
    themeIntent: {
      coreTheme: "Human connection in digital age",
      subTheme: "Self-acceptance, vulnerability",
      valueStance: "Empathetic, non-judgmental",
    },
    storyStructure: {
      storyWorld: "Modern city, present day, realistic rules",
      threeActStructure: "Setup (isolation) / Confrontation (encounter) / Resolution (opening up)",
      plotPoints: "Inciting incident at 1:00, turning point at 3:00, climax at 4:30",
      endingType: "Open ending",
    },
    characterSystem: {
      protagonist: "Jack - Goal: find meaning; Desire: connection; Flaw: fear of rejection",
      antagonist: "Internal - self-doubt and past trauma",
      supportingRoles: "Stranger who catalyzes change",
      relationships: "Emotional mirror, mutual recognition",
    },
    characterArc: {
      initialState: "Closed off, routine-bound",
      actionChanges: "Takes risk to engage with stranger",
      finalState: "Open to possibility, hopeful",
    },
    conflictDesign: {
      externalConflict: "Social expectations vs personal needs",
      internalConflict: "Desire for connection vs fear of hurt",
      conflictEscalation: "Progressive through small moments",
    },
    plotRhythm: {
      sceneArrangement: "12 scenes, alternating interior/exterior",
      rhythmControl: "Slow build to emotional peak",
      suspenseSetting: "Will protagonist take the risk?",
    },
    dialogueAction: {
      dialogueFunction: "Minimal, reveals character through subtext",
      subtext: "What's unsaid carries more weight",
      behaviorLogic: "Consistent with established psychology",
    },
    symbolMetaphor: {
      coreImagery: "Doors, windows, reflections",
      symbolicMeaning: "Thresholds, barriers, self-perception",
    },
    genreStyle: {
      genreRules: "Follows indie drama conventions",
      narrativeStyle: "Naturalistic, observational",
    },
    visualPotential: {
      visualSense: "Strong - evocative imagery throughout",
      audioVisualSpace: "Rich potential for atmospheric sound design",
    },
    overallEvaluation: {
      strengths: "Emotional resonance, visual storytelling, relatable theme",
      weaknesses: "Pacing could be tighter in middle section",
      revisionDirection: "Strengthen supporting character's presence",
    },
  },
  storyboard: [
    {
      shotNumber: 1,
      firstFrameImage: "",
      visualDescription: "Wide establishing shot of city skyline at dawn",
      contentDescription: "Sets the urban context, isolation theme",
      startSeconds: 0,
      endSeconds: 5,
      durationSeconds: 5,
      shotSize: "Extreme Wide",
      cameraAngle: "Eye Level",
      cameraMovement: "Static",
      focalLengthDepth: "Wide angle, deep focus",
      lighting: "Natural dawn light",
      music: "Soft ambient piano begins",
      dialogueVoiceover: "None",
    },
    {
      shotNumber: 2,
      firstFrameImage: "",
      visualDescription: "Close-up of Jack's face looking out window",
      contentDescription: "Introduces main character, contemplative mood",
      startSeconds: 5,
      endSeconds: 12,
      durationSeconds: 7,
      shotSize: "Close-up",
      cameraAngle: "Profile",
      cameraMovement: "Slow push in",
      focalLengthDepth: "85mm, shallow depth",
      lighting: "Window light, soft shadows",
      music: "Piano continues, adds subtle strings",
      dialogueVoiceover: "None",
    },
    {
      shotNumber: 3,
      firstFrameImage: "",
      visualDescription: "Medium shot of empty apartment interior",
      contentDescription: "Shows isolated living environment",
      startSeconds: 12,
      endSeconds: 18,
      durationSeconds: 6,
      shotSize: "Medium Wide",
      cameraAngle: "Eye Level",
      cameraMovement: "Slow pan left to right",
      focalLengthDepth: "35mm, medium depth",
      lighting: "Practical lamps, warm tones",
      music: "Minimal, ambient",
      dialogueVoiceover: "None",
    },
  ],
}

// Function to generate modified analysis based on user requirements
const generateModifiedAnalysis = (baseAnalysis: RemixAnalysisResult, requirements: string): RemixAnalysisResult => {
  const hasXiaobaiRequest = requirements.toLowerCase().includes("xiaobai") || 
                           requirements.includes("小白") ||
                           requirements.toLowerCase().includes("replace jack")

  if (hasXiaobaiRequest) {
    return {
      ...baseAnalysis,
      storyTheme: {
        ...baseAnalysis.storyTheme,
        characterAnalysis: {
          ...baseAnalysis.storyTheme.characterAnalysis,
          protagonist: "Xiaobai - Introverted professional, seeking meaning beyond work [MODIFIED: Replaced Jack with Xiaobai per your request]",
        },
      },
      scriptAnalysis: {
        ...baseAnalysis.scriptAnalysis,
        characterSystem: {
          ...baseAnalysis.scriptAnalysis.characterSystem,
          protagonist: "Xiaobai - Goal: find meaning; Desire: connection; Flaw: fear of rejection [MODIFIED: Character renamed]",
        },
      },
      storyboard: baseAnalysis.storyboard.map((shot) => ({
        ...shot,
        visualDescription: shot.visualDescription.replace(/Jack/g, "Xiaobai"),
        contentDescription: shot.contentDescription.replace(/Jack/g, "Xiaobai"),
      })),
      suggestedModifications: [
        "Replace all instances of 'Jack' with 'Xiaobai' throughout the video",
        "Update character name in any text overlays or credits",
        "Ensure voice-over (if any) uses new character name",
      ],
    }
  }

  return baseAnalysis
}

const generateMockScript = (requirements: string, referenceImages: File[]): GeneratedScript => {
  const hasXiaobaiRequest = requirements.toLowerCase().includes("xiaobai") || 
                           requirements.includes("小白")
  const characterName = hasXiaobaiRequest ? "Xiaobai" : "Jack"
  
  return {
    content: `REMIX SCRIPT: "Connection - ${characterName}'s Journey"
  
Based on your requirements${referenceImages.length > 0 ? ` and ${referenceImages.length} reference image(s)` : ''}, here is the proposed remix:

CHARACTER: ${characterName} (${hasXiaobaiRequest ? 'renamed from Jack as requested' : 'original character'})

SCENE 1 - OPENING (0:00 - 0:15)
- Use wide city shot from original (Shot 1)
- Add text overlay: "In a world of millions..."
- Music: Upbeat electronic remix of original piano theme

SCENE 2 - ${characterName.toUpperCase()} INTRO (0:15 - 0:30)
- Quick cuts of ${characterName}'s daily routine
- Use close-up from Shot 2, color grade to warmer tones
- Add subtle motion graphics around character
${referenceImages.length > 0 ? `- Apply visual style from reference images provided` : ''}

SCENE 3 - THE ENCOUNTER (0:30 - 0:50)
- Montage of key moments leading to meeting
- Speed ramp effects for dynamic feel
- Music builds to crescendo

SCENE 4 - RESOLUTION (0:50 - 1:00)
- Final hopeful moment with ${characterName}
- Slow motion effect
- Fade to white with logo

TOTAL DURATION: 60 seconds
FORMAT: Vertical (9:16) for social media

${hasXiaobaiRequest ? '\nNOTE: All references to "Jack" will be replaced with "Xiaobai" in the final output.' : ''}`,
    missingMaterials: [
      "Text overlay graphics for opening",
      "Motion graphics templates for character intro",
      "Logo file for ending",
      "Upbeat electronic music track (or approval to remix original)",
      "Brand color palette for consistent grading",
      ...(hasXiaobaiRequest ? ["Reference images/footage of Xiaobai character (if different appearance needed)"] : []),
    ],
  }
}

const mockFinalStoryboard: StoryboardShot[] = [
  {
    shotNumber: 1,
    firstFrameImage: "",
    visualDescription: "Vertical crop of city skyline, dawn colors enhanced",
    contentDescription: "Opening with text overlay 'In a world of millions...'",
    startSeconds: 0,
    endSeconds: 5,
    durationSeconds: 5,
    shotSize: "Wide",
    cameraAngle: "Eye Level",
    cameraMovement: "Slow zoom in",
    focalLengthDepth: "Wide angle, enhanced contrast",
    lighting: "Dawn light, boosted warmth",
    music: "Upbeat electronic intro",
    dialogueVoiceover: "None",
  },
  {
    shotNumber: 2,
    firstFrameImage: "",
    visualDescription: "Quick cut montage of protagonist routine",
    contentDescription: "Morning routine - coffee, phone, commute",
    startSeconds: 5,
    endSeconds: 15,
    durationSeconds: 10,
    shotSize: "Mixed - CU to Medium",
    cameraAngle: "Various",
    cameraMovement: "Quick cuts, 1-2s each",
    focalLengthDepth: "Shallow depth for intimacy",
    lighting: "Warm indoor to cool outdoor",
    music: "Beat drops, rhythm matches cuts",
    dialogueVoiceover: "None",
  },
  {
    shotNumber: 3,
    firstFrameImage: "",
    visualDescription: "Close-up protagonist with motion graphics",
    contentDescription: "Contemplative moment with animated elements",
    startSeconds: 15,
    endSeconds: 25,
    durationSeconds: 10,
    shotSize: "Close-up",
    cameraAngle: "Profile to 3/4",
    cameraMovement: "Slow push in",
    focalLengthDepth: "85mm, bokeh enhanced",
    lighting: "Window light, lens flare added",
    music: "Melodic bridge section",
    dialogueVoiceover: "None",
  },
  {
    shotNumber: 4,
    firstFrameImage: "",
    visualDescription: "Speed ramp montage of encounter",
    contentDescription: "Key moments of connection, dynamic editing",
    startSeconds: 25,
    endSeconds: 45,
    durationSeconds: 20,
    shotSize: "Mixed",
    cameraAngle: "Dynamic angles",
    cameraMovement: "Speed ramps, whip pans",
    focalLengthDepth: "Varies for effect",
    lighting: "Building warmth",
    music: "Building to crescendo",
    dialogueVoiceover: "Text overlays: 'Finding Connection'",
  },
  {
    shotNumber: 5,
    firstFrameImage: "",
    visualDescription: "Slow motion resolution moment",
    contentDescription: "Hopeful ending with logo fade in",
    startSeconds: 45,
    endSeconds: 60,
    durationSeconds: 15,
    shotSize: "Medium to Wide",
    cameraAngle: "Eye Level",
    cameraMovement: "Slow motion, 50% speed",
    focalLengthDepth: "Medium depth, soft overall",
    lighting: "Golden hour warmth",
    music: "Melodic resolution, fade out",
    dialogueVoiceover: "CTA: 'Start your journey'",
  },
]

export default function RemixPage() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [step, setStep] = useState<AnalysisStep>("upload")
  const [analysisResult, setAnalysisResult] = useState<RemixAnalysisResult | null>(null)
  const [generatedScript, setGeneratedScript] = useState<GeneratedScript | null>(null)
  const [finalStoryboard, setFinalStoryboard] = useState<StoryboardShot[] | null>(null)
  const [userModifications, setUserModifications] = useState("")
  const [initialRequirements, setInitialRequirements] = useState("")
  const [referenceImages, setReferenceImages] = useState<File[]>([])
  const [completedSteps, setCompletedSteps] = useState<string[]>([])
  const [isGeneratingVideo, setIsGeneratingVideo] = useState(false)
  const [videoGenerated, setVideoGenerated] = useState(false)
  const [isVideoPlaying, setIsVideoPlaying] = useState(false)
  // Video preview uses native HTML5 controls

  // Character and Scene Views state
  const [characters, setCharacters] = useState<CharacterView[]>([])
  const [scenes, setScenes] = useState<SceneView[]>([])

  // Track which step to display in UI
  const [displayStep, setDisplayStep] = useState<string>("analysis")

  // 🔌 Real API State
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [realStoryboard, setRealStoryboard] = useState<SocialSaverStoryboard | null>(null)

  // 🎬 Video Generation State
  const [generationProgress, setGenerationProgress] = useState<{
    stage: "idle" | "stylizing" | "generating" | "merging" | "complete" | "error"
    currentShot: number
    totalShots: number
    message: string
  }>({ stage: "idle", currentShot: 0, totalShots: 0, message: "" })
  const [generatedVideoUrl, setGeneratedVideoUrl] = useState<string | null>(null)
  
  // Redirect to batch mode if mode=batch
  useEffect(() => {
    if (searchParams.get("mode") === "batch") {
      router.replace("/dashboard/remix/batch")
    }
  }, [searchParams, router])
  
  // Handle continue from batch mode - load completed job analysis
  useEffect(() => {
    if (searchParams.get("continue") === "true") {
      const savedJob = sessionStorage.getItem("continueRemixJob")
      if (savedJob) {
        try {
          const jobData = JSON.parse(savedJob)
          if (jobData.analysisResult) {
            // Load the analysis result and set to results step
            setAnalysisResult(jobData.analysisResult)
            setStep("results")
            setDisplayStep("analysis")
            setCompletedSteps(["analysis"])
            
            // If there was a source post with requirements, set initial requirements
            if (jobData.sourcePost?.title) {
              setInitialRequirements(`Remix: ${jobData.sourcePost.title}`)
            }
            
            // Clear the session storage after loading
            sessionStorage.removeItem("continueRemixJob")
          }
        } catch (e) {
          console.error("Failed to load continue job:", e)
        }
      }
    }
  }, [searchParams])

  const getCurrentWorkflowStep = () => {
    if (step === "video" || videoGenerated) return "video"
    if (step === "storyboard" || step === "generatingStoryboard") return "storyboard"
    if (step === "views") return "views"
    if (step === "script" || step === "generating") return "script"
    return "analysis"
  }

  // Handle clicking on a step in the step indicator
  const handleStepClick = (stepId: string) => {
    // Map stepId to appropriate AnalysisStep
    switch (stepId) {
      case "analysis":
        setDisplayStep("analysis")
        if (analysisResult) {
          setStep("results")
        }
        break
      case "script":
        setDisplayStep("script")
        if (generatedScript) {
          setStep("script")
        }
        break
      case "views":
        setDisplayStep("views")
        if (completedSteps.includes("script")) {
          setStep("views")
        }
        break
      case "storyboard":
        setDisplayStep("storyboard")
        if (finalStoryboard) {
          setStep("storyboard")
        }
        break
      case "video":
        setDisplayStep("video")
        if (videoGenerated) {
          setStep("video")
        }
        break
    }
  }

  const handleUploadSubmit = async (files: File[], prompt: string, refImages: File[]) => {
    setStep("analyzing")
    setInitialRequirements(prompt)
    setReferenceImages(refImages)
    setApiError(null)

    try {
      // 🔌 Real API Call: Upload video and trigger analysis
      const videoFile = files[0]
      if (!videoFile) {
        throw new Error("No video file selected")
      }

      console.log("📤 Uploading video:", videoFile.name)
      const uploadResult = await uploadVideo(videoFile)
      console.log("✅ Upload complete, job_id:", uploadResult.job_id)

      setCurrentJobId(uploadResult.job_id)

      // Poll for storyboard data (analysis happens automatically on backend)
      let retries = 0
      const maxRetries = 60 // Max 3 minutes (60 * 3s)
      let storyboardData: SocialSaverStoryboard | null = null

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
      const processedStoryboard = storyboardData.storyboard.map((shot) => ({
        ...shot,
        firstFrameImage: shot.firstFrameImage
          ? getAssetUrl(uploadResult.job_id, shot.firstFrameImage)
          : "",
      }))

      setRealStoryboard({ ...storyboardData, storyboard: processedStoryboard })

      // Convert to RemixAnalysisResult format (using real storyboard + mock theme/script for now)
      // TODO: Replace with real Story Theme and Script Analysis when prompts are ready
      const totalDuration = processedStoryboard.reduce((sum, s) => sum + s.durationSeconds, 0)
      const realAnalysisResult: RemixAnalysisResult = {
        storyTheme: {
          ...mockAnalysisResult.storyTheme,
          basicInfo: {
            ...mockAnalysisResult.storyTheme.basicInfo,
            title: storyboardData.sourceVideo || "Uploaded Video",
            duration: `${Math.round(totalDuration)}s`,
          },
        },
        scriptAnalysis: mockAnalysisResult.scriptAnalysis,
        storyboard: processedStoryboard,
      }

      // Apply modifications based on user requirements
      const modifiedAnalysis = generateModifiedAnalysis(realAnalysisResult, prompt)
      setAnalysisResult(modifiedAnalysis)

      // Pre-fill user modifications with initial requirements
      if (prompt) {
        setUserModifications(prompt)
      }

      setStep("results")
      setDisplayStep("analysis")
      setCompletedSteps(["analysis"])
    } catch (error) {
      console.error("❌ Upload/Analysis error:", error)
      setApiError(error instanceof Error ? error.message : "Unknown error occurred")
      setStep("upload") // Go back to upload step on error
    }
  }

  const handleGenerateScript = async () => {
    setStep("generating")
    
    // Simulate API call for script generation
    await new Promise((resolve) => setTimeout(resolve, 2000))
    
    setGeneratedScript(generateMockScript(userModifications, referenceImages))
    setStep("script")
    setDisplayStep("script")
  }

  const handleRegenerateScript = async (newRequirements: string, newRefImages: File[]) => {
    setUserModifications(newRequirements)
    setReferenceImages(newRefImages)
    setStep("generating")
    
    // Simulate API call for script regeneration
    await new Promise((resolve) => setTimeout(resolve, 2000))
    
    setGeneratedScript(generateMockScript(newRequirements, newRefImages))
    setStep("script")
    setDisplayStep("script")
  }

  const handleScriptConfirm = async (editedScript: string, materials: { name: string; uploaded: boolean }[], generateWithoutMaterials: boolean) => {
    // After script confirmation, go to character/scene views step
    setCompletedSteps(["analysis", "script"])
    
    // Initialize default characters and scenes based on analysis
    if (characters.length === 0) {
      const defaultCharacters: CharacterView[] = [
        {
          id: "char-1",
          name: analysisResult?.scriptAnalysis.characterSystem.protagonist.split(" - ")[0] || "Main Character",
          description: analysisResult?.scriptAnalysis.characterSystem.protagonist || "",
          confirmed: false,
        }
      ]
      setCharacters(defaultCharacters)
    }
    
    if (scenes.length === 0) {
      const defaultScenes: SceneView[] = [
        {
          id: "scene-1",
          name: "Opening Scene",
          description: analysisResult?.storyTheme.basicInfo.background || "Urban setting",
          confirmed: false,
        },
        {
          id: "scene-2",
          name: "Main Scene",
          description: "Primary location for story events",
          confirmed: false,
        }
      ]
      setScenes(defaultScenes)
    }
    
    setStep("views")
    setDisplayStep("views")
  }
  
  const handleViewsConfirm = async () => {
    setStep("generatingStoryboard")
    setCompletedSteps(["analysis", "script", "views"])
    
    // Simulate API call for storyboard generation
    await new Promise((resolve) => setTimeout(resolve, 2500))
    
    setFinalStoryboard(mockFinalStoryboard)
    setStep("storyboard")
    setDisplayStep("storyboard")
    setCompletedSteps(["analysis", "script", "views", "storyboard"])
  }
  
  const handleViewsBack = () => {
    setStep("script")
    setDisplayStep("script")
  }

  const handleUpdateStoryboard = (updatedShots: StoryboardShot[]) => {
    setFinalStoryboard(updatedShots)
  }

  const handleConfirmStoryboard = async () => {
    if (!currentJobId) {
      setApiError("No job ID found. Please upload a video first.")
      return
    }

    setIsGeneratingVideo(true)
    setStep("video")
    setDisplayStep("video")
    setApiError(null)

    try {
      // Get the shots from the storyboard
      const shots = realStoryboard?.storyboard || analysisResult?.storyboard || []
      const totalShots = shots.length

      // 🎨 Stage 1: Stylize all shots
      setGenerationProgress({
        stage: "stylizing",
        currentShot: 0,
        totalShots,
        message: "Generating style frames with AI..."
      })

      for (let i = 0; i < totalShots; i++) {
        const shotId = `shot_${String(i + 1).padStart(2, "0")}`
        setGenerationProgress({
          stage: "stylizing",
          currentShot: i + 1,
          totalShots,
          message: `Stylizing shot ${i + 1} of ${totalShots}...`
        })

        try {
          await runTask("stylize", currentJobId, shotId)
        } catch (e) {
          console.warn(`Stylize shot ${shotId} failed, continuing...`, e)
        }
      }

      // 🎬 Stage 2: Generate videos for all shots (async - need to poll)
      setGenerationProgress({
        stage: "generating",
        currentShot: 0,
        totalShots,
        message: "Starting video generation..."
      })

      // Trigger video generation for all shots
      for (let i = 0; i < totalShots; i++) {
        const shotId = `shot_${String(i + 1).padStart(2, "0")}`
        try {
          await runTask("video_generate", currentJobId, shotId)
        } catch (e) {
          console.warn(`Video generate trigger for ${shotId} failed`, e)
        }
      }

      // Poll for video generation completion
      let pollAttempts = 0
      const maxPollAttempts = 120 // 10 minutes max (120 * 5s)
      let finalVideoCount = 0

      while (pollAttempts < maxPollAttempts) {
        const status = await getJobStatus(currentJobId)
        finalVideoCount = status.videoGeneratedCount

        setGenerationProgress({
          stage: "generating",
          currentShot: status.videoGeneratedCount,
          totalShots: status.totalShots,
          message: `Generating videos: ${status.videoGeneratedCount} of ${status.totalShots} complete...`
        })

        // Check if all videos are generated
        if (status.videoGeneratedCount >= status.totalShots) {
          break
        }

        // Check if there are still running tasks
        if (status.runningCount === 0 && status.videoGeneratedCount < status.totalShots) {
          // No running tasks but not all videos done - some might have failed (e.g., quota exceeded)
          console.warn(`Video generation completed with ${status.videoGeneratedCount}/${status.totalShots} videos (some may have failed due to API limits)`)
          break
        }

        await new Promise(resolve => setTimeout(resolve, 5000)) // Poll every 5 seconds
        pollAttempts++
      }

      // Check if we have any videos to merge
      if (finalVideoCount === 0) {
        throw new Error("No videos were generated. Please check your API quota and try again.")
      }

      const hasPartialFailure = finalVideoCount < totalShots

      // 🔗 Stage 3: Merge all videos
      setGenerationProgress({
        stage: "merging",
        currentShot: finalVideoCount,
        totalShots,
        message: hasPartialFailure
          ? `Merging ${finalVideoCount} of ${totalShots} shots (some failed due to API limits)...`
          : "Merging all shots into final video..."
      })

      const mergeResult = await runTask("merge", currentJobId)

      // Set the final video URL
      if (mergeResult.file) {
        const videoUrl = getAssetUrl(currentJobId, mergeResult.file)
        setGeneratedVideoUrl(videoUrl)
      }

      setGenerationProgress({
        stage: "complete",
        currentShot: finalVideoCount,
        totalShots,
        message: hasPartialFailure
          ? `Video created with ${finalVideoCount} of ${totalShots} shots (some failed due to API limits)`
          : "Video generation complete!"
      })

      setIsGeneratingVideo(false)
      setVideoGenerated(true)
      setCompletedSteps(["analysis", "script", "views", "storyboard", "video"])

    } catch (error) {
      console.error("Video generation error:", error)
      const errorMessage = error instanceof Error ? error.message : "Video generation failed"
      const isQuotaError = errorMessage.includes("quota") || errorMessage.includes("No videos were generated")

      setGenerationProgress({
        stage: "error",
        currentShot: 0,
        totalShots: 0,
        message: isQuotaError
          ? "API quota exceeded - Google Veo rate limit reached"
          : errorMessage
      })
      setApiError(isQuotaError
        ? "Video generation failed due to API quota limits. Please wait a few minutes and try again, or check your Google Cloud billing settings."
        : errorMessage
      )
      setIsGeneratingVideo(false)
    }
  }

  const handleStartOver = () => {
    setStep("upload")
    setDisplayStep("analysis")
    setAnalysisResult(null)
    setGeneratedScript(null)
    setFinalStoryboard(null)
    setUserModifications("")
    setInitialRequirements("")
    setReferenceImages([])
    setCompletedSteps([])
    setIsGeneratingVideo(false)
    setVideoGenerated(false)
    setCharacters([])
    setScenes([])
    // Reset API state
    setCurrentJobId(null)
    setApiError(null)
    setRealStoryboard(null)
    setGenerationProgress({ stage: "idle", currentShot: 0, totalShots: 0, message: "" })
    setGeneratedVideoUrl(null)
  }

  const showStepIndicator = step !== "upload"

  // Determine what content to show based on displayStep
  const shouldShowAnalysis = displayStep === "analysis" && (step === "results" || step === "analyzing" || completedSteps.includes("analysis"))
  const shouldShowScript = displayStep === "script" && (step === "script" || step === "generating" || completedSteps.includes("script"))
  const shouldShowViews = displayStep === "views" && (step === "views" || completedSteps.includes("views"))
  const shouldShowStoryboard = displayStep === "storyboard" && (step === "storyboard" || step === "generatingStoryboard" || completedSteps.includes("storyboard"))
  const shouldShowVideo = displayStep === "video" && (step === "video" || completedSteps.includes("video"))

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Video Remix</h1>
          <p className="text-muted-foreground mt-1">
            Upload videos, analyze content, and generate creative remixes
          </p>
        </div>
        <div className="flex items-center gap-3">
          {step === "upload" && (
            <Link href="/dashboard/remix/batch">
              <Button
                variant="outline"
                className="border-border text-foreground hover:bg-secondary bg-transparent"
              >
                <Layers className="w-4 h-4 mr-2" />
                Batch Mode
              </Button>
            </Link>
          )}
          {step !== "upload" && (
            <Button
              variant="outline"
              onClick={handleStartOver}
              className="border-border text-foreground hover:bg-secondary bg-transparent"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Start Over
            </Button>
          )}
        </div>
      </div>

      {/* Step: Upload */}
      {step === "upload" && (
        <div className="space-y-4">
          {apiError && (
            <Card className="bg-red-500/10 border-red-500">
              <CardContent className="py-4">
                <p className="text-red-500 text-sm">
                  <strong>Error:</strong> {apiError}
                </p>
              </CardContent>
            </Card>
          )}
          <VideoUpload onSubmit={handleUploadSubmit} />
        </div>
      )}

      {/* Main Content with Step Indicator */}
      {showStepIndicator && (
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-8">
          {/* Step Indicator - Left Side */}
          <div className="hidden lg:block sticky top-24 h-fit">
            <StepIndicator
              steps={WORKFLOW_STEPS}
              currentStep={getCurrentWorkflowStep()}
              completedSteps={completedSteps}
              onStepClick={handleStepClick}
            />
          </div>

          {/* Mobile Step Indicator */}
          <div className="lg:hidden">
            <div className="flex items-center gap-2 overflow-x-auto pb-2">
              {WORKFLOW_STEPS.map((s, i) => {
                const isClickable = completedSteps.includes(s.id) || getCurrentWorkflowStep() === s.id
                return (
                  <div key={s.id} className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => isClickable && handleStepClick(s.id)}
                      disabled={!isClickable}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                        completedSteps.includes(s.id) 
                          ? 'bg-accent text-accent-foreground cursor-pointer hover:bg-accent/80' 
                          : getCurrentWorkflowStep() === s.id
                          ? 'bg-accent/20 text-accent border border-accent cursor-pointer'
                          : 'bg-secondary text-muted-foreground cursor-not-allowed'
                      }`}
                    >
                      {s.label}
                    </button>
                    {i < WORKFLOW_STEPS.length - 1 && (
                      <div className={`w-4 h-0.5 ${completedSteps.includes(s.id) ? 'bg-accent' : 'bg-border'}`} />
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Content Area */}
          <div className="space-y-8">
            {/* Step: Analyzing */}
            {step === "analyzing" && (
              <Card className="bg-card border-border">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="w-12 h-12 text-accent animate-spin mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    Analyzing Your Video
                  </h3>
                  <p className="text-muted-foreground text-center max-w-md">
                    Extracting story themes, analyzing script elements, and breaking down storyboard shots...
                    {initialRequirements && (
                      <span className="block mt-2 text-accent">
                        Applying your modifications: &quot;{initialRequirements.substring(0, 50)}...&quot;
                      </span>
                    )}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Step: Results (Analysis) */}
            {shouldShowAnalysis && step !== "analyzing" && analysisResult && (
              <div className="space-y-8">
                {/* Show AI acknowledgment and suggested modifications if any */}
                {analysisResult.suggestedModifications && analysisResult.suggestedModifications.length > 0 && (
                  <Card className="bg-accent/10 border-accent">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base text-accent flex items-center gap-2">
                        <Sparkles className="w-4 h-4" />
                        Understanding Your Request
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <p className="text-sm text-foreground">
                        I noticed you want to replace the character with Xiaobai. I&apos;ve completed the video analysis below. Once you review the results, I&apos;ll confirm the modification details with you before proceeding.
                      </p>
                      <div className="border-t border-accent/30 pt-3">
                        <p className="text-xs text-muted-foreground mb-2">Planned modifications:</p>
                        <ul className="text-sm text-foreground space-y-1">
                          {analysisResult.suggestedModifications.map((mod, i) => (
                            <li key={i} className="flex items-start gap-2">
                              <span className="text-accent">-</span>
                              {mod}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </CardContent>
                  </Card>
                )}
                
                <StoryThemeTable data={analysisResult.storyTheme} />
                <ScriptAnalysisTable data={analysisResult.scriptAnalysis} />
                <StoryboardTable data={analysisResult.storyboard} />

                {/* User Modification Input */}
                <Card className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="text-foreground">Describe Your Remix Vision</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Textarea
                      placeholder="Based on the analysis above, describe what kind of remix you want to create. E.g., 'Create a 60-second highlight reel for Instagram with upbeat music and text overlays highlighting the emotional journey...'"
                      value={userModifications}
                      onChange={(e) => setUserModifications(e.target.value)}
                      rows={4}
                      className="resize-none bg-secondary border-border"
                    />
                    <Button
                      onClick={handleGenerateScript}
                      disabled={!userModifications.trim()}
                      className="w-full bg-accent text-accent-foreground hover:bg-accent/90"
                      size="lg"
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      Generate Remix Script
                    </Button>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Step: Generating Script */}
            {step === "generating" && (
              <Card className="bg-card border-border">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="w-12 h-12 text-accent animate-spin mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    Generating Remix Script
                  </h3>
                  <p className="text-muted-foreground text-center max-w-md">
                    Creating a customized script based on your requirements and the video analysis...
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Step: Script */}
            {shouldShowScript && step !== "generating" && generatedScript && (
              <GeneratedScriptCard
                data={generatedScript}
                userRequirements={userModifications}
                initialReferenceImages={referenceImages}
                onConfirm={handleScriptConfirm}
                onRegenerate={handleRegenerateScript}
              />
            )}

            {/* Step: Character & Scene Views */}
            {shouldShowViews && step === "views" && (
              <CharacterSceneViews
                characters={characters}
                scenes={scenes}
                onCharactersChange={setCharacters}
                onScenesChange={setScenes}
                onConfirm={handleViewsConfirm}
                onBack={handleViewsBack}
              />
            )}

            {/* Step: Generating Storyboard */}
            {step === "generatingStoryboard" && (
              <Card className="bg-card border-border">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="w-12 h-12 text-accent animate-spin mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    Generating Storyboard
                  </h3>
                  <p className="text-muted-foreground text-center max-w-md">
                    Creating detailed storyboard based on confirmed script and materials...
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Step: Storyboard with Chat */}
            {shouldShowStoryboard && step !== "generatingStoryboard" && finalStoryboard && (
              <div className="space-y-6">
                <Card className="bg-accent/10 border-accent">
                  <CardContent className="py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
                        <Sparkles className="w-5 h-5 text-accent-foreground" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground">Storyboard Generated!</h3>
                        <p className="text-sm text-muted-foreground">
                          Review the shots below. Use the chat to request any modifications.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                <StoryboardTable data={finalStoryboard} title="Remix Storyboard" />
                
                <StoryboardChat
                  storyboard={finalStoryboard}
                  onUpdateStoryboard={handleUpdateStoryboard}
                  onConfirm={handleConfirmStoryboard}
                />
              </div>
            )}

            {/* Step: Generating Video */}
            {step === "video" && isGeneratingVideo && (
              <Card className="bg-card border-border">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="w-12 h-12 text-accent animate-spin mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    {generationProgress.stage === "stylizing" && "Generating Style Frames"}
                    {generationProgress.stage === "generating" && "Generating Video Clips"}
                    {generationProgress.stage === "merging" && "Merging Final Video"}
                    {generationProgress.stage === "idle" && "Preparing..."}
                  </h3>
                  <p className="text-muted-foreground text-center max-w-md mb-4">
                    {generationProgress.message}
                  </p>
                  {generationProgress.totalShots > 0 && (
                    <div className="w-full max-w-md">
                      <div className="flex justify-between text-sm text-muted-foreground mb-2">
                        <span>Progress</span>
                        <span>{generationProgress.currentShot} / {generationProgress.totalShots} shots</span>
                      </div>
                      <div className="w-full bg-secondary rounded-full h-2">
                        <div
                          className="bg-accent h-2 rounded-full transition-all duration-300"
                          style={{
                            width: `${(generationProgress.currentShot / generationProgress.totalShots) * 100}%`
                          }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-2 text-center">
                        {generationProgress.stage === "stylizing" && "Using Google Imagen to create style frames..."}
                        {generationProgress.stage === "generating" && "Using Google Veo to generate video clips..."}
                        {generationProgress.stage === "merging" && "Combining all clips into final video..."}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Step: Video Generation Failed */}
            {step === "video" && !isGeneratingVideo && !videoGenerated && generationProgress.stage === "error" && (
              <Card className="bg-card border-red-500/30 border-2">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mb-4">
                    <Video className="w-8 h-8 text-red-500" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    Video Generation Failed
                  </h3>
                  <p className="text-muted-foreground text-center max-w-md mb-2">
                    {generationProgress.message}
                  </p>
                  {apiError && (
                    <p className="text-red-500 text-sm text-center max-w-md mb-6">
                      {apiError}
                    </p>
                  )}
                  <div className="flex gap-3">
                    <Button
                      onClick={() => {
                        setGenerationProgress({ stage: "idle", currentShot: 0, totalShots: 0, message: "" })
                        setApiError(null)
                        handleConfirmStoryboard()
                      }}
                      className="bg-accent text-accent-foreground hover:bg-accent/90"
                    >
                      Retry Generation
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setStep("storyboard")
                        setDisplayStep("storyboard")
                        setGenerationProgress({ stage: "idle", currentShot: 0, totalShots: 0, message: "" })
                        setApiError(null)
                      }}
                      className="border-border text-foreground hover:bg-secondary bg-transparent"
                    >
                      Back to Storyboard
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Step: Video Complete */}
            {shouldShowVideo && videoGenerated && (
              <div className="space-y-6">
                <Card className="bg-card border-border overflow-hidden">
                  <CardContent className="p-0">
                    {/* Video Preview Area */}
                    <div className="relative aspect-video bg-black">
                      {generatedVideoUrl ? (
                        <video
                          className="w-full h-full object-contain"
                          controls
                          preload="metadata"
                          key={generatedVideoUrl}
                        >
                          <source src={generatedVideoUrl} type="video/mp4" />
                          Your browser does not support the video tag.
                        </video>
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                          <p>Video not available</p>
                        </div>
                      )}
                    </div>
                    
                    {/* Video Info & Actions */}
                    <div className="p-6">
                      {/* Warning for partial generation */}
                      {generationProgress.currentShot < generationProgress.totalShots && generationProgress.totalShots > 0 && (
                        <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                          <p className="text-yellow-600 dark:text-yellow-400 text-sm">
                            ⚠️ Only {generationProgress.currentShot} of {generationProgress.totalShots} shots were generated.
                            Some shots failed due to API rate limits. The video contains available shots only.
                          </p>
                        </div>
                      )}

                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h3 className="text-xl font-semibold text-foreground">Video Generated Successfully!</h3>
                          <p className="text-muted-foreground mt-1">
                            Your remix video is ready for download and sharing.
                          </p>
                        </div>
                        <div className="w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center">
                          <Video className="w-6 h-6 text-accent" />
                        </div>
                      </div>
                      
                      {/* Video Details */}
                      <div className="grid grid-cols-3 gap-4 mb-6 text-sm">
                        <div className="bg-secondary/50 rounded-lg p-3">
                          <p className="text-muted-foreground">Duration</p>
                          <p className="text-foreground font-medium">60 seconds</p>
                        </div>
                        <div className="bg-secondary/50 rounded-lg p-3">
                          <p className="text-muted-foreground">Format</p>
                          <p className="text-foreground font-medium">MP4 (H.264)</p>
                        </div>
                        <div className="bg-secondary/50 rounded-lg p-3">
                          <p className="text-muted-foreground">Resolution</p>
                          <p className="text-foreground font-medium">1080x1920 (9:16)</p>
                        </div>
                      </div>
                      
                      {/* Action Buttons */}
                      <div className="flex gap-3">
                        <Button
                          className="flex-1 bg-accent text-accent-foreground hover:bg-accent/90"
                          disabled={!generatedVideoUrl}
                          onClick={async () => {
                            if (generatedVideoUrl) {
                              try {
                                // Fetch video as blob to handle cross-origin download
                                const response = await fetch(generatedVideoUrl)
                                const blob = await response.blob()
                                const blobUrl = URL.createObjectURL(blob)
                                const a = document.createElement("a")
                                a.href = blobUrl
                                a.download = `remix-${currentJobId || "video"}.mp4`
                                document.body.appendChild(a)
                                a.click()
                                document.body.removeChild(a)
                                URL.revokeObjectURL(blobUrl)
                              } catch (e) {
                                // Fallback: open in new tab
                                window.open(generatedVideoUrl, "_blank")
                              }
                            }
                          }}
                        >
                          <Download className="w-4 h-4 mr-2" />
                          Download Video
                        </Button>
                        <Button variant="outline" className="flex-1 border-border text-foreground hover:bg-secondary bg-transparent">
                          <Share2 className="w-4 h-4 mr-2" />
                          Share
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* Show final storyboard for reference */}
                {finalStoryboard && (
                  <StoryboardTable data={finalStoryboard} title="Final Storyboard Reference" />
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
