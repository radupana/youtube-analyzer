import { useState, useEffect, useCallback } from "react"
import { fetchTranscriptDefaults } from "./api"

const STORAGE_KEY = "youtube-analyzer-language-preferences"

export interface LanguagePreferences {
  preferredLanguages: string[]
  preferManual: boolean
}

const DEFAULT_PREFERENCES: LanguagePreferences = {
  preferredLanguages: ["en"],
  preferManual: true,
}

export function useLanguagePreferences() {
  const [preferences, setPreferences] = useState<LanguagePreferences>(DEFAULT_PREFERENCES)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const loadPreferences = async () => {
      // First check localStorage
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        try {
          const parsed = JSON.parse(stored) as LanguagePreferences
          setPreferences(parsed)
          setLoaded(true)
          return
        } catch {
          // Invalid JSON, fall through to server defaults
        }
      }

      // No localStorage, load from server defaults
      try {
        const defaults = await fetchTranscriptDefaults()
        const serverPrefs: LanguagePreferences = {
          preferredLanguages: defaults.preferred_languages,
          preferManual: defaults.prefer_manual,
        }
        setPreferences(serverPrefs)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(serverPrefs))
      } catch {
        // Use hardcoded defaults if server fails
        setPreferences(DEFAULT_PREFERENCES)
      }
      setLoaded(true)
    }

    loadPreferences()
  }, [])

  const updatePreferences = useCallback((newPrefs: Partial<LanguagePreferences>) => {
    setPreferences((prev) => {
      const updated = { ...prev, ...newPrefs }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
      return updated
    })
  }, [])

  return { preferences, updatePreferences, loaded }
}
