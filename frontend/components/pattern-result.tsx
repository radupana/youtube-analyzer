"use client"

import { useState } from "react"
import { X, Copy, Check } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface PatternResultProps {
  patternName: string
  result: string
  modelUsed: string
  onClose: () => void
}

export function PatternResult({ patternName, result, modelUsed, onClose }: PatternResultProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card data-testid="pattern-result" className="max-h-[50vh] flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between pb-2 shrink-0">
        <CardTitle data-testid="pattern-result-title" className="text-base">{patternName}</CardTitle>
        <div className="flex gap-1">
          <Button data-testid="pattern-result-copy" variant="ghost" size="sm" onClick={handleCopy} className="h-8 w-8 p-0">
            {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
          </Button>
          <Button data-testid="pattern-result-close" variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0">
        <div data-testid="pattern-result-content" className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown>{result}</ReactMarkdown>
        </div>
        <div data-testid="pattern-result-model" className="text-xs text-muted-foreground mt-4 pt-2 border-t">
          Generated with {modelUsed}
        </div>
      </CardContent>
    </Card>
  )
}
