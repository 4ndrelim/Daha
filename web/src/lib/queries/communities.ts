"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Community, ID } from "@/lib/api/types";
import { invalidatePool } from "@/lib/api/mock/pool";

export function useJoin(onDone?: (c: Community) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, code }: { id: ID; code?: string }) => api.communities.join(id, code ? { join_code: code } : {}),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["communities"] });
      qc.invalidateQueries({ queryKey: ["community"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
      invalidatePool();
      toast.success(`You joined ${c.name}!`);
      onDone?.(c);
    },
    onError: (e) => toast.error(e instanceof ApiError && e.status === 403 ? "That code didn't work." : "Couldn't join. Try again?"),
  });
}

export function useLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (c: Community) => api.communities.leave(c.id).then(() => c),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["communities"] });
      qc.invalidateQueries({ queryKey: ["community"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      invalidatePool();
      toast.success(`You left ${c.name}.`);
    },
    onError: () => toast.error("Couldn't leave. Try again?"),
  });
}
