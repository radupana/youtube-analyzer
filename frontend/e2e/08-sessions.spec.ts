import { test, expect } from "@playwright/test"
import { TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Session Management", () => {
  test("can create new session", async ({ page }) => {
    await page.goto("/")

    await expect(page.getByTestId("sessions-list").locator("[data-testid^='session-']")).toHaveCount(1)

    await page.getByTestId("new-session-button").click()

    await expect(page.getByTestId("sessions-list").locator("[data-testid^='session-']")).toHaveCount(2)
  })

  test("new session starts with no videos", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("new-session-button").click()

    await expect(page.getByTestId("videos-list")).toContainText("No videos loaded")
  })

  test("can switch between sessions", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("new-session-button").click()
    await expect(page.getByTestId("videos-list")).toContainText("No videos loaded")

    const sessions = page.getByTestId("sessions-list").locator("[data-testid^='session-']")
    await sessions.nth(1).click()

    await expect(page.getByTestId("videos-list")).toContainText(TEST_VIDEOS.A.title)
  })
})
