"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import ReactMarkdown from "react-markdown"
import { Copy, Check, Download, Sparkles, RefreshCw, FileText, Trash2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SessionSidebar } from "@/components/session-sidebar"
import { TranscriptViewer } from "@/components/transcript-viewer"
import { PatternSelector } from "@/components/pattern-selector"
import { PatternResult } from "@/components/pattern-result"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Video,
  TranscriptResponse,
  ExportFormat,
  PatternResult as PatternResultType,
  fetchSession,
  fetchSessionVideos,
  addVideo,
  removeVideo,
  fetchTaskProgress,
  sendChatMessageStream,
  fetchProviders,
  fetchCurrentProvider,
  setProvider,
  createSession,
  exportTranscript,
  copyTranscript,
  fetchTranscript,
} from "@/lib/api"

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

interface TaskProgress {
  status: string
  progress: number
  message: string
  current_video?: string
  current_step?: string
  elapsed_time?: number
}

interface LLMProvider {
  id: string
  name: string
  model: string
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionTitle, setSessionTitle] = useState<string>("")
  const [videos, setVideos] = useState<Video[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputUrl, setInputUrl] = useState("")
  const [chatInput, setChatInput] = useState("")
  const [urlError, setUrlError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sendingMessage, setSendingMessage] = useState(false)
  const [currentTask, setCurrentTask] = useState<string | null>(null)
  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null)
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [currentProvider, setCurrentProvider] = useState<LLMProvider | null>(null)
  const [initializing, setInitializing] = useState(true)
  const [copiedVideoId, setCopiedVideoId] = useState<string | null>(null)
  const [activeTranscript, setActiveTranscript] = useState<TranscriptResponse | null>(null)
  const [loadingTranscript, setLoadingTranscript] = useState<string | null>(null)
  const [patternResult, setPatternResult] = useState<PatternResultType | null>(null)
  const [selectedVideoForPattern, setSelectedVideoForPattern] = useState<string | null>(null)
  const [videoToDelete, setVideoToDelete] = useState<Video | null>(null)
  const streamingRef = useRef(false)

  const loadSession = useCallback(async (sid: string) => {
    try {
      const [session, sessionVideos] = await Promise.all([
        fetchSession(sid),
        fetchSessionVideos(sid),
      ])
      setSessionId(sid)
      setSessionTitle(session.title)
      setVideos(sessionVideos)
      setMessages(
        session.messages.map(m => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }))
      )
      localStorage.setItem("youtube-analyzer-session", sid)
    } catch (error) {
      console.error("Failed to load session:", error)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      const savedSessionId = localStorage.getItem("youtube-analyzer-session")
      if (savedSessionId) {
        try {
          await loadSession(savedSessionId)
        } catch {
          localStorage.removeItem("youtube-analyzer-session")
        }
      }
      setInitializing(false)
    }
    init()
  }, [loadSession])

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const [providersList, current] = await Promise.all([
          fetchProviders(),
          fetchCurrentProvider(),
        ])
        setProviders(providersList)
        setCurrentProvider(current)
      } catch (error) {
        console.error("Error fetching providers:", error)
      }
    }
    loadProviders()
  }, [])

  useEffect(() => {
    if (!currentTask) return

    const interval = setInterval(async () => {
      try {
        const progress = await fetchTaskProgress(currentTask)
        setTaskProgress(progress)

        if (progress.status === "completed" || progress.status === "failed") {
          setLoading(false)
          setCurrentTask(null)
          if (sessionId) {
            const videos = await fetchSessionVideos(sessionId)
            setVideos(videos)
          }
          setTimeout(() => setTaskProgress(null), 3000)
        }
      } catch (error) {
        console.error("Error fetching task progress:", error)
      }
    }, 500)

    return () => clearInterval(interval)
  }, [currentTask, sessionId])

  const handleSessionSelect = async (sid: string) => {
    await loadSession(sid)
  }

  const handleSessionCreated = async (sid: string) => {
    await loadSession(sid)
  }

  const handleSessionDeleted = async (deletedId: string, newActiveId: string | null) => {
    if (newActiveId) {
      await loadSession(newActiveId)
    } else {
      const session = await createSession("New Session")
      await loadSession(session.id)
    }
  }

  const isChannelUrl = (url: string) => {
    return /@[^/\s]+/.test(url) || /\/channel\//.test(url) || /\/c\//.test(url) || /\/user\//.test(url)
  }

  const isPlaylistOnlyUrl = (url: string) => {
    if (url.includes("list=") && !url.includes("watch?v=")) return true
    return url.includes("/playlist?")
  }

  const handleAddVideo = async () => {
    setUrlError(null)

    if (!sessionId) {
      setUrlError("No session selected. Please create or select a session.")
      return
    }

    if (isChannelUrl(inputUrl)) {
      setUrlError("Only single video URLs are supported. Please paste a video URL, not a channel.")
      return
    }
    if (isPlaylistOnlyUrl(inputUrl)) {
      setUrlError("Only single video URLs are supported. Please paste a video URL, not a playlist.")
      return
    }

    setLoading(true)
    setTaskProgress(null)

    try {
      const data = await addVideo(inputUrl, sessionId)
      setCurrentTask(data.task_id)
      setInputUrl("")
    } catch (error) {
      setUrlError(error instanceof Error ? error.message : "Failed to add video")
      setLoading(false)
    }
  }

  const handleRemoveVideo = async (video: Video) => {
    setVideoToDelete(video)
  }

  const confirmRemoveVideo = async () => {
    if (!sessionId || !videoToDelete) return

    try {
      await removeVideo(sessionId, videoToDelete.id)
      const updatedVideos = await fetchSessionVideos(sessionId)
      setVideos(updatedVideos)
    } catch (error) {
      console.error("Error removing video:", error)
    }
    setVideoToDelete(null)
  }

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !sessionId) return
    if (streamingRef.current) return // Prevent double invocation
    streamingRef.current = true

    const userMessage: ChatMessage = { role: "user", content: chatInput }
    setMessages(prev => [...prev, userMessage])
    const messageText = chatInput
    setChatInput("")
    setSendingMessage(true)

    const assistantMessage: ChatMessage = { role: "assistant", content: "" }
    setMessages(prev => [...prev, assistantMessage])

    try {
      await sendChatMessageStream(
        messageText,
        sessionId,
        (chunk) => {
          setMessages(prev =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === "assistant"
                ? { ...msg, content: msg.content + chunk }
                : msg
            )
          )
        }
      )
    } catch (error) {
      setMessages(prev =>
        prev.map((msg, i) =>
          i === prev.length - 1 && msg.role === "assistant"
            ? { ...msg, content: `Error: ${error instanceof Error ? error.message : "Failed to get response"}` }
            : msg
        )
      )
    }
    setSendingMessage(false)
    streamingRef.current = false
  }

  const handleProviderChange = async (providerId: string) => {
    try {
      await setProvider(providerId)
      const current = await fetchCurrentProvider()
      setCurrentProvider(current)
    } catch (error) {
      console.error("Error changing provider:", error)
    }
  }

  const handleExport = async (videoId: string, format: ExportFormat) => {
    try {
      const { blob, filename } = await exportTranscript(videoId, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error("Export failed:", error)
    }
  }

  const handleCopy = async (videoId: string) => {
    try {
      const text = await copyTranscript(videoId)
      await navigator.clipboard.writeText(text)
      setCopiedVideoId(videoId)
      setTimeout(() => setCopiedVideoId(null), 2000)
    } catch (error) {
      console.error("Copy failed:", error)
    }
  }

  const handleViewTranscript = async (videoId: string) => {
    if (activeTranscript?.video_id === videoId) {
      setActiveTranscript(null)
      return
    }

    setLoadingTranscript(videoId)
    try {
      const transcript = await fetchTranscript(videoId)
      setActiveTranscript(transcript)
    } catch (error) {
      console.error("Failed to load transcript:", error)
    }
    setLoadingTranscript(null)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready": return "text-green-600"
      case "processing": return "text-yellow-600"
      case "error": return "text-red-600"
      default: return "text-gray-600"
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "ready": return "Ready"
      case "processing": return "Processing..."
      case "error": return "No transcript"
      default: return status
    }
  }

  if (initializing) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  return (
    <div className="flex h-screen">
      <SessionSidebar
        activeSessionId={sessionId}
        onSessionSelect={handleSessionSelect}
        onSessionCreated={handleSessionCreated}
        onSessionDeleted={handleSessionDeleted}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b">
          <div>
            <h1 className="text-2xl font-bold">YouTube Analyzer</h1>
            {sessionTitle && (
              <p className="text-sm text-muted-foreground">{sessionTitle}</p>
            )}
          </div>
          {providers.length > 0 && (
            <div className="flex items-center gap-2">
              <Label htmlFor="provider" className="text-sm text-muted-foreground">Model:</Label>
              <select
                id="provider"
                value={currentProvider?.id || ""}
                onChange={e => handleProviderChange(e.target.value)}
                className="border rounded px-2 py-1 text-sm bg-background"
              >
                {providers.map(provider => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <div className="grid grid-cols-3 gap-4 h-full">
            <div className="col-span-1 flex flex-col gap-4 overflow-hidden">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Add Video</CardTitle>
                  <CardDescription>Paste a YouTube video URL</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <Input
                      type="url"
                      placeholder="https://youtube.com/watch?v=..."
                      value={inputUrl}
                      onChange={e => {
                        setInputUrl(e.target.value)
                        setUrlError(null)
                      }}
                      disabled={loading || !sessionId}
                      className={urlError ? "border-red-500" : ""}
                    />
                    {urlError && <p className="text-sm text-red-500 mt-1">{urlError}</p>}
                  </div>
                  <Button
                    onClick={handleAddVideo}
                    disabled={loading || !inputUrl || !sessionId}
                    className="w-full"
                    size="sm"
                  >
                    {loading ? "Processing..." : "Add Video"}
                  </Button>

                  {taskProgress && (
                    <div className="p-2 border rounded bg-muted/50 text-sm">
                      <div className="font-medium">{taskProgress.message}</div>
                      {taskProgress.current_video && (
                        <div className="text-xs text-muted-foreground truncate">{taskProgress.current_video}</div>
                      )}
                      <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
                        <div
                          className="bg-primary h-1.5 rounded-full transition-all"
                          style={{ width: `${taskProgress.progress || 0}%` }}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Videos ({videos.length})</CardTitle>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto">
                  {videos.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No videos loaded</p>
                  ) : (
                    <ul className="space-y-2">
                      {videos.map(video => (
                        <li key={video.id} className="p-2 border rounded text-sm">
                          <div className="flex justify-between items-start gap-2">
                            <div className="min-w-0 flex-1">
                              <div className="font-medium truncate" title={video.title}>{video.title}</div>
                              <div className="text-xs text-muted-foreground">{video.channel_title}</div>
                              <div className="text-xs mt-1">
                                <span className={getStatusColor(video.status)}>{getStatusText(video.status)}</span>
                                {video.transcript_source === "youtube" && <span className="text-green-600"> · Captions</span>}
                                {video.transcript_source === "whisper" && <span className="text-blue-600"> · Whisper</span>}
                              </div>
                            </div>
                            <TooltipProvider delayDuration={200}>
                              <div className="flex items-center gap-1">
                                {video.status === "ready" && (
                                  <>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          onClick={() => setSelectedVideoForPattern(selectedVideoForPattern === video.id ? null : video.id)}
                                          className="h-6 w-6 p-0"
                                        >
                                          <Sparkles className={`h-3 w-3 ${selectedVideoForPattern === video.id ? "text-yellow-500" : ""}`} />
                                        </Button>
                                      </TooltipTrigger>
                                      <TooltipContent>Analyze with patterns</TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          onClick={() => handleViewTranscript(video.id)}
                                          disabled={loadingTranscript === video.id}
                                          className="h-6 w-6 p-0"
                                        >
                                          {loadingTranscript === video.id ? (
                                            <RefreshCw className="h-3 w-3 animate-spin" />
                                          ) : (
                                            <FileText className={`h-3 w-3 ${activeTranscript?.video_id === video.id ? "text-blue-500" : ""}`} />
                                          )}
                                        </Button>
                                      </TooltipTrigger>
                                      <TooltipContent>
                                        {activeTranscript?.video_id === video.id ? "Hide transcript" : "View transcript"}
                                      </TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          onClick={() => handleCopy(video.id)}
                                          className="h-6 w-6 p-0"
                                        >
                                          {copiedVideoId === video.id ? (
                                            <Check className="h-3 w-3 text-green-600" />
                                          ) : (
                                            <Copy className="h-3 w-3" />
                                          )}
                                        </Button>
                                      </TooltipTrigger>
                                      <TooltipContent>Copy transcript</TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <DropdownMenu>
                                          <DropdownMenuTrigger asChild>
                                            <Button size="sm" variant="ghost" className="h-6 w-6 p-0">
                                              <Download className="h-3 w-3" />
                                            </Button>
                                          </DropdownMenuTrigger>
                                          <DropdownMenuContent align="end">
                                            <DropdownMenuItem onClick={() => handleExport(video.id, "txt")}>
                                              Plain Text (.txt)
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => handleExport(video.id, "md")}>
                                              Markdown (.md)
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => handleExport(video.id, "srt")}>
                                              Subtitles (.srt)
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => handleExport(video.id, "json")}>
                                              JSON (.json)
                                            </DropdownMenuItem>
                                          </DropdownMenuContent>
                                        </DropdownMenu>
                                      </TooltipTrigger>
                                      <TooltipContent>Download</TooltipContent>
                                    </Tooltip>
                                  </>
                                )}
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => handleRemoveVideo(video)}
                                      className="shrink-0 h-6 w-6 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                    >
                                      <Trash2 className="h-3 w-3" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Remove video</TooltipContent>
                                </Tooltip>
                              </div>
                            </TooltipProvider>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="col-span-2 flex flex-col min-h-0 gap-4">
              {selectedVideoForPattern && (
                <PatternSelector
                  videoId={selectedVideoForPattern}
                  onPatternApplied={(result) => {
                    setPatternResult(result)
                    setSelectedVideoForPattern(null)
                  }}
                  onClose={() => setSelectedVideoForPattern(null)}
                />
              )}
              {patternResult && (
                <PatternResult
                  patternName={patternResult.pattern_name}
                  result={patternResult.result}
                  modelUsed={patternResult.model_used}
                  onClose={() => setPatternResult(null)}
                />
              )}
              {activeTranscript && (
                <Card className="h-[40%] flex flex-col min-h-0">
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <div className="min-w-0 flex-1">
                      <CardTitle className="text-lg">Transcript</CardTitle>
                      <CardDescription className="truncate">{activeTranscript.video_title}</CardDescription>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setActiveTranscript(null)} className="h-8 w-8 p-0 shrink-0">
                      <span className="text-lg">&times;</span>
                    </Button>
                  </CardHeader>
                  <CardContent className="flex-1 p-0 min-h-0">
                    <TranscriptViewer segments={activeTranscript.segments} hasTimestamps={activeTranscript.has_timestamps} />
                  </CardContent>
                </Card>
              )}
              <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Chat</CardTitle>
                  <CardDescription>Ask questions about your videos</CardDescription>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col min-h-0 p-0">
                  <div className="flex-1 overflow-y-auto px-6 py-2">
                    {messages.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-8">
                        Add a video and ask questions about it
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {messages.map((message, index) => (
                          <div
                            key={index}
                            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                                message.role === "user"
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-muted"
                              }`}
                            >
                              {message.role === "user" ? (
                                <pre className="whitespace-pre-wrap font-sans">{message.content}</pre>
                              ) : (
                                <div className="prose prose-sm max-w-none dark:prose-invert">
                                  <ReactMarkdown>{message.content}</ReactMarkdown>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                        {sendingMessage && messages[messages.length - 1]?.content === "" && (
                          <div className="flex justify-start">
                            <div className="bg-muted rounded-lg px-3 py-2 text-sm text-muted-foreground animate-pulse">
                              Generating...
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 p-4 border-t">
                    <Input
                      placeholder="Ask about the videos..."
                      value={chatInput}
                      onChange={e => setChatInput(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && !sendingMessage && handleSendMessage()}
                      disabled={sendingMessage || !sessionId}
                    />
                    <Button
                      onClick={handleSendMessage}
                      disabled={sendingMessage || !chatInput.trim() || !sessionId}
                    >
                      Send
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>

      <AlertDialog open={videoToDelete !== null} onOpenChange={(open) => !open && setVideoToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove video?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove &quot;{videoToDelete?.title}&quot; from this session. The video data will remain cached in the database for future use.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRemoveVideo} className="bg-red-600 hover:bg-red-700">
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
