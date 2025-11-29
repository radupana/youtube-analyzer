import { expect } from "@playwright/test"
import { test, TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Transcript", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/")
    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })
  })

  test("can view transcript", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const transcriptButton = videoCard.locator("[data-testid^='transcript-button-']")
    await transcriptButton.click()

    await expect(page.getByTestId("transcript-viewer")).toBeVisible()
    await expect(page.getByTestId("transcript-content")).toBeVisible()
  })

  test("transcript contains expected content", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const transcriptButton = videoCard.locator("[data-testid^='transcript-button-']")
    await transcriptButton.click()

    await expect(page.getByTestId("transcript-content")).toContainText(
      TEST_VIDEOS.A.transcriptPhrase,
      { ignoreCase: true }
    )
  })

  test("can search transcript and find matches", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const transcriptButton = videoCard.locator("[data-testid^='transcript-button-']")
    await transcriptButton.click()

    await page.getByTestId("transcript-search-input").fill("two sets")

    await expect(page.getByTestId("transcript-match-count")).toBeVisible({ timeout: 3000 })
    await expect(page.getByTestId("transcript-match-count")).toContainText("of")
  })

  test("shows no matches for nonsense search", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const transcriptButton = videoCard.locator("[data-testid^='transcript-button-']")
    await transcriptButton.click()

    await page.getByTestId("transcript-search-input").fill("xyzzy12345nonsense")

    await expect(page.getByTestId("transcript-no-matches")).toBeVisible({ timeout: 3000 })
  })

  test("can navigate between search matches", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const transcriptButton = videoCard.locator("[data-testid^='transcript-button-']")
    await transcriptButton.click()

    await page.getByTestId("transcript-search-input").fill("the")

    await expect(page.getByTestId("transcript-match-count")).toBeVisible({ timeout: 3000 })
    const initialCount = await page.getByTestId("transcript-match-count").textContent()

    await page.getByTestId("transcript-next-match").click()
    await page.waitForTimeout(300)

    const afterNextCount = await page.getByTestId("transcript-match-count").textContent()
    expect(initialCount).not.toBe(afterNextCount)
  })

  test("can clear search", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const transcriptButton = videoCard.locator("[data-testid^='transcript-button-']")
    await transcriptButton.click()

    await page.getByTestId("transcript-search-input").fill("test")
    await expect(page.getByTestId("transcript-search-clear")).toBeVisible()

    await page.getByTestId("transcript-search-clear").click()

    await expect(page.getByTestId("transcript-search-input")).toHaveValue("")
  })
})
