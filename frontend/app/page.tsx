"use client"

import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SessionSidebar } from "@/components/session-sidebar"
import {
  Video,
  fetchSession,
  fetchSessionVideos,
  addVideo,
  removeVideo,
  fetchTaskProgress,
  sendChatMessage,
  fetchProviders,
  fetchCurrentProvider,
  setProvider,
  createSession,
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

  const handleRemoveVideo = async (videoId: string) => {
    if (!sessionId) return

    try {
      await removeVideo(sessionId, videoId)
      const updatedVideos = await fetchSessionVideos(sessionId)
      setVideos(updatedVideos)
    } catch (error) {
      console.error("Error removing video:", error)
    }
  }

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !sessionId) return

    const userMessage: ChatMessage = { role: "user", content: chatInput }
    setMessages(prev => [...prev, userMessage])
    const messageText = chatInput
    setChatInput("")
    setSendingMessage(true)

    try {
      const data = await sendChatMessage(messageText, sessionId)
      const assistantMessage: ChatMessage = { role: "assistant", content: data.response }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: `Error: ${error instanceof Error ? error.message : "Failed to get response"}`,
      }
      setMessages(prev => [...prev, errorMessage])
    }
    setSendingMessage(false)
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
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRemoveVideo(video.id)}
                              className="shrink-0 h-6 px-2 text-red-600 hover:text-red-700"
                            >
                              ×
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="col-span-2 flex flex-col min-h-0">
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
                              <pre className="whitespace-pre-wrap font-sans">{message.content}</pre>
                            </div>
                          </div>
                        ))}
                        {sendingMessage && (
                          <div className="flex justify-start">
                            <div className="bg-muted rounded-lg px-3 py-2 text-sm text-muted-foreground">
                              Thinking...
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
    </div>
  )
}
