import { test as setup } from "@playwright/test"
import { clearDatabase, healthCheck } from "./helpers/database"

setup("clear database before tests", async () => {
  const isHealthy = await healthCheck()
  if (!isHealthy) {
    throw new Error(
      "Backend is not running. Start with: docker-compose up -d"
    )
  }

  await clearDatabase()
})
