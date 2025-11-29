"use client"

import { useState, useMemo, useRef, useCallback, useEffect } from "react"
import { Search, ChevronUp, ChevronDown, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { TranscriptSegment } from "@/lib/api"

interface TranscriptViewerProps {
  segments: TranscriptSegment[]
  hasTimestamps: boolean
}

interface SearchMatch {
  segmentIndex: number
  startInSegment: number
  endInSegment: number
}

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)

  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  }
  return `${m}:${s.toString().padStart(2, "0")}`
}

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

export function TranscriptViewer({ segments, hasTimestamps }: TranscriptViewerProps) {
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0)
  const matchRefs = useRef<Map<number, HTMLElement>>(new Map())

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.slice(0, 200))
      setCurrentMatchIndex(0) // Reset to first match when search changes
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    matchRefs.current.clear()
  }, [segments])

  const matches = useMemo((): SearchMatch[] => {
    if (!debouncedQuery.trim()) return []

    const results: SearchMatch[] = []
    const regex = new RegExp(escapeRegExp(debouncedQuery), "gi")

    segments.forEach((segment, segmentIndex) => {
      let match
      while ((match = regex.exec(segment.text)) !== null) {
        results.push({
          segmentIndex,
          startInSegment: match.index,
          endInSegment: match.index + match[0].length,
        })
      }
    })

    return results
  }, [debouncedQuery, segments])

  useEffect(() => {
    if (matches.length === 0) return

    const matchElement = matchRefs.current.get(currentMatchIndex)
    if (matchElement) {
      matchElement.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }, [currentMatchIndex, matches.length])

  const goToNextMatch = useCallback(() => {
    if (matches.length === 0) return
    setCurrentMatchIndex((prev) => (prev + 1) % matches.length)
  }, [matches.length])

  const goToPrevMatch = useCallback(() => {
    if (matches.length === 0) return
    setCurrentMatchIndex((prev) => (prev - 1 + matches.length) % matches.length)
  }, [matches.length])

  const clearSearch = useCallback(() => {
    setQuery("")
    setDebouncedQuery("")
  }, [])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && matches.length > 0) {
        e.preventDefault()
        if (e.shiftKey) {
          goToPrevMatch()
        } else {
          goToNextMatch()
        }
      }
    },
    [goToNextMatch, goToPrevMatch, matches.length]
  )

  const renderSegmentText = (segment: TranscriptSegment, segmentIndex: number) => {
    if (!debouncedQuery.trim()) {
      return segment.text
    }

    const segmentMatches = matches.filter((m) => m.segmentIndex === segmentIndex)
    if (segmentMatches.length === 0) {
      return segment.text
    }

    const parts: React.ReactNode[] = []
    let lastEnd = 0

    segmentMatches.forEach((match, matchIdx) => {
      const globalMatchIndex = matches.findIndex(
        (m) => m.segmentIndex === segmentIndex && m.startInSegment === match.startInSegment
      )
      const isCurrentMatch = globalMatchIndex === currentMatchIndex

      if (match.startInSegment > lastEnd) {
        parts.push(segment.text.slice(lastEnd, match.startInSegment))
      }

      parts.push(
        <mark
          key={`${segmentIndex}-${matchIdx}`}
          ref={(el) => {
            if (el) matchRefs.current.set(globalMatchIndex, el)
          }}
          className={isCurrentMatch ? "bg-yellow-400 text-black px-0.5 rounded" : "bg-yellow-200 text-black px-0.5 rounded"}
        >
          {segment.text.slice(match.startInSegment, match.endInSegment)}
        </mark>
      )

      lastEnd = match.endInSegment
    })

    if (lastEnd < segment.text.length) {
      parts.push(segment.text.slice(lastEnd))
    }

    return parts
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 p-2 border-b">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search transcript..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-8 pr-8"
          />
          {query && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearSearch}
              className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6 p-0"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>

        {matches.length > 0 && (
          <>
            <span className="text-sm text-muted-foreground whitespace-nowrap">
              {currentMatchIndex + 1} of {matches.length}
            </span>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={goToPrevMatch} className="h-8 w-8 p-0" title="Previous match (Shift+Enter)">
                <ChevronUp className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={goToNextMatch} className="h-8 w-8 p-0" title="Next match (Enter)">
                <ChevronDown className="h-4 w-4" />
              </Button>
            </div>
          </>
        )}

        {debouncedQuery && matches.length === 0 && <span className="text-sm text-muted-foreground">No matches</span>}
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2">
          {segments.map((segment, index) => (
            <div key={index} className="flex gap-3">
              {hasTimestamps && segment.start_time > 0 && (
                <span className="text-xs text-muted-foreground font-mono shrink-0 w-16">{formatTimestamp(segment.start_time)}</span>
              )}
              <p className="text-sm leading-relaxed">{renderSegmentText(segment, index)}</p>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
