import { Suspense } from "react";
import { ExploreScreen } from "./explore-screen";

export default function ExplorePage() {
  return (
    <Suspense>
      <ExploreScreen />
    </Suspense>
  );
}
