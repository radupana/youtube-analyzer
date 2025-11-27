"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Session, fetchSessions, createSession, updateSession, deleteSession } from "@/lib/api"

interface SessionSidebarProps {
  activeSessionId: string | null
  onSessionSelect: (sessionId: string) => void
  onSessionCreated: (sessionId: string) => void
  onSessionDeleted: (deletedId: string, newActiveId: string | null) => void
}

export function SessionSidebar({
  activeSessionId,
  onSessionSelect,
  onSessionCreated,
  onSessionDeleted,
}: SessionSidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState("")
  const editInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const initSessions = async () => {
      try {
        const data = await fetchSessions()
        setSessions(data)

        // Auto-create session if none exist and no active session
        if (data.length === 0 && !activeSessionId) {
          const session = await createSession("Untitled Session")
          setSessions([{ ...session, video_count: 0, message_count: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }])
          onSessionCreated(session.id)
        } else if (data.length > 0 && !activeSessionId) {
          // Select first session if none active
          onSessionSelect(data[0].id)
        }
      } catch (error) {
        console.error("Failed to load sessions:", error)
      } finally {
        setLoading(false)
      }
    }
    initSessions()
  }, [activeSessionId, onSessionCreated, onSessionSelect])

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingId])

  const handleCreateSession = async () => {
    try {
      const session = await createSession("Untitled Session")
      setSessions(prev => [{ ...session, video_count: 0, message_count: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }, ...prev])
      onSessionCreated(session.id)
      setEditingId(session.id)
      setEditingTitle("Untitled Session")
    } catch (error) {
      console.error("Failed to create session:", error)
    }
  }

  const handleStartEdit = (session: Session) => {
    setEditingId(session.id)
    setEditingTitle(session.title)
  }

  const handleSaveEdit = async () => {
    if (!editingId || !editingTitle.trim()) {
      setEditingId(null)
      return
    }

    try {
      await updateSession(editingId, editingTitle.trim())
      setSessions(prev =>
        prev.map(s => (s.id === editingId ? { ...s, title: editingTitle.trim() } : s))
      )
    } catch (error) {
      console.error("Failed to update session:", error)
    } finally {
      setEditingId(null)
    }
  }

  const handleCancelEdit = () => {
    setEditingId(null)
  }

  const handleDeleteSession = async (sessionId: string) => {
    const session = sessions.find(s => s.id === sessionId)
    if (!session) return

    if (!confirm(`Delete "${session.title}"? This will permanently remove all videos and chat history.`)) {
      return
    }

    try {
      await deleteSession(sessionId)
      const remainingSessions = sessions.filter(s => s.id !== sessionId)
      setSessions(remainingSessions)

      if (sessionId === activeSessionId) {
        const newActiveId = remainingSessions.length > 0 ? remainingSessions[0].id : null
        onSessionDeleted(sessionId, newActiveId)
      }
    } catch (error) {
      console.error("Failed to delete session:", error)
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  if (loading) {
    return (
      <div className="w-64 border-r bg-muted/30 p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-8 bg-muted rounded" />
          <div className="h-16 bg-muted rounded" />
          <div className="h-16 bg-muted rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="w-64 border-r bg-muted/30 flex flex-col">
      <div className="p-3 border-b">
        <Button onClick={handleCreateSession} className="w-full" size="sm">
          + New Session
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground p-2">No sessions yet</p>
          ) : (
            sessions.map(session => (
              <div
                key={session.id}
                className={`group relative p-2 rounded-md cursor-pointer transition-colors ${
                  session.id === activeSessionId
                    ? "bg-primary/10 border border-primary/20"
                    : "hover:bg-muted"
                }`}
                onClick={() => {
                  if (editingId !== session.id) {
                    onSessionSelect(session.id)
                  }
                }}
              >
                {editingId === session.id ? (
                  <Input
                    ref={editInputRef}
                    value={editingTitle}
                    onChange={e => setEditingTitle(e.target.value)}
                    onBlur={handleSaveEdit}
                    onKeyDown={e => {
                      if (e.key === "Enter") handleSaveEdit()
                      if (e.key === "Escape") handleCancelEdit()
                    }}
                    className="h-6 text-sm"
                    onClick={e => e.stopPropagation()}
                  />
                ) : (
                  <div
                    className="font-medium text-sm truncate pr-12"
                    title={session.title}
                  >
                    {session.title}
                  </div>
                )}
                <div className="text-xs text-muted-foreground mt-1">
                  {session.video_count} videos · {session.message_count} messages
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate(session.updated_at)}
                </div>

                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    className="text-muted-foreground hover:text-primary"
                    onClick={e => {
                      e.stopPropagation()
                      handleStartEdit(session)
                    }}
                    title="Rename session"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                      <path d="m15 5 4 4" />
                    </svg>
                  </button>
                  <button
                    className="text-muted-foreground hover:text-red-600"
                    onClick={e => {
                      e.stopPropagation()
                      handleDeleteSession(session.id)
                    }}
                    title="Delete session"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 6h18" />
                      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
