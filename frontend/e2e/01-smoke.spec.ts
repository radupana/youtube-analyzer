import { expect } from "@playwright/test"
import { test } from "./helpers/fixtures"

test.describe("Smoke Tests", () => {
  test("page loads successfully", async ({ page }) => {
    await page.goto("/")

    await expect(page.getByRole("heading", { name: "YouTube Analyzer" })).toBeVisible()
    await expect(page.getByTestId("session-sidebar")).toBeVisible()
    await expect(page.getByTestId("url-input")).toBeVisible()
    await expect(page.getByTestId("add-video-button")).toBeVisible()
    await expect(page.getByTestId("chat-input")).toBeVisible()
  })

  test("session is auto-created on first load", async ({ page }) => {
    await page.goto("/")

    await expect(page.getByTestId("sessions-list")).toBeVisible()
    const sessions = page.getByTestId("sessions-list").locator("[data-testid^='session-']")
    await expect(sessions).toHaveCount(1, { timeout: 5000 })
  })

  test("provider dropdown is visible when providers exist", async ({ page }) => {
    await page.goto("/")

    await expect(page.getByTestId("provider-dropdown")).toBeVisible({ timeout: 5000 })
  })
})
