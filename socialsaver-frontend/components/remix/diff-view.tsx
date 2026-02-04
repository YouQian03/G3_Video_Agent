"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ArrowRight,
  User,
  MapPin,
  Palette,
  ChevronDown,
  ChevronUp,
  Film,
  Sparkles,
} from "lucide-react";
import type { RemixDiffResponse, RemixDiffEntry } from "@/lib/api";

interface DiffViewProps {
  diffData: RemixDiffResponse;
}

export function DiffView({ diffData }: DiffViewProps) {
  const [expandedShots, setExpandedShots] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<"all" | "changed">("changed");

  const toggleShot = (shotId: string) => {
    const newExpanded = new Set(expandedShots);
    if (newExpanded.has(shotId)) {
      newExpanded.delete(shotId);
    } else {
      newExpanded.add(shotId);
    }
    setExpandedShots(newExpanded);
  };

  const expandAll = () => {
    setExpandedShots(new Set(diffData.diff.map((d) => d.shotId)));
  };

  const collapseAll = () => {
    setExpandedShots(new Set());
  };

  const filteredDiff =
    viewMode === "changed"
      ? diffData.diff.filter((d) => d.changes.length > 0 || d.remixNotes)
      : diffData.diff;

  const getChangeIcon = (type: string) => {
    switch (type) {
      case "SUBJECT_CHANGE":
        return <User className="w-3 h-3" />;
      case "ENVIRONMENT_CHANGE":
        return <MapPin className="w-3 h-3" />;
      case "STYLE_CHANGE":
        return <Palette className="w-3 h-3" />;
      default:
        return <Sparkles className="w-3 h-3" />;
    }
  };

  const getChangeColor = (type: string) => {
    switch (type) {
      case "SUBJECT_CHANGE":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "ENVIRONMENT_CHANGE":
        return "bg-green-500/10 text-green-500 border-green-500/20";
      case "STYLE_CHANGE":
        return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      default:
        return "bg-orange-500/10 text-orange-500 border-orange-500/20";
    }
  };

  const getBeatTagColor = (tag: string) => {
    const colors: Record<string, string> = {
      HOOK: "bg-red-500",
      SETUP: "bg-blue-500",
      TURN: "bg-yellow-500",
      CTA: "bg-green-500",
    };
    return colors[tag] || "bg-gray-500";
  };

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Film className="w-4 h-4" />
            Remix 摘要
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{diffData.summary.totalShots}</div>
              <div className="text-xs text-muted-foreground">总分镜数</div>
            </div>
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold text-blue-500">
                {diffData.summary.shotsModified}
              </div>
              <div className="text-xs text-muted-foreground">已修改</div>
            </div>
            <div className="col-span-2 p-3 bg-muted rounded-lg">
              <div className="text-sm font-medium mb-1">主要变更</div>
              <div className="flex flex-wrap gap-1">
                {diffData.summary.primaryChanges.map((change, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {change.length > 30 ? change.slice(0, 30) + "..." : change}
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          {/* Preserved Elements */}
          {diffData.summary.preservedElements.length > 0 && (
            <div className="mt-3 pt-3 border-t">
              <div className="text-xs text-muted-foreground mb-1">保留元素</div>
              <div className="flex flex-wrap gap-1">
                {diffData.summary.preservedElements.map((elem, i) => (
                  <Badge key={i} variant="outline" className="text-xs">
                    {elem}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Diff List */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">分镜对比</CardTitle>
            <div className="flex items-center gap-2">
              <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "all" | "changed")}>
                <TabsList className="h-8">
                  <TabsTrigger value="changed" className="text-xs px-2 h-6">
                    仅显示变更 ({filteredDiff.length})
                  </TabsTrigger>
                  <TabsTrigger value="all" className="text-xs px-2 h-6">
                    全部 ({diffData.diff.length})
                  </TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" onClick={expandAll} className="h-8 px-2">
                  展开全部
                </Button>
                <Button variant="ghost" size="sm" onClick={collapseAll} className="h-8 px-2">
                  收起全部
                </Button>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[500px] pr-4">
            <div className="space-y-2">
              {filteredDiff.map((entry) => (
                <DiffEntry
                  key={entry.shotId}
                  entry={entry}
                  isExpanded={expandedShots.has(entry.shotId)}
                  onToggle={() => toggleShot(entry.shotId)}
                  getChangeIcon={getChangeIcon}
                  getChangeColor={getChangeColor}
                  getBeatTagColor={getBeatTagColor}
                />
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

interface DiffEntryProps {
  entry: RemixDiffEntry;
  isExpanded: boolean;
  onToggle: () => void;
  getChangeIcon: (type: string) => React.ReactNode;
  getChangeColor: (type: string) => string;
  getBeatTagColor: (tag: string) => string;
}

function DiffEntry({
  entry,
  isExpanded,
  onToggle,
  getChangeIcon,
  getChangeColor,
  getBeatTagColor,
}: DiffEntryProps) {
  const hasChanges = entry.changes.length > 0 || entry.remixNotes;

  return (
    <div
      className={`border rounded-lg overflow-hidden ${
        hasChanges ? "border-blue-500/30 bg-blue-500/5" : ""
      }`}
    >
      {/* Header */}
      <button
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="font-mono text-xs">
            {entry.shotId}
          </Badge>
          <Badge className={`${getBeatTagColor(entry.beatTag)} text-xs`}>
            {entry.beatTag}
          </Badge>
          {entry.changes.length > 0 && (
            <div className="flex gap-1">
              {entry.changes.map((change, i) => (
                <span
                  key={i}
                  className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs border ${getChangeColor(
                    change.type
                  )}`}
                >
                  {getChangeIcon(change.type)}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {hasChanges && (
            <Badge variant="secondary" className="text-xs">
              已修改
            </Badge>
          )}
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 border-t bg-background">
          {/* Changes */}
          {entry.changes.length > 0 && (
            <div className="pt-3">
              <div className="text-xs text-muted-foreground mb-2">变更类型</div>
              <div className="flex flex-wrap gap-2">
                {entry.changes.map((change, i) => (
                  <div
                    key={i}
                    className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs border ${getChangeColor(
                      change.type
                    )}`}
                  >
                    {getChangeIcon(change.type)}
                    <span>{change.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* First Frame Comparison */}
          <div className="pt-3">
            <div className="text-xs text-muted-foreground mb-2">首帧描述对比</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Original */}
              <div className="p-3 bg-muted/50 rounded-lg">
                <div className="text-xs font-medium text-muted-foreground mb-1">
                  原始 (Concrete)
                </div>
                <p className="text-sm">
                  {entry.originalFirstFrame || (
                    <span className="text-muted-foreground italic">无原始描述</span>
                  )}
                </p>
              </div>

              {/* Arrow */}
              <div className="hidden md:flex items-center justify-center absolute left-1/2 -translate-x-1/2">
                <ArrowRight className="w-5 h-5 text-muted-foreground" />
              </div>

              {/* Remixed */}
              <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                <div className="text-xs font-medium text-blue-500 mb-1">
                  Remix 后
                </div>
                <p className="text-sm">{entry.remixedFirstFrame}</p>
              </div>
            </div>
          </div>

          {/* Remix Notes */}
          {entry.remixNotes && (
            <div className="pt-2">
              <div className="text-xs text-muted-foreground mb-1">修改说明</div>
              <p className="text-sm text-muted-foreground italic">
                {entry.remixNotes}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
