"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  Sparkles,
  Image as ImageIcon,
  FileText,
  Play,
  CheckCircle,
  ArrowRight,
  RefreshCw,
} from "lucide-react";

import { AssetPreview } from "@/components/remix/asset-preview";
import { DiffView } from "@/components/remix/diff-view";
import { PromptReview } from "@/components/remix/prompt-review";

import {
  triggerRemix,
  pollRemixStatus,
  getRemixDiff,
  getRemixPrompts,
  triggerAssetGeneration,
  pollAssetGeneration,
  getGeneratedAssets,
  type RemixDiffResponse,
  type RemixPromptsResponse,
  type GeneratedAssetsResponse,
} from "@/lib/api";

type WorkflowStep = "input" | "remixing" | "diff" | "assets" | "prompts" | "ready";

export default function AdvancedRemixPage() {
  const searchParams = useSearchParams();

  // Job ID state
  const [jobId, setJobId] = useState(searchParams.get("job_id") || "");
  const [isValidJob, setIsValidJob] = useState(false);

  // Remix state
  const [remixPrompt, setRemixPrompt] = useState("");
  const [isRemixing, setIsRemixing] = useState(false);
  const [remixError, setRemixError] = useState<string | null>(null);

  // Data state
  const [diffData, setDiffData] = useState<RemixDiffResponse | null>(null);
  const [promptsData, setPromptsData] = useState<RemixPromptsResponse | null>(null);
  const [assetsData, setAssetsData] = useState<GeneratedAssetsResponse | null>(null);

  // Asset generation state
  const [isGeneratingAssets, setIsGeneratingAssets] = useState(false);
  const [assetGenError, setAssetGenError] = useState<string | null>(null);

  // Current step
  const [currentStep, setCurrentStep] = useState<WorkflowStep>("input");
  const [activeTab, setActiveTab] = useState<"diff" | "assets" | "prompts">("diff");

  // Validate job ID on change
  useEffect(() => {
    setIsValidJob(jobId.trim().length > 0);
  }, [jobId]);

  // Handle remix submission
  const handleSubmitRemix = async () => {
    if (!jobId || !remixPrompt.trim()) return;

    setIsRemixing(true);
    setRemixError(null);
    setCurrentStep("remixing");

    try {
      // Trigger remix
      await triggerRemix(jobId, remixPrompt);

      // Poll for completion
      await pollRemixStatus(
        jobId,
        (status) => {
          console.log("Remix status:", status);
        },
        2000,
        90 // 3 minutes max
      );

      // Fetch diff data
      const diff = await getRemixDiff(jobId);
      setDiffData(diff);

      // Fetch prompts data
      const prompts = await getRemixPrompts(jobId);
      setPromptsData(prompts);

      setCurrentStep("diff");
      setActiveTab("diff");
    } catch (error) {
      setRemixError(error instanceof Error ? error.message : "Remix failed");
      setCurrentStep("input");
    } finally {
      setIsRemixing(false);
    }
  };

  // Handle asset generation
  const handleGenerateAssets = async () => {
    if (!jobId) return;

    setIsGeneratingAssets(true);
    setAssetGenError(null);

    try {
      // Trigger asset generation
      await triggerAssetGeneration(jobId);

      // Poll for completion
      await pollAssetGeneration(
        jobId,
        (status) => {
          console.log("Asset generation status:", status);
        },
        3000,
        60 // 3 minutes max
      );

      // Fetch generated assets
      const assets = await getGeneratedAssets(jobId);
      setAssetsData(assets);

      setCurrentStep("assets");
      setActiveTab("assets");
    } catch (error) {
      setAssetGenError(error instanceof Error ? error.message : "Asset generation failed");
    } finally {
      setIsGeneratingAssets(false);
    }
  };

  // Load existing data for a job
  const handleLoadExistingJob = async () => {
    if (!jobId) return;

    try {
      // Try to load diff data
      const diff = await getRemixDiff(jobId);
      setDiffData(diff);

      // Try to load prompts data
      const prompts = await getRemixPrompts(jobId);
      setPromptsData(prompts);

      // Try to load assets
      const assets = await getGeneratedAssets(jobId);
      setAssetsData(assets);

      setCurrentStep("diff");
    } catch (error) {
      setRemixError("Could not load existing job data. Make sure the job has been remixed.");
    }
  };

  const getStepStatus = (step: WorkflowStep) => {
    const order: WorkflowStep[] = ["input", "remixing", "diff", "assets", "prompts", "ready"];
    const currentIndex = order.indexOf(currentStep);
    const stepIndex = order.indexOf(step);

    if (stepIndex < currentIndex) return "completed";
    if (stepIndex === currentIndex) return "current";
    return "pending";
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Advanced Remix</h1>
        <p className="text-muted-foreground mt-1">
          M4 Intent Injection + M5 Asset Generation + Prompt Review
        </p>
      </div>

      {/* Progress Indicator */}
      <div className="flex items-center gap-2 p-4 bg-muted/50 rounded-lg overflow-x-auto">
        {[
          { id: "input" as const, label: "Input", icon: FileText },
          { id: "diff" as const, label: "Diff View", icon: Sparkles },
          { id: "assets" as const, label: "Assets", icon: ImageIcon },
          { id: "prompts" as const, label: "Prompts", icon: FileText },
          { id: "ready" as const, label: "Ready", icon: Play },
        ].map((step, index, arr) => (
          <div key={step.id} className="flex items-center gap-2">
            <div
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
                getStepStatus(step.id) === "completed"
                  ? "bg-green-500/20 text-green-500"
                  : getStepStatus(step.id) === "current"
                  ? "bg-blue-500/20 text-blue-500 border border-blue-500"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {getStepStatus(step.id) === "completed" ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <step.icon className="w-4 h-4" />
              )}
              <span className="whitespace-nowrap">{step.label}</span>
            </div>
            {index < arr.length - 1 && (
              <ArrowRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Input */}
      {currentStep === "input" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Step 1: Enter Job ID and Remix Prompt
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Job ID</label>
              <div className="flex gap-2">
                <Input
                  placeholder="e.g., job_d62f0d42"
                  value={jobId}
                  onChange={(e) => setJobId(e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="outline"
                  onClick={handleLoadExistingJob}
                  disabled={!isValidJob}
                >
                  Load Existing
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Enter the job ID from a previously analyzed video
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Remix Prompt</label>
              <Textarea
                placeholder="e.g., Replace McDonald with Mixue Ice Cream, and change the Christmas theme to Valentine's Day."
                value={remixPrompt}
                onChange={(e) => setRemixPrompt(e.target.value)}
                rows={4}
              />
              <p className="text-xs text-muted-foreground">
                Describe how you want to transform the video
              </p>
            </div>

            {remixError && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <p className="text-red-500 text-sm">{remixError}</p>
              </div>
            )}

            <Button
              onClick={handleSubmitRemix}
              disabled={!isValidJob || !remixPrompt.trim() || isRemixing}
              className="w-full"
              size="lg"
            >
              {isRemixing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Processing Intent Injection...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Run M4: Intent Injection
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Remixing */}
      {currentStep === "remixing" && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Loader2 className="w-12 h-12 animate-spin text-blue-500 mb-4" />
            <h3 className="text-lg font-semibold mb-2">Running Intent Injection</h3>
            <p className="text-muted-foreground text-center max-w-md">
              Parsing your intent and generating remixed prompts for all shots...
            </p>
          </CardContent>
        </Card>
      )}

      {/* Steps 3-5: Results Tabs */}
      {(currentStep === "diff" || currentStep === "assets" || currentStep === "prompts" || currentStep === "ready") && (
        <div className="space-y-4">
          {/* Job Info */}
          <Card>
            <CardContent className="py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="font-mono">
                    {jobId}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    {remixPrompt.slice(0, 60)}...
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentStep("input")}
                >
                  <RefreshCw className="w-4 h-4 mr-1" />
                  New Remix
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="diff" className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                Diff View
              </TabsTrigger>
              <TabsTrigger value="assets" className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4" />
                Assets
              </TabsTrigger>
              <TabsTrigger value="prompts" className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Prompts
              </TabsTrigger>
            </TabsList>

            {/* Diff View Tab */}
            <TabsContent value="diff" className="mt-4">
              {diffData ? (
                <div className="space-y-4">
                  <DiffView diffData={diffData} />

                  <Card>
                    <CardContent className="py-4">
                      <div className="flex items-center justify-between">
                        <p className="text-sm text-muted-foreground">
                          Next: Generate character and environment assets
                        </p>
                        <Button
                          onClick={handleGenerateAssets}
                          disabled={isGeneratingAssets}
                        >
                          {isGeneratingAssets ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Generating...
                            </>
                          ) : (
                            <>
                              <ImageIcon className="w-4 h-4 mr-2" />
                              Run M5: Generate Assets
                            </>
                          )}
                        </Button>
                      </div>
                      {assetGenError && (
                        <p className="text-red-500 text-sm mt-2">{assetGenError}</p>
                      )}
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <Card>
                  <CardContent className="py-8 text-center">
                    <p className="text-muted-foreground">No diff data available</p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Assets Tab */}
            <TabsContent value="assets" className="mt-4">
              {assetsData ? (
                <AssetPreview
                  characters={assetsData.assets.characters}
                  environments={assetsData.assets.environments}
                  isGenerating={isGeneratingAssets}
                  onRegenerate={handleGenerateAssets}
                />
              ) : (
                <Card>
                  <CardContent className="py-8 text-center space-y-4">
                    <ImageIcon className="w-12 h-12 mx-auto text-muted-foreground" />
                    <p className="text-muted-foreground">No assets generated yet</p>
                    <Button
                      onClick={handleGenerateAssets}
                      disabled={isGeneratingAssets || !diffData}
                    >
                      {isGeneratingAssets ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <ImageIcon className="w-4 h-4 mr-2" />
                          Generate Assets
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Prompts Tab */}
            <TabsContent value="prompts" className="mt-4">
              {promptsData ? (
                <div className="space-y-4">
                  <PromptReview promptsData={promptsData} />

                  <Card>
                    <CardContent className="py-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">Ready for Video Generation</p>
                          <p className="text-sm text-muted-foreground">
                            Review prompts above, then proceed to generate video
                          </p>
                        </div>
                        <Button size="lg" disabled>
                          <Play className="w-4 h-4 mr-2" />
                          Generate Video (Coming Soon)
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <Card>
                  <CardContent className="py-8 text-center">
                    <p className="text-muted-foreground">No prompts data available</p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
