import { app } from "./app.js";
import { config } from "./config.js";
import { startNotificationJobs } from "./jobs/notificationJobs.js";

app.listen(config.port, () => {
  console.log(`Cloud Lab API listening on http://localhost:${config.port}`);
  startNotificationJobs();
});
