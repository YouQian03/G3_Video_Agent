"use client"

import { useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FolderOpen } from "lucide-react"
import { SaveToLibraryDialog } from "@/components/save-to-library-dialog"
import { saveShotToLibrary } from "@/lib/asset-storage"
import type { StoryboardShot } from "@/lib/types/remix"

interface StoryboardTableProps {
  data: StoryboardShot[]
  title?: string
  showSaveButtons?: boolean
}

export function StoryboardTable({ data, title = "Storyboard Breakdown", showSaveButtons = true }: StoryboardTableProps) {
  // Debug: Log each shot's image URL
  console.log("🎬 StoryboardTable data:", data?.map(s => ({
    shotNumber: s.shotNumber,
    image: s.firstFrameImage,
    startSec: s.startSeconds
  })))

  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [selectedShot, setSelectedShot] = useState<StoryboardShot | null>(null)

  const handleSaveShot = (shot: StoryboardShot) => {
    setSelectedShot(shot)
    setSaveDialogOpen(true)
  }

  const handleSaveToLibrary = (name: string, tags: string[]) => {
    if (!selectedShot) return
    saveShotToLibrary(name, tags, selectedShot)
  }

  // Handle undefined or empty data
  if (!data || data.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-foreground">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-8">No storyboard data available</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-foreground">{title}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-border">
                <TableHead className="text-muted-foreground whitespace-nowrap">Shot Number</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">First Frame Image</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap min-w-[200px]">Visual Description</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap min-w-[200px]">Content Description</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Start Seconds</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">End Second</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Duration Seconds</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Shot Size</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Camera Angle</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Camera Movement</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Focal Length & Depth of Field</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Lighting</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap">Music</TableHead>
                <TableHead className="text-muted-foreground whitespace-nowrap min-w-[150px]">Dialogue & Voice-over</TableHead>
                {showSaveButtons && (
                  <TableHead className="text-muted-foreground whitespace-nowrap">Actions</TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((shot) => (
                <TableRow key={shot.shotNumber} className="border-border">
                  <TableCell className="text-foreground font-medium">{shot.shotNumber}</TableCell>
                  <TableCell>
                    <div className="w-24 h-16 bg-secondary rounded flex items-center justify-center text-xs text-muted-foreground">
                      {shot.firstFrameImage ? (
                        <img
                          src={shot.firstFrameImage || "/placeholder.svg"}
                          alt={`Shot ${shot.shotNumber}`}
                          className="w-full h-full object-cover rounded"
                        />
                      ) : (
                        "Placeholder"
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-foreground text-sm">{shot.visualDescription || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.contentDescription || "-"}</TableCell>
                  <TableCell className="text-foreground">{shot.startSeconds}s</TableCell>
                  <TableCell className="text-foreground">{shot.endSeconds}s</TableCell>
                  <TableCell className="text-foreground">{shot.durationSeconds}s</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.shotSize || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.cameraAngle || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.cameraMovement || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.focalLengthDepth || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.lighting || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.music || "-"}</TableCell>
                  <TableCell className="text-foreground text-sm">{shot.dialogueVoiceover || "-"}</TableCell>
                  {showSaveButtons && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSaveShot(shot)}
                        className="gap-1 text-accent hover:text-accent hover:bg-accent/10"
                      >
                        <FolderOpen className="w-4 h-4" />
                        Save
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {selectedShot && (
        <SaveToLibraryDialog
          open={saveDialogOpen}
          onOpenChange={setSaveDialogOpen}
          assetType="storyboard"
          defaultName={`Shot ${selectedShot.shotNumber} - ${selectedShot.visualDescription?.slice(0, 30) || "Untitled"}...`}
          onSave={handleSaveToLibrary}
        />
      )}
    </>
  )
}
