"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { ID, Transaction, TxAction } from "@/lib/api/types";
import { invalidatePool } from "@/lib/api/mock/pool";

export function useTxAction(onDone?: (tx: Transaction) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: ID; action: TxAction }) => api.transactions.action(id, { action }),
    onSuccess: (tx) => {
      qc.setQueryData(["transaction", tx.id], tx);
      qc.invalidateQueries({ queryKey: ["request"] });
      qc.invalidateQueries({ queryKey: ["item", tx.item.id] });
      qc.invalidateQueries({ queryKey: ["messages", tx.conversation_id] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      invalidatePool();
      onDone?.(tx);
    },
    onError: (e) => toast.error(e instanceof ApiError && e.status === 409 ? "That changed in the meantime. Refreshing." : "Didn't work. Try again?"),
  });
}
