"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp, RefreshCw, Sparkles } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { VideoAnalysis } from "@/lib/api"

interface AnalysisCardProps {
  analysis: VideoAnalysis
  videoTitle: string
  onRegenerate: () => void
  isRegenerating: boolean
}

export function AnalysisCard({ analysis, videoTitle, onRegenerate, isRegenerating }: AnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Sparkles className="h-4 w-4 text-yellow-500 shrink-0" />
            <CardTitle className="text-base truncate">{videoTitle}</CardTitle>
            {analysis.cached && (
              <span className="text-xs text-muted-foreground shrink-0">
                ({formatDate(analysis.created_at)})
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              size="sm"
              variant="ghost"
              onClick={onRegenerate}
              disabled={isRegenerating}
              className="h-7 px-2"
              title="Regenerate analysis"
            >
              <RefreshCw className={`h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`} />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-7 px-2"
            >
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="space-y-4 pt-0">
          <div>
            <h4 className="font-medium text-sm mb-1">Summary</h4>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {analysis.summary}
            </p>
          </div>

          {analysis.key_takeaways.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-1">Key Takeaways</h4>
              <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                {analysis.key_takeaways.map((takeaway, i) => (
                  <li key={i}>{takeaway}</li>
                ))}
              </ul>
            </div>
          )}

          {analysis.main_topics.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-1">Main Topics</h4>
              <div className="flex flex-wrap gap-1">
                {analysis.main_topics.map((topic, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 bg-muted rounded-full text-xs"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}

          {analysis.notable_quotes.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-1">Notable Quotes</h4>
              <div className="space-y-1">
                {analysis.notable_quotes.map((quote, i) => (
                  <blockquote
                    key={i}
                    className="border-l-2 border-muted pl-2 text-sm text-muted-foreground italic"
                  >
                    &ldquo;{quote}&rdquo;
                  </blockquote>
                ))}
              </div>
            </div>
          )}

          <div className="text-xs text-muted-foreground pt-2 border-t">
            Generated with {analysis.model_used}
          </div>
        </CardContent>
      )}
    </Card>
  )
}
