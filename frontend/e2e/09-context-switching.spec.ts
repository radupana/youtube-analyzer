import { expect } from "@playwright/test"
import { test, TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Context Switching Between Sessions", () => {
  test("chat context is isolated between sessions", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    let videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("url-input").fill(TEST_VIDEOS.B.url)
    await page.getByTestId("add-video-button").click()

    await expect(page.getByTestId("videos-list").locator("li")).toHaveCount(2, {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("chat-input").fill("What videos do I have loaded?")
    await page.getByTestId("chat-send-button").click()

    await expect(page.getByTestId("chat-message-assistant-1")).toBeVisible({
      timeout: TIMEOUTS.chatResponse,
    })

    const session1Response = await page.getByTestId("chat-message-assistant-1").textContent()

    await page.getByTestId("new-session-button").click()
    await page.waitForTimeout(500)

    await page.getByTestId("url-input").fill(TEST_VIDEOS.C.url)
    await page.getByTestId("add-video-button").click()

    videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("chat-input").fill("What videos do I have loaded?")
    await page.getByTestId("chat-send-button").click()

    await expect(page.getByTestId("chat-message-assistant-1")).toBeVisible({
      timeout: TIMEOUTS.chatResponse,
    })

    const session2Response = await page.getByTestId("chat-message-assistant-1").textContent()

    expect(session1Response).toBeTruthy()
    expect(session2Response).toBeTruthy()

    const session1ContainsVideoC = session1Response!.toLowerCase().includes("villain") ||
                                    session1Response!.toLowerCase().includes("actress") ||
                                    session1Response!.toLowerCase().includes("cinema")
    expect(session1ContainsVideoC).toBe(false)

    const session2ContainsVideoA = session2Response!.toLowerCase().includes("2 set") ||
                                    session2Response!.toLowerCase().includes("two set") ||
                                    session2Response!.toLowerCase().includes("connor")
    const session2ContainsVideoB = session2Response!.toLowerCase().includes("habit") ||
                                    session2Response!.toLowerCase().includes("ted")
    expect(session2ContainsVideoA || session2ContainsVideoB).toBe(false)
  })

  test("switching back to session preserves chat history", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })

    await page.getByTestId("chat-input").fill("This is a test message in session 1")
    await page.getByTestId("chat-send-button").click()

    await expect(page.getByTestId("chat-message-assistant-1")).toBeVisible({
      timeout: TIMEOUTS.chatResponse,
    })

    await page.getByTestId("new-session-button").click()
    await page.waitForTimeout(500)

    await expect(page.getByTestId("chat-messages")).not.toContainText("This is a test message in session 1")

    const sessions = page.getByTestId("sessions-list").locator("[data-testid^='session-']")
    await sessions.nth(1).click()

    await expect(page.getByTestId("chat-messages")).toContainText("This is a test message in session 1")
  })
})
