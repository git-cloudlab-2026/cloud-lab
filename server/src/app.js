import cors from "cors";
import express from "express";
import helmet from "helmet";
import { apiRouter } from "./routes/index.js";
import { errorHandler, notFoundHandler } from "./middlewares/error-handler.js";
import { attachCurrentUser } from "./middlewares/auth.js";
import { sessionMiddleware } from "./middlewares/session.js";

export const app = express();

app.use(helmet());
app.use(cors({ credentials: true, origin: true }));
app.use(express.json({ limit: "1mb" }));
app.use(sessionMiddleware());
app.use(attachCurrentUser);

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use("/api/v1", apiRouter);
app.use(notFoundHandler);
app.use(errorHandler);
