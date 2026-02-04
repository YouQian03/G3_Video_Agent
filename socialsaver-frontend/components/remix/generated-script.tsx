"use client"

import React from "react"

import { useState, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Check, Edit3, Sparkles, FileText, RefreshCw, ImagePlus, X } from "lucide-react"
import type { GeneratedScript } from "@/lib/types/remix"

interface ReferenceImage {
  file: File
  preview: string
}

interface GeneratedScriptProps {
  data: GeneratedScript
  userRequirements: string
  initialReferenceImages?: File[]
  onConfirm: () => void
  onRegenerate?: (newRequirements: string, referenceImages: File[]) => void
}

export function GeneratedScriptCard({
  data,
  userRequirements,
  initialReferenceImages = [],
  onConfirm,
  onRegenerate
}: GeneratedScriptProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [isConfirmed, setIsConfirmed] = useState(false)
  const [scriptContent, setScriptContent] = useState(data.content)
  const [editedRequirements, setEditedRequirements] = useState(userRequirements)
  const [showRequirementsEdit, setShowRequirementsEdit] = useState(false)
  const [referenceImages, setReferenceImages] = useState<ReferenceImage[]>(
    initialReferenceImages.map((file) => ({ file, preview: URL.createObjectURL(file) }))
  )
  const refImageInputRef = useRef<HTMLInputElement>(null)

  const handleModify = () => {
    setIsEditing(true)
  }

  const handleConfirmScript = () => {
    setIsEditing(false)
    setIsConfirmed(true)
    // Notify parent that script is confirmed
    onConfirm()
  }

  const handleAddReferenceImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files
    if (selectedFiles) {
      const newImages = Array.from(selectedFiles).map((file) => ({
        file,
        preview: URL.createObjectURL(file),
      }))
      setReferenceImages((prev) => [...prev, ...newImages])
    }
    if (refImageInputRef.current) {
      refImageInputRef.current.value = ""
    }
  }

  const removeReferenceImage = (index: number) => {
    setReferenceImages((prev) => {
      const removed = prev[index]
      URL.revokeObjectURL(removed.preview)
      return prev.filter((_, i) => i !== index)
    })
  }

  const handleRegenerate = () => {
    if (onRegenerate) {
      onRegenerate(editedRequirements, referenceImages.map((r) => r.file))
    }
  }

  return (
    <div className="space-y-6">
      {/* User Requirements Summary Card */}
      <Card className="bg-secondary/50 border-border">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-accent" />
              <CardTitle className="text-base text-foreground">Your Remix Requirements</CardTitle>
            </div>
            {!isConfirmed && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRequirementsEdit(!showRequirementsEdit)}
                className="text-muted-foreground hover:text-foreground"
              >
                <Edit3 className="w-4 h-4 mr-1" />
                Edit
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {showRequirementsEdit && !isConfirmed ? (
            <div className="space-y-3">
              <Textarea
                value={editedRequirements}
                onChange={(e) => setEditedRequirements(e.target.value)}
                rows={4}
                className="resize-none bg-secondary border-border"
              />

              {/* Reference Images for regeneration */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm text-muted-foreground">Reference Images</label>
                  <input
                    ref={refImageInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={handleAddReferenceImage}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => refImageInputRef.current?.click()}
                    className="border-border text-muted-foreground hover:text-foreground hover:bg-secondary bg-transparent"
                  >
                    <ImagePlus className="w-4 h-4 mr-1" />
                    Add
                  </Button>
                </div>
                {referenceImages.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {referenceImages.map((img, index) => (
                      <div
                        key={index}
                        className="relative group w-16 h-16 rounded-lg overflow-hidden border border-border"
                      >
                        <img
                          src={img.preview || "/placeholder.svg"}
                          alt={`Reference ${index + 1}`}
                          className="w-full h-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => removeReferenceImage(index)}
                          className="absolute inset-0 bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                        >
                          <X className="w-4 h-4 text-foreground" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Button
                onClick={handleRegenerate}
                variant="outline"
                className="w-full border-accent text-accent hover:bg-accent/10 bg-transparent"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Regenerate Script with New Requirements
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-muted-foreground text-sm leading-relaxed">
                {userRequirements}
              </p>
              {referenceImages.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {referenceImages.map((img, index) => (
                    <div
                      key={index}
                      className="w-12 h-12 rounded overflow-hidden border border-border"
                    >
                      <img
                        src={img.preview || "/placeholder.svg"}
                        alt={`Reference ${index + 1}`}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Generated Script Card */}
      <Card className={`bg-card border-2 ${isConfirmed ? 'border-accent' : 'border-accent/30'}`}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-accent" />
              <CardTitle className="text-foreground">Generated Remix Script</CardTitle>
            </div>
            <Badge
              variant="outline"
              className={isConfirmed ? "border-accent bg-accent text-accent-foreground" : "border-accent text-accent"}
            >
              {isConfirmed ? "Confirmed" : "Awaiting Confirmation"}
            </Badge>
          </div>
          <CardDescription className="text-muted-foreground">
            {isConfirmed
              ? "Script confirmed. Proceed to Character & Scene Views to prepare assets."
              : isEditing
              ? "Edit the script below, then confirm when ready."
              : "Review the script below. Click Modify to make changes, or Confirm to proceed."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isEditing ? (
            <Textarea
              value={scriptContent}
              onChange={(e) => setScriptContent(e.target.value)}
              rows={16}
              className="resize-none bg-secondary border-border font-mono text-sm leading-relaxed"
            />
          ) : (
            <div className={`bg-secondary rounded-lg p-4 max-h-96 overflow-y-auto ${isConfirmed ? 'opacity-80' : ''}`}>
              <pre className="whitespace-pre-wrap text-sm text-foreground font-mono leading-relaxed">
                {scriptContent}
              </pre>
            </div>
          )}
        </CardContent>
        {!isConfirmed && (
          <CardFooter className="flex flex-col sm:flex-row gap-3 pt-4">
            <Button
              onClick={handleConfirmScript}
              className="flex-1 bg-accent text-accent-foreground hover:bg-accent/90"
              size="lg"
            >
              <Check className="w-4 h-4 mr-2" />
              Confirm Script
            </Button>
            <Button
              onClick={handleModify}
              variant="outline"
              className="flex-1 border-border text-foreground hover:bg-secondary bg-transparent"
              size="lg"
            >
              <Edit3 className="w-4 h-4 mr-2" />
              Modify
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  )
}
