import { test, expect } from "@playwright/test"
import { TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Add Video", () => {
  test("can add a video and see transcript loaded", async ({ page }) => {
    await page.goto("/")

    await expect(page.getByTestId("url-input")).toBeVisible()

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    await expect(page.getByTestId("task-progress")).toBeVisible({ timeout: 5000 })

    await expect(page.getByTestId("videos-list").locator("li")).toHaveCount(1, {
      timeout: TIMEOUTS.videoProcessing,
    })

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard).toContainText(TEST_VIDEOS.A.title, { timeout: 5000 })

    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })
  })

  test("rejects channel URLs", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill("https://www.youtube.com/@mkbhd")
    await page.getByTestId("add-video-button").click()

    await expect(page.getByTestId("url-error")).toBeVisible()
    await expect(page.getByTestId("url-error")).toContainText("Only single video URLs")
  })

  test("rejects playlist-only URLs", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")
    await page.getByTestId("add-video-button").click()

    await expect(page.getByTestId("url-error")).toBeVisible()
    await expect(page.getByTestId("url-error")).toContainText("Only single video URLs")
  })
})
