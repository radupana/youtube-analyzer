import { API_BASE_URL } from "./fixtures"

export async function clearDatabase(): Promise<void> {
  const sessionsRes = await fetch(`${API_BASE_URL}/sessions`)
  if (!sessionsRes.ok) {
    throw new Error(`Failed to fetch sessions: ${sessionsRes.status}`)
  }
  const { sessions } = await sessionsRes.json()

  for (const session of sessions) {
    const deleteRes = await fetch(`${API_BASE_URL}/sessions/${session.id}`, {
      method: "DELETE",
    })
    if (!deleteRes.ok) {
      console.warn(`Failed to delete session ${session.id}`)
    }
  }

  const videosRes = await fetch(`${API_BASE_URL}/videos/cache/clear`, {
    method: "DELETE",
  })
  if (!videosRes.ok) {
    console.warn(`Failed to clear video cache: ${videosRes.status}`)
  }
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/settings/llm-providers`)
    return res.ok
  } catch {
    return false
  }
}

export async function setLLMProvider(providerId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/settings/llm-provider`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_id: providerId }),
  })
  if (!res.ok) {
    throw new Error(`Failed to set provider: ${res.status}`)
  }
}

export async function getAvailableProviders(): Promise<string[]> {
  const res = await fetch(`${API_BASE_URL}/settings/llm-providers`)
  if (!res.ok) {
    throw new Error(`Failed to fetch providers: ${res.status}`)
  }
  const providers = await res.json()
  return providers.map((p: { id: string }) => p.id)
}
