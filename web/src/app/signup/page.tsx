import { Suspense } from "react";
import { SignupScreen } from "./signup-screen";

export default function SignupPage() {
  return (
    <Suspense>
      <SignupScreen />
    </Suspense>
  );
}
