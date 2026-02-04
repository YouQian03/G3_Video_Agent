"use client";

import { useState } from "react";
import Image from "next/image";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, User, MapPin, RefreshCw, CheckCircle, XCircle, ImageIcon } from "lucide-react";
import type { CharacterAsset, EnvironmentAsset } from "@/lib/api";

interface AssetPreviewProps {
  characters: CharacterAsset[];
  environments: EnvironmentAsset[];
  isGenerating?: boolean;
  onRegenerate?: () => void;
}

export function AssetPreview({
  characters,
  environments,
  isGenerating = false,
  onRegenerate,
}: AssetPreviewProps) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return <Badge className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" />完成</Badge>;
      case "GENERATING":
        return <Badge className="bg-blue-500"><Loader2 className="w-3 h-3 mr-1 animate-spin" />生成中</Badge>;
      case "FAILED":
        return <Badge className="bg-red-500"><XCircle className="w-3 h-3 mr-1" />失败</Badge>;
      case "PARTIAL":
        return <Badge className="bg-yellow-500">部分完成</Badge>;
      default:
        return <Badge variant="secondary">未开始</Badge>;
    }
  };

  const ImagePlaceholder = () => (
    <div className="w-full h-full bg-muted flex items-center justify-center rounded-lg">
      <ImageIcon className="w-8 h-8 text-muted-foreground" />
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">生成的资产</h3>
          <p className="text-sm text-muted-foreground">
            角色三视图和环境参考图
          </p>
        </div>
        {onRegenerate && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRegenerate}
            disabled={isGenerating}
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            重新生成
          </Button>
        )}
      </div>

      {/* Characters Section */}
      {characters.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <User className="w-4 h-4" />
              角色 ({characters.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {characters.map((char) => (
              <div key={char.anchorId} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="font-medium">{char.name || char.anchorId}</h4>
                    <p className="text-xs text-muted-foreground">{char.anchorId}</p>
                  </div>
                  {getStatusBadge(char.status)}
                </div>

                {/* Three Views Grid */}
                <div className="grid grid-cols-3 gap-3">
                  {/* Front View */}
                  <div className="space-y-1">
                    <p className="text-xs text-center text-muted-foreground">正面</p>
                    <div className="aspect-video relative overflow-hidden rounded-lg border bg-muted">
                      {char.threeViews.front ? (
                        <Image
                          src={char.threeViews.front}
                          alt={`${char.name} - Front`}
                          fill
                          className="object-cover cursor-pointer hover:scale-105 transition-transform"
                          onClick={() => setSelectedImage(char.threeViews.front)}
                        />
                      ) : (
                        <ImagePlaceholder />
                      )}
                    </div>
                  </div>

                  {/* Side View */}
                  <div className="space-y-1">
                    <p className="text-xs text-center text-muted-foreground">侧面</p>
                    <div className="aspect-video relative overflow-hidden rounded-lg border bg-muted">
                      {char.threeViews.side ? (
                        <Image
                          src={char.threeViews.side}
                          alt={`${char.name} - Side`}
                          fill
                          className="object-cover cursor-pointer hover:scale-105 transition-transform"
                          onClick={() => setSelectedImage(char.threeViews.side)}
                        />
                      ) : (
                        <ImagePlaceholder />
                      )}
                    </div>
                  </div>

                  {/* Back View */}
                  <div className="space-y-1">
                    <p className="text-xs text-center text-muted-foreground">背面</p>
                    <div className="aspect-video relative overflow-hidden rounded-lg border bg-muted">
                      {char.threeViews.back ? (
                        <Image
                          src={char.threeViews.back}
                          alt={`${char.name} - Back`}
                          fill
                          className="object-cover cursor-pointer hover:scale-105 transition-transform"
                          onClick={() => setSelectedImage(char.threeViews.back)}
                        />
                      ) : (
                        <ImagePlaceholder />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Environments Section */}
      {environments.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <MapPin className="w-4 h-4" />
              环境 ({environments.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {environments.map((env) => (
              <div key={env.anchorId} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="font-medium">{env.name || env.anchorId}</h4>
                    <p className="text-xs text-muted-foreground">{env.anchorId}</p>
                  </div>
                  {getStatusBadge(env.status)}
                </div>

                {/* Environment Reference Image */}
                <div className="aspect-video relative overflow-hidden rounded-lg border bg-muted max-w-md">
                  {env.referenceImage ? (
                    <Image
                      src={env.referenceImage}
                      alt={`${env.name} - Reference`}
                      fill
                      className="object-cover cursor-pointer hover:scale-105 transition-transform"
                      onClick={() => setSelectedImage(env.referenceImage)}
                    />
                  ) : (
                    <ImagePlaceholder />
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {characters.length === 0 && environments.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center">
            <ImageIcon className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">暂无生成的资产</p>
            <p className="text-sm text-muted-foreground mt-1">
              请先运行 Intent Injection 生成 Identity Anchors
            </p>
          </CardContent>
        </Card>
      )}

      {/* Lightbox Modal */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] w-full">
            <Image
              src={selectedImage}
              alt="Preview"
              width={1280}
              height={720}
              className="object-contain w-full h-full rounded-lg"
            />
            <Button
              variant="secondary"
              size="sm"
              className="absolute top-2 right-2"
              onClick={() => setSelectedImage(null)}
            >
              关闭
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
