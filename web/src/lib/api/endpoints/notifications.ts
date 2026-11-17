import { call, http } from "../client";
import { notMocked } from "../mock";
import type { MarkReadBody, Notification, UnreadCounts } from "../types";

export const notifications = {
  list: (query: { unread_only?: boolean; limit?: number } = {}) =>
    call("notifications", () => http<Notification[]>("GET", "/notifications", { query }), () => notMocked<Notification[]>("notifications.list")),
  unreadCount: () =>
    call("notifications", () => http<UnreadCounts>("GET", "/notifications/unread-count"), () => notMocked<UnreadCounts>("notifications.unreadCount")),
  markRead: (body: MarkReadBody) =>
    call("notifications", () => http<void>("POST", "/notifications/read", { body }), () => notMocked<void>("notifications.markRead")),
};
