import { call, http } from "../client";
import { notMocked } from "../mock";
import type { AuthResponse, DemoLoginBody, LoginBody, SignupBody, UserRef } from "../types";

export const auth = {
  signup: (body: SignupBody) =>
    call("auth", () => http<AuthResponse>("POST", "/auth/signup", { body }), () => notMocked<AuthResponse>("auth.signup")),
  login: (body: LoginBody) =>
    call("auth", () => http<AuthResponse>("POST", "/auth/login", { body }), () => notMocked<AuthResponse>("auth.login")),
  demoUsers: () =>
    call("auth", () => http<UserRef[]>("GET", "/auth/demo-users"), () => notMocked<UserRef[]>("auth.demoUsers")),
  demoLogin: (body: DemoLoginBody) =>
    call("auth", () => http<AuthResponse>("POST", "/auth/demo-login", { body }), () => notMocked<AuthResponse>("auth.demoLogin")),
};
