import { test as base } from "@playwright/test"
import { clearDatabase } from "./database"

// Extended test fixture that clears database before each test
export const test = base.extend({})

// Hook to clear database before each test for isolation
test.beforeEach(async () => {
  await clearDatabase()
})

export const TEST_VIDEOS = {
  A: {
    url: "https://www.youtube.com/watch?v=pDI39YKFSTY",
    title: "Why Everyone is Switching to the 2 Set Method",
    channel: "Connor",
    transcriptPhrase: "when you know you only have two sets, you can go all in",
  },
  B: {
    url: "https://www.youtube.com/watch?v=-moW9jvvMr4",
    title: "A Simple Way to Break a Bad Habit",
    channel: "TED",
    transcriptPhrase: "In fact, we even told them to smoke",
  },
  C: {
    url: "https://www.youtube.com/watch?v=c4e9rQAKQSs",
    title: "When an actress plays the villain too well",
    channel: "Via Cinema",
    transcriptPhrase: "he says the exact same lines",
  },
} as const

export const TIMEOUTS = {
  videoProcessing: 60_000,
  chatResponse: 30_000,
  patternAnalysis: 60_000,
} as const

export const API_BASE_URL = "http://localhost:8000/api/v1"
