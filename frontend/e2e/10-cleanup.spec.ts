import { expect } from "@playwright/test"
import { test, TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Cleanup Operations", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/")
    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })
  })

  test("can remove video from session", async ({ page }) => {
    await expect(page.getByTestId("videos-list").locator("li")).toHaveCount(1)

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const removeButton = videoCard.locator("[data-testid^='remove-button-']")
    await removeButton.click()

    await page.getByRole("button", { name: "Remove" }).click()

    await expect(page.getByTestId("videos-list")).toContainText("No videos loaded")
  })

  test("can delete session", async ({ page }) => {
    await page.getByTestId("new-session-button").click()

    await expect(page.getByTestId("sessions-list").locator("[data-testid^='session-']")).toHaveCount(2)

    const sessions = page.getByTestId("sessions-list").locator("[data-testid^='session-']")
    const sessionToDelete = sessions.nth(0)

    await sessionToDelete.hover()
    const deleteButton = sessionToDelete.locator("[data-testid^='delete-session-']")

    page.on("dialog", dialog => dialog.accept())

    await deleteButton.click()

    await expect(page.getByTestId("sessions-list").locator("[data-testid^='session-']")).toHaveCount(1)
  })

  test("remove video confirmation can be cancelled", async ({ page }) => {
    const videoCard = page.getByTestId("videos-list").locator("li").first()
    const removeButton = videoCard.locator("[data-testid^='remove-button-']")
    await removeButton.click()

    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByTestId("videos-list").locator("li")).toHaveCount(1)
  })
})
