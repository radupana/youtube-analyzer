import { expect } from "@playwright/test"
import { test, TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Multi-Video Session", () => {
  test("can add multiple videos to same session", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const firstVideoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(firstVideoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("url-input").fill(TEST_VIDEOS.B.url)
    await page.getByTestId("add-video-button").click()

    await expect(page.getByTestId("videos-list").locator("li")).toHaveCount(2, {
      timeout: TIMEOUTS.videoProcessing,
    })

    await expect(page.getByTestId("videos-list")).toContainText(TEST_VIDEOS.A.title)
    await expect(page.getByTestId("videos-list")).toContainText(TEST_VIDEOS.B.title)
  })

  test("both videos show ready status", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const firstVideoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(firstVideoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("url-input").fill(TEST_VIDEOS.B.url)
    await page.getByTestId("add-video-button").click()

    await expect(page.getByTestId("videos-list").locator("li")).toHaveCount(2, {
      timeout: TIMEOUTS.videoProcessing,
    })

    const videoCards = page.getByTestId("videos-list").locator("li")
    await expect(videoCards.nth(0).locator("[data-testid^='video-status-']")).toContainText("Ready")
    await expect(videoCards.nth(1).locator("[data-testid^='video-status-']")).toContainText("Ready")
  })
})
