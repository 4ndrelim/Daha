import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ParsedRequest, ParseRequestBody } from "../types";

export const ai = {
  parseRequest: (body: ParseRequestBody) =>
    call("ai", () => http<ParsedRequest>("POST", "/ai/parse-request", { body }), () => notMocked<ParsedRequest>("ai.parseRequest")),
};
