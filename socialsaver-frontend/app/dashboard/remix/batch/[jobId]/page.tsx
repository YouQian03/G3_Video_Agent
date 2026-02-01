"use client"

import { useState, useEffect } from "react"
import { useRouter, useParams } from "next/navigation"
import { StoryThemeTable } from "@/components/remix/story-theme-table"
import { ScriptAnalysisTable } from "@/components/remix/script-analysis-table"
import { StoryboardTable } from "@/components/remix/storyboard-table"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import {
  ArrowLeft,
  Play,
  FileText,
  Film,
  Palette,
  CheckCircle2,
  Clock,
  Sparkles,
} from "lucide-react"
import type { BatchRemixJob } from "@/lib/types/remix"

export default function BatchJobDetailPage() {
  const router = useRouter()
  const params = useParams()
  const [job, setJob] = useState<BatchRemixJob | null>(null)
  const [activeTab, setActiveTab] = useState("theme")

  useEffect(() => {
    // Load job from sessionStorage
    const storedJob = sessionStorage.getItem("selectedBatchJob")
    if (storedJob) {
      try {
        const parsedJob = JSON.parse(storedJob)
        if (parsedJob.id === `job-${params.jobId}` || parsedJob.id === params.jobId) {
          setJob(parsedJob)
        }
      } catch (e) {
        console.error("Failed to parse job:", e)
      }
    }
  }, [params.jobId])

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <div className="w-16 h-16 bg-secondary rounded-2xl flex items-center justify-center mb-4">
          <FileText className="w-8 h-8 text-muted-foreground" />
        </div>
        <h1 className="text-2xl font-bold text-foreground mb-2">Job Not Found</h1>
        <p className="text-muted-foreground mb-4">
          The requested analysis job could not be found.
        </p>
        <Button
          onClick={() => router.push("/dashboard/remix/batch")}
          className="bg-accent text-accent-foreground hover:bg-accent/90"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Queue
        </Button>
      </div>
    )
  }

  const handleContinueToRemix = () => {
    // Store the analysis result for the remix workflow
    sessionStorage.setItem("batchJobAnalysis", JSON.stringify(job.analysisResult))
    router.push("/dashboard/remix?fromBatch=true")
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/dashboard/remix/batch")}
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Queue
          </Button>
        </div>
      </div>

      {/* Job Info Card */}
      <Card className="bg-card border-border">
        <CardContent className="py-4">
          <div className="flex flex-col lg:flex-row lg:items-center gap-6">
            {/* Thumbnail */}
            <div className="relative w-48 h-28 bg-secondary rounded-lg overflow-hidden flex-shrink-0">
              {job.thumbnailUrl ? (
                <img
                  src={job.thumbnailUrl || "/placeholder.svg"}
                  alt={job.videoName}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Play className="w-10 h-10 text-muted-foreground" />
                </div>
              )}
            </div>

            {/* Info */}
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-foreground">{job.videoName}</h1>
                <Badge className="bg-accent/20 text-accent border-accent/30">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  Analysis Complete
                </Badge>
              </div>
              
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                {job.startedAt && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    Started: {new Date(job.startedAt).toLocaleString()}
                  </span>
                )}
                {job.completedAt && (
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" />
                    Completed: {new Date(job.completedAt).toLocaleString()}
                  </span>
                )}
              </div>

              {job.sourcePost && (
                <p className="text-sm text-muted-foreground">
                  Source: {job.sourcePost.platform.toUpperCase()} - {job.sourcePost.author}
                </p>
              )}
            </div>

            {/* Continue Action */}
            <Button
              onClick={handleContinueToRemix}
              className="bg-accent text-accent-foreground hover:bg-accent/90"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Continue to Remix
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Results Tabs */}
      {job.analysisResult && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-secondary">
            <TabsTrigger
              value="theme"
              className="data-[state=active]:bg-accent data-[state=active]:text-accent-foreground"
            >
              <Palette className="w-4 h-4 mr-2" />
              Story Theme
            </TabsTrigger>
            <TabsTrigger
              value="script"
              className="data-[state=active]:bg-accent data-[state=active]:text-accent-foreground"
            >
              <FileText className="w-4 h-4 mr-2" />
              Script Analysis
            </TabsTrigger>
            <TabsTrigger
              value="storyboard"
              className="data-[state=active]:bg-accent data-[state=active]:text-accent-foreground"
            >
              <Film className="w-4 h-4 mr-2" />
              Storyboard
            </TabsTrigger>
          </TabsList>

          <TabsContent value="theme" className="mt-4">
            <StoryThemeTable data={job.analysisResult.storyTheme} showSaveButton={false} />
          </TabsContent>

          <TabsContent value="script" className="mt-4">
            <ScriptAnalysisTable data={job.analysisResult.scriptAnalysis} showSaveButton={false} />
          </TabsContent>

          <TabsContent value="storyboard" className="mt-4">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-foreground flex items-center gap-2">
                  <Film className="w-5 h-5" />
                  Storyboard Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <StoryboardTable data={job.analysisResult.storyboard} showSaveButtons={false} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
