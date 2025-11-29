import { test as teardown } from "@playwright/test"
import { clearDatabase } from "./helpers/database"

teardown("clear database after tests", async () => {
  await clearDatabase()
})
