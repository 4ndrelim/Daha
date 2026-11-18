import { Suspense } from "react";
import { RequestScreen } from "./request-screen";

export default function RequestPage() {
  return (
    <Suspense>
      <RequestScreen />
    </Suspense>
  );
}
