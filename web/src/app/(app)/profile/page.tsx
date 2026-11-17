import { PagePlaceholder } from "@/components/layout/page-placeholder";
import { LogoutButton } from "@/components/daha/logout-button";

export default function Page() {
  return (
    <div className="space-y-6">
      <PagePlaceholder title="Profile" note="B5: inventory, requests, activity, reviews, settings." />
      <LogoutButton />
    </div>
  );
}
