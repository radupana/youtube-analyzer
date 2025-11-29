"use client"

import { useState, useEffect } from "react"
import { RefreshCw, Check } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  fetchPatterns,
  fetchVideoPatternResults,
  applyPattern,
  Pattern,
  PatternResult,
  CachedPatternResult,
} from "@/lib/api"

interface PatternSelectorProps {
  videoId: string
  onPatternApplied: (result: PatternResult) => void
  onClose: () => void
}

export function PatternSelector({ videoId, onPatternApplied, onClose }: PatternSelectorProps) {
  const [patterns, setPatterns] = useState<Pattern[]>([])
  const [cachedResults, setCachedResults] = useState<Record<string, CachedPatternResult>>({})
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [patternsData, cachedData] = await Promise.all([
          fetchPatterns(),
          fetchVideoPatternResults(videoId),
        ])
        setPatterns(patternsData)
        const cachedMap: Record<string, CachedPatternResult> = {}
        for (const result of cachedData) {
          cachedMap[result.pattern_id] = result
        }
        setCachedResults(cachedMap)
      } catch (err) {
        console.error("Failed to load patterns:", err)
      }
    }
    loadData()
  }, [videoId])

  const handleApplyPattern = async (patternId: string, refresh: boolean = false) => {
    setLoading(patternId)
    setError(null)
    try {
      const result = await applyPattern(videoId, patternId, refresh)
      onPatternApplied(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply pattern")
    }
    setLoading(null)
  }

  if (patterns.length === 0) return null

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  return (
    <Card>
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <CardTitle className="text-lg">Analysis Patterns</CardTitle>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
          <span className="text-lg">&times;</span>
        </Button>
      </CardHeader>
      <CardContent>
        {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
        <div className="grid grid-cols-2 gap-2">
          {patterns.map(pattern => {
            const cached = cachedResults[pattern.id]
            return (
              <div key={pattern.id} className="relative">
                <Button
                  variant="outline"
                  className={`h-auto w-full p-3 flex flex-col items-start text-left ${
                    cached ? "border-green-500/50 bg-green-50/50 dark:bg-green-950/20" : ""
                  }`}
                  onClick={() => handleApplyPattern(pattern.id, false)}
                  disabled={loading !== null}
                >
                  <div className="flex items-center gap-2 w-full">
                    {loading === pattern.id ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <span className="text-lg">{pattern.icon}</span>
                    )}
                    {cached && <Check className="h-3 w-3 text-green-600 ml-auto" />}
                  </div>
                  <span className="font-medium text-sm">{pattern.name}</span>
                  <span className="text-xs text-muted-foreground line-clamp-2">
                    {pattern.description}
                  </span>
                  {cached && (
                    <span className="text-xs text-green-600 mt-1">
                      Cached {formatDate(cached.created_at)}
                    </span>
                  )}
                </Button>
                {cached && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-1 right-1 h-6 w-6 p-0"
                    onClick={e => {
                      e.stopPropagation()
                      handleApplyPattern(pattern.id, true)
                    }}
                    disabled={loading !== null}
                    title="Refresh"
                  >
                    <RefreshCw className={`h-3 w-3 ${loading === pattern.id ? "animate-spin" : ""}`} />
                  </Button>
                )}
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
