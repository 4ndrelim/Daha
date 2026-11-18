import { Suspense } from "react";
import { RequestComposer } from "./request-composer";

export default function AddRequestPage() {
  return (
    <Suspense>
      <RequestComposer />
    </Suspense>
  );
}
