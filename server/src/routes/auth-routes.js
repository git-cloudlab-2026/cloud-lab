import { Router } from "express";
import { callback, login, logout, me } from "../controllers/auth-controller.js";
import { asyncHandler } from "../middlewares/async-handler.js";

export const authRouter = Router();

authRouter.get("/login", asyncHandler(login));
authRouter.post("/login", asyncHandler(login));
authRouter.get("/callback", asyncHandler(callback));
authRouter.post("/logout", asyncHandler(logout));
authRouter.get("/me", asyncHandler(me));

