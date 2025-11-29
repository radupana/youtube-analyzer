import { test, expect } from "@playwright/test"
import { TEST_VIDEOS, TIMEOUTS } from "./helpers/fixtures"

test.describe("Chat", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/")
    await page.getByTestId("url-input").fill(TEST_VIDEOS.A.url)
    await page.getByTestId("add-video-button").click()

    const videoCard = page.getByTestId("videos-list").locator("li").first()
    await expect(videoCard.locator("[data-testid^='video-status-']")).toContainText("Ready", {
      timeout: TIMEOUTS.videoProcessing,
    })
  })

  test("can send message and receive response", async ({ page }) => {
    await page.getByTestId("chat-input").fill("What is this video about?")
    await page.getByTestId("chat-send-button").click()

    await expect(page.getByTestId("chat-message-user-0")).toBeVisible()
    await expect(page.getByTestId("chat-message-user-0")).toContainText("What is this video about?")

    await expect(page.getByTestId("chat-message-assistant-1")).toBeVisible({
      timeout: TIMEOUTS.chatResponse,
    })

    const response = await page.getByTestId("chat-message-assistant-1").textContent()
    expect(response).toBeTruthy()
    expect(response!.length).toBeGreaterThan(20)
  })

  test("chat input is cleared after sending", async ({ page }) => {
    await page.getByTestId("chat-input").fill("Test message")
    await page.getByTestId("chat-send-button").click()

    await expect(page.getByTestId("chat-input")).toHaveValue("")
  })

  test("send button is disabled when input is empty", async ({ page }) => {
    await expect(page.getByTestId("chat-input")).toHaveValue("")
    await expect(page.getByTestId("chat-send-button")).toBeDisabled()
  })

  test("can send message with Enter key", async ({ page }) => {
    await page.getByTestId("chat-input").fill("Quick test")
    await page.getByTestId("chat-input").press("Enter")

    await expect(page.getByTestId("chat-message-user-0")).toBeVisible()
  })
})
