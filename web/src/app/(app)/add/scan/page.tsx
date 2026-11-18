import { ScanFlow } from "@/components/scan/scan-flow";

export default function ScanPage() {
  return (
    <ScanFlow
      mode="add"
      intro={
        <div>
          <h1 className="text-[22px] leading-7 font-semibold">Snap your stuff</h1>
          <p className="mt-1 text-muted-foreground">We&apos;ll spot what&apos;s in the photo and list it. You pick what to share.</p>
        </div>
      }
    />
  );
}
