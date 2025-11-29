import { expect } from "@playwright/test"
import { test, TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Export Transcript", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/")
    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })
  })

  test("can export transcript as txt", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const exportButton = videoCard.locator("[data-testid^='export-button-']")
    await exportButton.click()

    const downloadPromise = page.waitForEvent("download")
    await page.getByText("Plain Text (.txt)").click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toContain(".txt")
  })

  test("can export transcript as markdown", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const exportButton = videoCard.locator("[data-testid^='export-button-']")
    await exportButton.click()

    const downloadPromise = page.waitForEvent("download")
    await page.getByText("Markdown (.md)").click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toContain(".md")
  })

  test("can export transcript as srt", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const exportButton = videoCard.locator("[data-testid^='export-button-']")
    await exportButton.click()

    const downloadPromise = page.waitForEvent("download")
    await page.getByText("Subtitles (.srt)").click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toContain(".srt")
  })

  test("can export transcript as json", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const exportButton = videoCard.locator("[data-testid^='export-button-']")
    await exportButton.click()

    const downloadPromise = page.waitForEvent("download")
    await page.getByText("JSON (.json)").click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toContain(".json")
  })
})
