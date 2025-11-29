import { test, expect } from "@playwright/test"
import { TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Pattern Analysis", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/")
    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })
  })

  test("can open pattern selector", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const patternButton = videoCard.locator("[data-testid^='pattern-button-']")
    await patternButton.click()

    await expect(page.getByTestId("pattern-selector")).toBeVisible()
    await expect(page.getByTestId("pattern-quick_summary")).toBeVisible()
  })

  test("can apply quick_summary pattern", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const patternButton = videoCard.locator("[data-testid^='pattern-button-']")
    await patternButton.click()

    await page.getByTestId("pattern-quick_summary").click()

    await expect(page.getByTestId("pattern-result")).toBeVisible({
      timeout: TIMEOUTS.patternAnalysis,
    })
    await expect(page.getByTestId("pattern-result-title")).toContainText("Quick Summary")
    await expect(page.getByTestId("pattern-result-content")).toBeVisible()

    const content = await page.getByTestId("pattern-result-content").textContent()
    expect(content).toBeTruthy()
    expect(content!.length).toBeGreaterThan(50)
  })

  test("pattern result shows model attribution", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const patternButton = videoCard.locator("[data-testid^='pattern-button-']")
    await patternButton.click()

    await page.getByTestId("pattern-quick_summary").click()

    await expect(page.getByTestId("pattern-result")).toBeVisible({
      timeout: TIMEOUTS.patternAnalysis,
    })
    await expect(page.getByTestId("pattern-result-model")).toBeVisible()
    await expect(page.getByTestId("pattern-result-model")).toContainText("Generated with")
  })

  test("can close pattern result", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const patternButton = videoCard.locator("[data-testid^='pattern-button-']")
    await patternButton.click()

    await page.getByTestId("pattern-quick_summary").click()

    await expect(page.getByTestId("pattern-result")).toBeVisible({
      timeout: TIMEOUTS.patternAnalysis,
    })

    await page.getByTestId("pattern-result-close").click()

    await expect(page.getByTestId("pattern-result")).not.toBeVisible()
  })

  test("can close pattern selector without selecting", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const patternButton = videoCard.locator("[data-testid^='pattern-button-']")
    await patternButton.click()

    await expect(page.getByTestId("pattern-selector")).toBeVisible()

    await page.getByTestId("pattern-selector-close").click()

    await expect(page.getByTestId("pattern-selector")).not.toBeVisible()
  })
})
