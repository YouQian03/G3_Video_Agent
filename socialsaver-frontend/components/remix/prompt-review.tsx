"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Image as ImageIcon,
  Video,
  Camera,
  Edit2,
  Check,
  X,
  User,
  MapPin,
  Copy,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { RemixPromptsResponse, T2IPrompt, I2VPrompt, IdentityAnchor } from "@/lib/api";

interface PromptReviewProps {
  promptsData: RemixPromptsResponse;
  onPromptEdit?: (shotId: string, type: "t2i" | "i2v", newPrompt: string) => void;
}

export function PromptReview({ promptsData, onPromptEdit }: PromptReviewProps) {
  const [activeTab, setActiveTab] = useState<"t2i" | "i2v" | "anchors">("t2i");
  const [editingPrompt, setEditingPrompt] = useState<{
    shotId: string;
    type: "t2i" | "i2v";
  } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [expandedShots, setExpandedShots] = useState<Set<string>>(new Set());

  const toggleShot = (shotId: string) => {
    const newExpanded = new Set(expandedShots);
    if (newExpanded.has(shotId)) {
      newExpanded.delete(shotId);
    } else {
      newExpanded.add(shotId);
    }
    setExpandedShots(newExpanded);
  };

  const startEditing = (shotId: string, type: "t2i" | "i2v", currentPrompt: string) => {
    setEditingPrompt({ shotId, type });
    setEditValue(currentPrompt);
  };

  const cancelEditing = () => {
    setEditingPrompt(null);
    setEditValue("");
  };

  const saveEditing = () => {
    if (editingPrompt && onPromptEdit) {
      onPromptEdit(editingPrompt.shotId, editingPrompt.type, editValue);
    }
    cancelEditing();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="t2i" className="flex items-center gap-2">
            <ImageIcon className="w-4 h-4" />
            T2I Prompts ({promptsData.t2iPrompts.length})
          </TabsTrigger>
          <TabsTrigger value="i2v" className="flex items-center gap-2">
            <Video className="w-4 h-4" />
            I2V Prompts ({promptsData.i2vPrompts.length})
          </TabsTrigger>
          <TabsTrigger value="anchors" className="flex items-center gap-2">
            <User className="w-4 h-4" />
            Identity Anchors
          </TabsTrigger>
        </TabsList>

        {/* T2I Prompts Tab */}
        <TabsContent value="t2i" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ImageIcon className="w-4 h-4" />
                Text-to-Image Prompts (Imagen 4.0)
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                用于生成每个分镜的首帧静态图片
              </p>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px] pr-4">
                <div className="space-y-3">
                  {promptsData.t2iPrompts.map((prompt) => (
                    <T2IPromptCard
                      key={prompt.shotId}
                      prompt={prompt}
                      isExpanded={expandedShots.has(`t2i-${prompt.shotId}`)}
                      onToggle={() => toggleShot(`t2i-${prompt.shotId}`)}
                      isEditing={
                        editingPrompt?.shotId === prompt.shotId &&
                        editingPrompt?.type === "t2i"
                      }
                      editValue={editValue}
                      onEditValueChange={setEditValue}
                      onStartEdit={() => startEditing(prompt.shotId, "t2i", prompt.prompt)}
                      onSaveEdit={saveEditing}
                      onCancelEdit={cancelEditing}
                      onCopy={() => copyToClipboard(prompt.prompt)}
                      canEdit={!!onPromptEdit}
                    />
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* I2V Prompts Tab */}
        <TabsContent value="i2v" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Video className="w-4 h-4" />
                Image-to-Video Prompts (Veo 3.1)
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                用于将首帧动画化生成视频片段
              </p>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px] pr-4">
                <div className="space-y-3">
                  {promptsData.i2vPrompts.map((prompt) => (
                    <I2VPromptCard
                      key={prompt.shotId}
                      prompt={prompt}
                      isExpanded={expandedShots.has(`i2v-${prompt.shotId}`)}
                      onToggle={() => toggleShot(`i2v-${prompt.shotId}`)}
                      isEditing={
                        editingPrompt?.shotId === prompt.shotId &&
                        editingPrompt?.type === "i2v"
                      }
                      editValue={editValue}
                      onEditValueChange={setEditValue}
                      onStartEdit={() => startEditing(prompt.shotId, "i2v", prompt.prompt)}
                      onSaveEdit={saveEditing}
                      onCancelEdit={cancelEditing}
                      onCopy={() => copyToClipboard(prompt.prompt)}
                      canEdit={!!onPromptEdit}
                    />
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Identity Anchors Tab */}
        <TabsContent value="anchors" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Characters */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <User className="w-4 h-4" />
                  角色 ({promptsData.identityAnchors.characters.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-3">
                    {promptsData.identityAnchors.characters.map((anchor) => (
                      <AnchorCard key={anchor.anchorId} anchor={anchor} type="character" />
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Environments */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <MapPin className="w-4 h-4" />
                  环境 ({promptsData.identityAnchors.environments.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-3">
                    {promptsData.identityAnchors.environments.map((anchor) => (
                      <AnchorCard key={anchor.anchorId} anchor={anchor} type="environment" />
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// T2I Prompt Card Component
interface T2IPromptCardProps {
  prompt: T2IPrompt;
  isExpanded: boolean;
  onToggle: () => void;
  isEditing: boolean;
  editValue: string;
  onEditValueChange: (value: string) => void;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onCopy: () => void;
  canEdit: boolean;
}

function T2IPromptCard({
  prompt,
  isExpanded,
  onToggle,
  isEditing,
  editValue,
  onEditValueChange,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onCopy,
  canEdit,
}: T2IPromptCardProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors text-left"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            {prompt.shotId}
          </Badge>
          <span className="text-sm text-muted-foreground truncate max-w-md">
            {prompt.prompt.slice(0, 60)}...
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 border-t">
          {/* Camera Info */}
          <div className="pt-3 flex flex-wrap gap-2">
            <Badge variant="secondary" className="text-xs">
              <Camera className="w-3 h-3 mr-1" />
              {prompt.cameraPreserved.shotSize}
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {prompt.cameraPreserved.cameraAngle}
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {prompt.cameraPreserved.cameraMovement}
            </Badge>
          </div>

          {/* Applied Anchors */}
          {(prompt.appliedAnchors.characters.length > 0 ||
            prompt.appliedAnchors.environments.length > 0) && (
            <div className="flex flex-wrap gap-1">
              {prompt.appliedAnchors.characters.map((c) => (
                <Badge key={c} className="text-xs bg-blue-500/10 text-blue-500">
                  <User className="w-3 h-3 mr-1" />
                  {c}
                </Badge>
              ))}
              {prompt.appliedAnchors.environments.map((e) => (
                <Badge key={e} className="text-xs bg-green-500/10 text-green-500">
                  <MapPin className="w-3 h-3 mr-1" />
                  {e}
                </Badge>
              ))}
            </div>
          )}

          {/* Prompt Text */}
          <div className="space-y-2">
            {isEditing ? (
              <>
                <Textarea
                  value={editValue}
                  onChange={(e) => onEditValueChange(e.target.value)}
                  className="min-h-[120px] text-sm font-mono"
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={onSaveEdit}>
                    <Check className="w-3 h-3 mr-1" />
                    保存
                  </Button>
                  <Button size="sm" variant="outline" onClick={onCancelEdit}>
                    <X className="w-3 h-3 mr-1" />
                    取消
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-sm font-mono whitespace-pre-wrap">{prompt.prompt}</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={onCopy}>
                    <Copy className="w-3 h-3 mr-1" />
                    复制
                  </Button>
                  {canEdit && (
                    <Button size="sm" variant="ghost" onClick={onStartEdit}>
                      <Edit2 className="w-3 h-3 mr-1" />
                      编辑
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// I2V Prompt Card Component
interface I2VPromptCardProps {
  prompt: I2VPrompt;
  isExpanded: boolean;
  onToggle: () => void;
  isEditing: boolean;
  editValue: string;
  onEditValueChange: (value: string) => void;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onCopy: () => void;
  canEdit: boolean;
}

function I2VPromptCard({
  prompt,
  isExpanded,
  onToggle,
  isEditing,
  editValue,
  onEditValueChange,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onCopy,
  canEdit,
}: I2VPromptCardProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors text-left"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            {prompt.shotId}
          </Badge>
          <Badge variant="secondary" className="text-xs">
            {prompt.durationSeconds}s
          </Badge>
          <span className="text-sm text-muted-foreground truncate max-w-md">
            {prompt.prompt.slice(0, 50)}...
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 border-t">
          {/* Camera Info */}
          <div className="pt-3 flex flex-wrap gap-2">
            <Badge variant="secondary" className="text-xs">
              <Camera className="w-3 h-3 mr-1" />
              {prompt.cameraPreserved.shotSize}
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {prompt.cameraPreserved.cameraMovement}
            </Badge>
            {prompt.firstFrameInheritance && (
              <Badge className="text-xs bg-purple-500/10 text-purple-500">
                首帧继承
              </Badge>
            )}
          </div>

          {/* Prompt Text */}
          <div className="space-y-2">
            {isEditing ? (
              <>
                <Textarea
                  value={editValue}
                  onChange={(e) => onEditValueChange(e.target.value)}
                  className="min-h-[100px] text-sm font-mono"
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={onSaveEdit}>
                    <Check className="w-3 h-3 mr-1" />
                    保存
                  </Button>
                  <Button size="sm" variant="outline" onClick={onCancelEdit}>
                    <X className="w-3 h-3 mr-1" />
                    取消
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-sm font-mono whitespace-pre-wrap">{prompt.prompt}</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={onCopy}>
                    <Copy className="w-3 h-3 mr-1" />
                    复制
                  </Button>
                  {canEdit && (
                    <Button size="sm" variant="ghost" onClick={onStartEdit}>
                      <Edit2 className="w-3 h-3 mr-1" />
                      编辑
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Anchor Card Component
interface AnchorCardProps {
  anchor: IdentityAnchor;
  type: "character" | "environment";
}

function AnchorCard({ anchor, type }: AnchorCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors text-left"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          {type === "character" ? (
            <User className="w-4 h-4 text-blue-500" />
          ) : (
            <MapPin className="w-4 h-4 text-green-500" />
          )}
          <span className="font-medium">{anchor.anchorName}</span>
          <Badge variant="outline" className="text-xs font-mono">
            {anchor.anchorId}
          </Badge>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-2 border-t pt-3">
          {anchor.originalPlaceholder && (
            <div className="text-xs text-muted-foreground">
              占位符: <code className="bg-muted px-1 rounded">{anchor.originalPlaceholder}</code>
            </div>
          )}
          <div className="p-3 bg-muted rounded-lg">
            <p className="text-sm">{anchor.detailedDescription}</p>
          </div>
          {anchor.styleAdaptation && (
            <div className="text-xs text-muted-foreground">
              风格适配: {anchor.styleAdaptation}
            </div>
          )}
          {anchor.atmosphericConditions && (
            <div className="text-xs text-muted-foreground">
              大气条件: {anchor.atmosphericConditions}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
