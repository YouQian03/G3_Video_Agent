"use client"

import { useState, Fragment } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Users, MapPin, ChevronDown, ChevronUp } from "lucide-react"
import type { CharacterEntity, EnvironmentEntity } from "@/lib/api"

interface CharacterInventoryTableProps {
  jobId: string
  characters: CharacterEntity[]
  environments: EnvironmentEntity[]
  onUpdate?: () => void
}

export function CharacterInventoryTable({
  jobId,
  characters,
  environments,
  onUpdate,
}: CharacterInventoryTableProps) {
  // Debug logging
  console.log("🎭 CharacterInventoryTable props:", {
    jobId,
    charactersCount: characters?.length || 0,
    environmentsCount: environments?.length || 0,
  })
  if (environments?.length > 0) {
    console.log("🌍 Environment details:", environments.map(e => ({ id: e.entityId, name: e.displayName })))
  }

  const [expandedCharacter, setExpandedCharacter] = useState<string | null>(null)
  const [expandedEnvironment, setExpandedEnvironment] = useState<string | null>(null)

  const getImportanceBadge = (importance: string) => {
    switch (importance) {
      case "PRIMARY":
        return <Badge className="bg-accent text-accent-foreground">Primary</Badge>
      case "SECONDARY":
        return <Badge variant="secondary">Secondary</Badge>
      default:
        return <Badge variant="outline">Background</Badge>
    }
  }

  const toggleCharacterExpand = (entityId: string) => {
    setExpandedCharacter(expandedCharacter === entityId ? null : entityId)
  }

  const toggleEnvironmentExpand = (entityId: string) => {
    setExpandedEnvironment(expandedEnvironment === entityId ? null : entityId)
  }

  return (
    <div className="space-y-6">
      {/* Characters Table */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-foreground flex items-center gap-2">
            <Users className="w-5 h-5" />
            Character Inventory
            <Badge variant="secondary" className="ml-2">
              {characters.length} detected
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {characters.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No characters detected in this video.
            </p>
          ) : (
            <div className="rounded-md border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-secondary/50">
                    <TableHead className="w-[120px]">Entity ID</TableHead>
                    <TableHead>Display Name</TableHead>
                    <TableHead className="w-[100px]">Importance</TableHead>
                    <TableHead className="w-[100px] text-right">Shots</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {characters.map((char) => (
                    <Fragment key={char.entityId}>
                      <TableRow
                        className="cursor-pointer hover:bg-secondary/30"
                        onClick={() => toggleCharacterExpand(char.entityId)}
                      >
                        <TableCell className="font-mono text-xs text-accent">
                          {char.entityId}
                        </TableCell>
                        <TableCell className="font-medium">{char.displayName}</TableCell>
                        <TableCell>{getImportanceBadge(char.importance)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger>
                                  <Badge variant="outline">{char.shotCount}</Badge>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p className="text-xs">
                                    Appears in: {char.appearsInShots.join(", ")}
                                  </p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                            {expandedCharacter === char.entityId ? (
                              <ChevronUp className="w-4 h-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-muted-foreground" />
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                      {expandedCharacter === char.entityId && (
                        <TableRow className="bg-secondary/20">
                          <TableCell colSpan={4} className="py-4">
                            <div className="space-y-3 px-4">
                              <div>
                                <p className="text-xs text-muted-foreground mb-1">Visual Signature</p>
                                <p className="text-sm">{char.visualSignature}</p>
                              </div>
                              <div>
                                <p className="text-xs text-muted-foreground mb-1">Detailed Description</p>
                                <p className="text-sm text-muted-foreground">{char.detailedDescription}</p>
                              </div>
                              {char.visualCues && char.visualCues.length > 0 && (
                                <div>
                                  <p className="text-xs text-muted-foreground mb-1">Visual Cues</p>
                                  <div className="flex flex-wrap gap-1">
                                    {char.visualCues.map((cue, idx) => (
                                      <Badge key={idx} variant="outline" className="text-xs">
                                        {cue}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Environments Table */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-foreground flex items-center gap-2">
            <MapPin className="w-5 h-5" />
            Environment Inventory
            <Badge variant="secondary" className="ml-2">
              {environments.length} detected
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {environments.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No environments detected in this video.
            </p>
          ) : (
            <div className="rounded-md border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-secondary/50">
                    <TableHead className="w-[120px]">Entity ID</TableHead>
                    <TableHead>Display Name</TableHead>
                    <TableHead className="w-[100px]">Importance</TableHead>
                    <TableHead className="w-[100px] text-right">Shots</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {environments.map((env) => (
                    <Fragment key={env.entityId}>
                      <TableRow
                        className="cursor-pointer hover:bg-secondary/30"
                        onClick={() => toggleEnvironmentExpand(env.entityId)}
                      >
                        <TableCell className="font-mono text-xs text-blue-400">
                          {env.entityId}
                        </TableCell>
                        <TableCell className="font-medium">{env.displayName}</TableCell>
                        <TableCell>{getImportanceBadge(env.importance)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger>
                                  <Badge variant="outline">{env.shotCount}</Badge>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p className="text-xs">
                                    Appears in: {env.appearsInShots.join(", ")}
                                  </p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                            {expandedEnvironment === env.entityId ? (
                              <ChevronUp className="w-4 h-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-muted-foreground" />
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                      {expandedEnvironment === env.entityId && (
                        <TableRow className="bg-secondary/20">
                          <TableCell colSpan={4} className="py-4">
                            <div className="space-y-3 px-4">
                              <div>
                                <p className="text-xs text-muted-foreground mb-1">Visual Signature</p>
                                <p className="text-sm">{env.visualSignature}</p>
                              </div>
                              <div>
                                <p className="text-xs text-muted-foreground mb-1">Detailed Description</p>
                                <p className="text-sm text-muted-foreground">{env.detailedDescription}</p>
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
