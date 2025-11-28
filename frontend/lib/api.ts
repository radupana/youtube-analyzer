const API_BASE = "http://localhost:8000/api/v1"

export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
  video_count: number
  message_count: number
}

export interface SessionDetail {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: { id: string; role: string; content: string; created_at: string }[]
  videos: { id: string; video_id: string; title: string; channel_title: string; transcript_source: string | null; added_at: string }[]
}

export interface Video {
  id: string
  title: string
  channel_title: string
  status: string
  transcript?: string
  transcript_source?: string
}

export async function fetchSessions(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/sessions`)
  if (!response.ok) throw new Error("Failed to fetch sessions")
  const data = await response.json()
  return data.sessions
}

export async function fetchSession(id: string): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${id}`)
  if (!response.ok) throw new Error("Failed to fetch session")
  return response.json()
}

export async function createSession(title: string): Promise<{ id: string; title: string }> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  })
  if (!response.ok) throw new Error("Failed to create session")
  return response.json()
}

export async function updateSession(id: string, title: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  })
  if (!response.ok) throw new Error("Failed to update session")
}

export async function deleteSession(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${id}`, {
    method: "DELETE",
  })
  if (!response.ok) throw new Error("Failed to delete session")
}

export async function fetchSessionVideos(sessionId: string): Promise<Video[]> {
  const response = await fetch(`${API_BASE}/videos/session/${sessionId}`)
  if (!response.ok) throw new Error("Failed to fetch videos")
  const data = await response.json()
  return data.videos
}

export async function addVideo(url: string, sessionId: string): Promise<{ task_id: string }> {
  const response = await fetch(`${API_BASE}/videos/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, session_id: sessionId }),
  })
  if (!response.ok) {
    const errorData = await response.json()
    const detail = errorData.detail
    if (typeof detail === "string") throw new Error(detail)
    if (Array.isArray(detail)) throw new Error(detail.map((e: { msg: string }) => e.msg).join(", "))
    throw new Error("Failed to add video")
  }
  return response.json()
}

export async function removeVideo(sessionId: string, videoId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/videos/session/${sessionId}/video/${videoId}`, {
    method: "DELETE",
  })
  if (!response.ok) throw new Error("Failed to remove video")
}

export async function fetchTaskProgress(taskId: string): Promise<{
  status: string
  progress: number
  message: string
  current_video?: string
  current_step?: string
  elapsed_time?: number
}> {
  const response = await fetch(`${API_BASE}/videos/task/${taskId}`)
  if (!response.ok) throw new Error("Failed to fetch task progress")
  return response.json()
}

export async function sendChatMessage(message: string, sessionId: string): Promise<{ response: string }> {
  const response = await fetch(`${API_BASE}/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!response.ok) {
    const errorData = await response.json()
    const detail = errorData.detail
    if (typeof detail === "string") throw new Error(detail)
    if (Array.isArray(detail)) throw new Error(detail.map((e: { msg: string }) => e.msg).join(", "))
    throw new Error("Failed to send message")
  }
  return response.json()
}

export async function fetchProviders(): Promise<{ id: string; name: string; model: string }[]> {
  const response = await fetch(`${API_BASE}/settings/llm-providers`)
  if (!response.ok) return []
  return response.json()
}

export async function fetchCurrentProvider(): Promise<{ id: string; name: string; model: string } | null> {
  const response = await fetch(`${API_BASE}/settings/llm-provider`)
  if (!response.ok) return null
  return response.json()
}

export async function setProvider(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/settings/llm-provider`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  })
  if (!response.ok) throw new Error("Failed to set provider")
}

export type ExportFormat = "txt" | "md" | "srt" | "json"

export async function exportTranscript(
  videoId: string,
  format: ExportFormat
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/export?format=${format}`)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || "Failed to export transcript")
  }

  const disposition = response.headers.get("Content-Disposition")
  const filenameMatch = disposition?.match(/filename="(.+)"/)
  const filename = filenameMatch?.[1] || `transcript.${format}`

  const blob = await response.blob()
  return { blob, filename }
}

export async function copyTranscript(videoId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/export?format=txt`)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || "Failed to fetch transcript")
  }

  return response.text()
}
