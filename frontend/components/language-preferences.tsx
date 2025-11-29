"use client"

import { useState } from "react"
import { Languages, X, GripVertical } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { LanguagePreferences } from "@/lib/useLanguagePreferences"

// Common language codes with display names
const AVAILABLE_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "pt", name: "Portuguese" },
  { code: "it", name: "Italian" },
  { code: "nl", name: "Dutch" },
  { code: "pl", name: "Polish" },
  { code: "ru", name: "Russian" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "zh", name: "Chinese" },
  { code: "ar", name: "Arabic" },
  { code: "hi", name: "Hindi" },
  { code: "tr", name: "Turkish" },
  { code: "vi", name: "Vietnamese" },
  { code: "th", name: "Thai" },
  { code: "id", name: "Indonesian" },
  { code: "sv", name: "Swedish" },
  { code: "da", name: "Danish" },
  { code: "no", name: "Norwegian" },
  { code: "fi", name: "Finnish" },
  { code: "cs", name: "Czech" },
  { code: "uk", name: "Ukrainian" },
]

interface LanguagePreferencesDialogProps {
  preferences: LanguagePreferences
  onUpdate: (prefs: Partial<LanguagePreferences>) => void
}

export function LanguagePreferencesDialog({
  preferences,
  onUpdate,
}: LanguagePreferencesDialogProps) {
  const [open, setOpen] = useState(false)
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(
    preferences.preferredLanguages
  )
  const [preferManual, setPreferManual] = useState(preferences.preferManual)
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)

  const handleOpen = (isOpen: boolean) => {
    if (isOpen) {
      setSelectedLanguages(preferences.preferredLanguages)
      setPreferManual(preferences.preferManual)
    }
    setOpen(isOpen)
  }

  const handleSave = () => {
    onUpdate({
      preferredLanguages: selectedLanguages,
      preferManual,
    })
    setOpen(false)
  }

  const toggleLanguage = (code: string) => {
    if (selectedLanguages.includes(code)) {
      setSelectedLanguages(selectedLanguages.filter((c) => c !== code))
    } else {
      setSelectedLanguages([...selectedLanguages, code])
    }
  }

  const removeLanguage = (code: string) => {
    setSelectedLanguages(selectedLanguages.filter((c) => c !== code))
  }

  const moveLanguage = (fromIndex: number, toIndex: number) => {
    const newList = [...selectedLanguages]
    const [moved] = newList.splice(fromIndex, 1)
    newList.splice(toIndex, 0, moved)
    setSelectedLanguages(newList)
  }

  const handleDragStart = (index: number) => {
    setDraggedIndex(index)
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    if (draggedIndex !== null && draggedIndex !== index) {
      moveLanguage(draggedIndex, index)
      setDraggedIndex(index)
    }
  }

  const handleDragEnd = () => {
    setDraggedIndex(null)
  }

  const getLanguageName = (code: string) => {
    return AVAILABLE_LANGUAGES.find((l) => l.code === code)?.name || code.toUpperCase()
  }

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Languages className="h-4 w-4" />
          <span className="hidden sm:inline">Languages</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Transcript Language Preferences</DialogTitle>
          <DialogDescription>
            Choose your preferred languages for YouTube captions. Drag to reorder priority.
            These preferences only apply when captions are available; Whisper fallback auto-detects the spoken language.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="prefer-manual" className="text-sm">
              Prefer manual captions over auto-generated
            </Label>
            <Switch
              id="prefer-manual"
              checked={preferManual}
              onCheckedChange={setPreferManual}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium">
              Selected Languages (drag to reorder)
            </Label>
            {selectedLanguages.length === 0 ? (
              <p className="text-sm text-muted-foreground py-2">
                No languages selected. Any available transcript will be used.
              </p>
            ) : (
              <div className="space-y-1">
                {selectedLanguages.map((code, index) => (
                  <div
                    key={code}
                    draggable
                    onDragStart={() => handleDragStart(index)}
                    onDragOver={(e) => handleDragOver(e, index)}
                    onDragEnd={handleDragEnd}
                    className={`flex items-center gap-2 p-2 bg-muted rounded cursor-move ${
                      draggedIndex === index ? "opacity-50" : ""
                    }`}
                  >
                    <GripVertical className="h-4 w-4 text-muted-foreground" />
                    <span className="text-xs font-mono bg-background px-1 rounded">
                      {index + 1}
                    </span>
                    <span className="flex-1 text-sm">{getLanguageName(code)}</span>
                    <span className="text-xs text-muted-foreground">{code}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => removeLanguage(code)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium">Add Languages</Label>
            <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto">
              {AVAILABLE_LANGUAGES.filter(
                (l) => !selectedLanguages.includes(l.code)
              ).map((lang) => (
                <Button
                  key={lang.code}
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => toggleLanguage(lang.code)}
                >
                  {lang.name}
                </Button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Preferences</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
