import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ConversationSummary, DirectConversationBody, ID, Message, SendMessageBody } from "../types";

export const conversations = {
  list: () =>
    call("conversations", () => http<ConversationSummary[]>("GET", "/conversations"), () => notMocked<ConversationSummary[]>("conversations.list")),
  direct: (body: DirectConversationBody) =>
    call("conversations", () => http<ConversationSummary>("POST", "/conversations", { body }), () => notMocked<ConversationSummary>("conversations.direct")),
  get: (id: ID) =>
    call("conversations", () => http<ConversationSummary>("GET", `/conversations/${id}`), () => notMocked<ConversationSummary>("conversations.get")),
  messages: (id: ID, query: { after_id?: ID; limit?: number } = {}) =>
    call("conversations", () => http<Message[]>("GET", `/conversations/${id}/messages`, { query }), () => notMocked<Message[]>("conversations.messages")),
  send: (id: ID, body: SendMessageBody) =>
    call("conversations", () => http<Message>("POST", `/conversations/${id}/messages`, { body }), () => notMocked<Message>("conversations.send")),
  markRead: (id: ID) =>
    call("conversations", () => http<void>("POST", `/conversations/${id}/read`), () => notMocked<void>("conversations.markRead")),
};
