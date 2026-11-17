import { call, http } from "../client";
import { mockAi } from "../mock/ai";
import type { ParsedRequest, ParseRequestBody } from "../types";

export const ai = {
  parseRequest: (body: ParseRequestBody) =>
    call("ai", () => http<ParsedRequest>("POST", "/ai/parse-request", { body }), () => mockAi.parseRequest(body)),
};
