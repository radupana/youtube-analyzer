"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface Video {
  id: string
  title: string
  channel_title: string
  status: string
  transcript?: string
  transcript_source?: string
}

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

interface TaskProgress {
  status: string
  progress: number
  total: number
  processed: number
  message: string
  videos_added: string[]
  current_video?: string
  current_step?: string
  elapsed_time?: number
}

export default function Home() {
  const [videos, setVideos] = useState<Video[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputUrl, setInputUrl] = useState("")
  const [chatInput, setChatInput] = useState("")
  const [urlError, setUrlError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sendingMessage, setSendingMessage] = useState(false)
  const [currentTask, setCurrentTask] = useState<string | null>(null)
  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null)

  // Poll for videos periodically
  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/videos")
        const data = await response.json()
        setVideos(data.videos)
      } catch (error) {
        console.error("Error fetching videos:", error)
      }
    }

    fetchVideos()
    const interval = setInterval(fetchVideos, 2000) // Poll every 2 seconds
    return () => clearInterval(interval)
  }, [])

  // Poll for task progress
  useEffect(() => {
    if (!currentTask) return

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/v1/videos/task/${currentTask}`)
        if (response.ok) {
          const progress = await response.json()
          setTaskProgress(progress)

          if (progress.status === "completed" || progress.status === "failed") {
            setLoading(false)
            setCurrentTask(null)
            setTimeout(() => setTaskProgress(null), 3000) // Clear progress after 3 seconds
          }
        }
      } catch (error) {
        console.error("Error fetching task progress:", error)
      }
    }, 500) // Poll every 500ms for progress

    return () => clearInterval(interval)
  }, [currentTask])

  // Basic frontend validation for URL type
  const isChannelUrl = (url: string) => {
    return /@[^/\s]+/.test(url) ||
           /\/channel\//.test(url) ||
           /\/c\//.test(url) ||
           /\/user\//.test(url)
  }

  const isPlaylistOnlyUrl = (url: string) => {
    // Reject playlist pages without a video
    if (url.includes("list=") && !url.includes("watch?v=")) return true
    return url.includes("/playlist?");
  }

  const handleAddVideo = async () => {
    setUrlError(null)

    // Frontend validation
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
      const response = await fetch("http://localhost:8000/api/v1/videos/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: inputUrl }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        setUrlError(errorData.detail || "Failed to add video")
        setLoading(false)
        return
      }

      const data = await response.json()
      setCurrentTask(data.task_id)
      setInputUrl("")
    } catch (error) {
      console.error("Error adding video:", error)
      setUrlError("Failed to add video. Check if the backend is running.")
      setLoading(false)
    }
  }

  const handleRemoveVideo = async (videoId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/videos/${videoId}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error("Failed to remove video")
      }

      // Refresh video list
      const videosResponse = await fetch("http://localhost:8000/api/v1/videos")
      const videosData = await videosResponse.json()
      setVideos(videosData.videos)
    } catch (error) {
      console.error("Error removing video:", error)
    }
  }

  const handleSendMessage = async () => {
    if (!chatInput.trim()) return

    const userMessage: ChatMessage = { role: "user", content: chatInput }
    setMessages([...messages, userMessage])
    const messageText = chatInput // Save the message before clearing
    setChatInput("")
    setSendingMessage(true)

    try {
      const response = await fetch("http://localhost:8000/api/v1/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText }),
      })

      if (!response.ok) {
        throw new Error("Failed to send message")
      }

      const data = await response.json()

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.response,
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error("Error sending message:", error)
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "Error: Failed to get response. Please check if the backend is running.",
      }
      setMessages(prev => [...prev, errorMessage])
    }
    setSendingMessage(false)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready":
        return "text-green-600"
      case "processing":
        return "text-yellow-600"
      case "error":
        return "text-red-600"
      default:
        return "text-gray-600"
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "ready":
        return "Ready"
      case "processing":
        return "Processing..."
      case "error":
        return "No transcript"
      default:
        return status
    }
  }

  return (
    <div className="container mx-auto p-4 max-w-7xl">
      <h1 className="text-4xl font-bold mb-6">YouTube Analyzer</h1>

      <div className="grid grid-cols-3 gap-6 h-[calc(100vh-140px)]">
        <div className="col-span-1 flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Add video</CardTitle>
              <CardDescription>
                Paste a YouTube video URL to analyze
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="url">YouTube Video URL</Label>
                <Input
                  id="url"
                  type="url"
                  placeholder="https://youtube.com/watch?v=..."
                  value={inputUrl}
                  onChange={(e) => {
                    setInputUrl(e.target.value)
                    setUrlError(null)
                  }}
                  disabled={loading}
                  className={urlError ? "border-red-500" : ""}
                />
                {urlError && (
                  <p className="text-sm text-red-500 mt-1">{urlError}</p>
                )}
              </div>
              <Button
                onClick={handleAddVideo}
                disabled={loading || !inputUrl}
                className="w-full"
              >
                {loading ? (
                  taskProgress && taskProgress.current_step?.startsWith('whisper_') ?
                    taskProgress.current_step === 'whisper_downloading' ? "Downloading audio..." :
                    taskProgress.current_step === 'whisper_loading' ? "Loading Whisper..." :
                    taskProgress.current_step === 'whisper_transcribing' ? "Transcribing..." :
                    "Processing..." :
                    "Processing..."
                ) : "Add video"}
              </Button>

              {/* Progress indicator */}
              {taskProgress && (
                <div className="mt-4 p-3 border rounded-lg bg-muted/50">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="text-sm font-medium">{taskProgress.message}</div>
                      {taskProgress.current_video && (
                        <div className="text-xs text-muted-foreground mt-1">
                          {taskProgress.current_video}
                        </div>
                      )}
                    </div>
                    {taskProgress.elapsed_time !== undefined && taskProgress.elapsed_time > 0 && (
                      <div className="text-xs text-muted-foreground ml-2">
                        {Math.floor(taskProgress.elapsed_time / 60)}:{(taskProgress.elapsed_time % 60).toString().padStart(2, '0')}
                      </div>
                    )}
                  </div>

                  <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all duration-300"
                      style={{ width: `${taskProgress.progress || 0}%` }}
                    />
                  </div>

                  {taskProgress.current_step && (
                    <div className="text-xs text-muted-foreground">
                      {taskProgress.current_step === 'cache' && 'Loading from cache...'}
                      {taskProgress.current_step === 'whisper_downloading' && 'Downloading audio...'}
                      {taskProgress.current_step === 'whisper_loading' && 'Loading Whisper model...'}
                      {taskProgress.current_step === 'whisper_transcribing' && 'Transcribing with Whisper...'}
                      {taskProgress.current_step === 'transcript' && 'Fetching transcript...'}
                      {taskProgress.current_step === 'metadata' && 'Loading video info...'}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Loaded Videos ({videos.length})</CardTitle>
                {videos.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      try {
                        await fetch("http://localhost:8000/api/v1/videos/cache/clear", {
                          method: "DELETE",
                        })
                        setVideos([])
                      } catch (error) {
                        console.error("Error clearing cache:", error)
                      }
                    }}
                    className="text-red-600 hover:text-red-700"
                  >
                    Clear All
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 overflow-hidden">
              {videos.length === 0 ? (
                <p className="text-muted-foreground">No videos loaded</p>
              ) : (
                <div className="h-full overflow-y-auto">
                  <ul className="space-y-2">
                    {videos.map((video) => (
                      <li key={video.id} className="p-2 border rounded-lg overflow-hidden">
                        <div className="flex justify-between items-start">
                          <div className="flex-1 min-w-0 mr-2">
                            <div className="font-medium text-sm truncate" title={video.title}>
                              {video.title}
                            </div>
                            <div className="text-muted-foreground text-xs">
                              {video.channel_title}
                            </div>
                            <div className="text-xs mt-1">
                              <span className={getStatusColor(video.status)}>
                                {getStatusText(video.status)}
                              </span>
                              {video.status === "ready" && video.transcript_source === "youtube" && (
                                <span className="text-green-600">
                                  {" "}• 📝 YouTube captions
                                </span>
                              )}
                              {video.status === "ready" && video.transcript_source === "whisper" && (
                                <span className="text-blue-600">
                                  {" "}• 🎤 Whisper transcript
                                </span>
                              )}
                              {video.status === "ready" && video.transcript_source === "skipped" && (
                                <span className="text-gray-500">
                                  {" "}• Metadata only
                                </span>
                              )}
                              {video.status === "error" && (
                                <span className="text-red-500">
                                  {" "}• ❌ No transcript available
                                </span>
                              )}
                            </div>
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleRemoveVideo(video.id)}
                            className="shrink-0 text-red-600 hover:text-red-700"
                          >
                            Remove
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="col-span-2 flex flex-col">
          <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <CardHeader>
              <CardTitle>Chat</CardTitle>
              <CardDescription>
                Ask questions about your loaded videos
                {videos.filter(v => v.status === "ready" && v.transcript_source === "youtube").length > 0 && (
                  <span className="text-green-600">
                    {" "}• {videos.filter(v => v.status === "ready" && v.transcript_source === "youtube").length} with YouTube captions
                  </span>
                )}
                {videos.filter(v => v.status === "ready" && v.transcript_source === "whisper").length > 0 && (
                  <span className="text-blue-600">
                    {" "}• {videos.filter(v => v.status === "ready" && v.transcript_source === "whisper").length} with Whisper transcripts
                  </span>
                )}
                {videos.filter(v => v.status === "error").length > 0 && (
                  <span className="text-red-500">
                    {" "}• {videos.filter(v => v.status === "error").length} failed
                  </span>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col min-h-0 !p-0">
              <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
                <div className="space-y-4">
                  {messages.length === 0 ? (
                    <p className="text-muted-foreground text-center">
                      Add a YouTube video, then ask questions about it!
                    </p>
                  ) : (
                    messages.map((message, index) => (
                      <div
                        key={index}
                        className={`flex ${
                          message.role === "user" ? "justify-end" : "justify-start"
                        }`}
                      >
                        <div
                          className={`max-w-[80%] rounded-lg px-4 py-2 ${
                            message.role === "user"
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted"
                          }`}
                        >
                          <pre className="whitespace-pre-wrap font-sans">
                            {message.content}
                          </pre>
                        </div>
                      </div>
                    ))
                  )}
                  {sendingMessage && (
                    <div className="flex justify-start">
                      <div className="bg-muted rounded-lg px-4 py-2">
                        <span className="text-muted-foreground">Thinking...</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex gap-2 px-6 pb-6">
                <Input
                  className="flex-1"
                  placeholder="Ask about the videos..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && !sendingMessage && handleSendMessage()}
                  disabled={sendingMessage}
                />
                <Button
                  className="shrink-0"
                  onClick={handleSendMessage}
                  disabled={sendingMessage || !chatInput.trim()}
                >
                  {sendingMessage ? "Sending..." : "Send"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
