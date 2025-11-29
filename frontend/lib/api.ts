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
  channel_id: string
  channel_title: string
  duration: string
  published_at: string
  status: string
  progress: number
  progress_message?: string
  error_message?: string
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

export async function addVideo(url: string, sessionId: string): Promise<{ video_id: string; status: string }> {
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

export async function sendChatMessageStream(
  message: string,
  sessionId: string,
  onChunk: (chunk: string) => void,
  onSessionId?: (sessionId: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/message/stream`, {
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

  const reader = response.body?.getReader()
  if (!reader) throw new Error("No response body")

  const decoder = new TextDecoder()
  let isFirstMessage = true
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Process complete lines only (SSE format: "data: ...\n\n")
    const lines = buffer.split("\n")
    // Keep the last incomplete line in the buffer
    buffer = lines.pop() || ""

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6)
        if (data === "[DONE]") continue

        if (isFirstMessage) {
          onSessionId?.(data)
          isFirstMessage = false
        } else {
          const unescaped = data.replace(/\\n/g, "\n")
          onChunk(unescaped)
        }
      }
    }
  }

  // Process any remaining data in buffer
  if (buffer.startsWith("data: ")) {
    const data = buffer.slice(6)
    if (data !== "[DONE]" && !isFirstMessage) {
      const unescaped = data.replace(/\\n/g, "\n")
      onChunk(unescaped)
    }
  }
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


export interface TranscriptSegment {
  text: string
  start_time: number
  end_time: number
}

export interface TranscriptResponse {
  video_id: string
  video_title: string
  full_text: string
  segments: TranscriptSegment[]
  has_timestamps: boolean
}

export async function fetchTranscript(videoId: string): Promise<TranscriptResponse> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/transcript`)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || "Failed to fetch transcript")
  }

  return response.json()
}

export interface Pattern {
  id: string
  name: string
  description: string
  icon: string
  category: string
}

export interface PatternResult {
  video_id: string
  pattern_id: string
  pattern_name: string
  result: string
  model_used: string
  created_at: string
}

export interface CachedPatternResult {
  pattern_id: string
  model_used: string
  created_at: string
}

export async function fetchPatterns(): Promise<Pattern[]> {
  const response = await fetch(`${API_BASE}/patterns`)
  if (!response.ok) throw new Error("Failed to fetch patterns")
  const data = await response.json()
  return data.patterns
}

export async function fetchVideoPatternResults(videoId: string): Promise<CachedPatternResult[]> {
  const response = await fetch(`${API_BASE}/patterns/videos/${videoId}/results`)
  if (!response.ok) return []
  return response.json()
}

export async function applyPattern(
  videoId: string,
  patternId: string,
  refresh: boolean = false
): Promise<PatternResult> {
  const endpoint = refresh
    ? `${API_BASE}/patterns/videos/${videoId}/results/${patternId}/refresh`
    : `${API_BASE}/patterns/videos/${videoId}/results/${patternId}`

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || "Failed to apply pattern")
  }

  return response.json()
}

export async function deletePatternResult(videoId: string, patternId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/patterns/videos/${videoId}/results/${patternId}`, {
    method: "DELETE",
  })
  if (!response.ok) throw new Error("Failed to delete pattern result")
}
