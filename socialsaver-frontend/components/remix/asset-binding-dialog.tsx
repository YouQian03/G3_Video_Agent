"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Loader2, Upload, User, MapPin } from "lucide-react"

interface AssetBindingDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  entityId: string
  entityType: "CHARACTER" | "ENVIRONMENT"
  displayName: string
  visualSignature: string
  onConfirm: (assetId: string, assetName: string, imageUrl?: string) => Promise<void>
}

export function AssetBindingDialog({
  open,
  onOpenChange,
  entityId,
  entityType,
  displayName,
  visualSignature,
  onConfirm,
}: AssetBindingDialogProps) {
  const [assetName, setAssetName] = useState("")
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setImageFile(file)
      const reader = new FileReader()
      reader.onloadend = () => {
        setImagePreview(reader.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleSubmit = async () => {
    if (!assetName.trim()) {
      setError("Please enter an asset name")
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      // Generate a unique asset ID
      const assetId = `asset_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

      // For now, use the preview URL as the image URL
      // In a real implementation, you'd upload the image to the server first
      await onConfirm(assetId, assetName.trim(), imagePreview || undefined)

      // Reset form and close dialog
      setAssetName("")
      setImageFile(null)
      setImagePreview(null)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to bind asset")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!isSubmitting) {
      setAssetName("")
      setImageFile(null)
      setImagePreview(null)
      setError(null)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {entityType === "CHARACTER" ? (
              <User className="w-5 h-5 text-accent" />
            ) : (
              <MapPin className="w-5 h-5 text-blue-400" />
            )}
            Bind Asset to {entityType === "CHARACTER" ? "Character" : "Environment"}
          </DialogTitle>
          <DialogDescription>
            Create or select an asset to replace this original entity in the remix.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Entity Info */}
          <div className="p-3 bg-secondary/50 rounded-lg space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-xs">
                {entityId}
              </Badge>
              <span className="font-medium">{displayName}</span>
            </div>
            <p className="text-sm text-muted-foreground">{visualSignature}</p>
          </div>

          {/* Asset Name */}
          <div className="space-y-2">
            <Label htmlFor="assetName">Replacement Asset Name</Label>
            <Input
              id="assetName"
              placeholder={entityType === "CHARACTER" ? "e.g., Iron Man, Pikachu" : "e.g., Cyberpunk City, Forest"}
              value={assetName}
              onChange={(e) => setAssetName(e.target.value)}
              className="bg-secondary border-border"
            />
            <p className="text-xs text-muted-foreground">
              This name will be used in all shots where this entity appears.
            </p>
          </div>

          {/* Reference Image Upload */}
          <div className="space-y-2">
            <Label>Reference Image (Optional)</Label>
            <div className="flex items-start gap-4">
              {imagePreview ? (
                <div className="relative w-24 h-24 rounded-lg overflow-hidden border border-border">
                  <img
                    src={imagePreview}
                    alt="Preview"
                    className="w-full h-full object-cover"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setImageFile(null)
                      setImagePreview(null)
                    }}
                    className="absolute top-1 right-1 w-5 h-5 bg-black/50 rounded-full flex items-center justify-center text-white text-xs hover:bg-black/70"
                  >
                    ×
                  </button>
                </div>
              ) : (
                <label className="w-24 h-24 rounded-lg border-2 border-dashed border-border flex flex-col items-center justify-center cursor-pointer hover:border-accent/50 hover:bg-secondary/50 transition-colors">
                  <Upload className="w-6 h-6 text-muted-foreground mb-1" />
                  <span className="text-xs text-muted-foreground">Upload</span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageChange}
                    className="hidden"
                  />
                </label>
              )}
              <div className="flex-1 text-xs text-muted-foreground">
                <p>Upload a reference image for the replacement asset.</p>
                <p className="mt-1">This will help generate consistent visuals across all shots.</p>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-500">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isSubmitting}
            className="border-border"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || !assetName.trim()}
            className="bg-accent text-accent-foreground hover:bg-accent/90"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Binding...
              </>
            ) : (
              "Bind Asset"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
