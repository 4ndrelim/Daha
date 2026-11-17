"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

/** Share links: /r/<id> → /requests/<id> (the app layout handles login first). */
export default function ShareRedirect() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/requests/${id}`);
  }, [id, router]);
  return null;
}
