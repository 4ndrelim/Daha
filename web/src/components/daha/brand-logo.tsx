import Image from "next/image";
import { cn } from "@/lib/utils";

/** The DAHA logo (web/public/brand/daha-logo.png, used as supplied). 661×291 source, shown ~220 px wide. */
export function BrandLogo({ className }: { className?: string }) {
  return (
    <Image src="/brand/daha-logo.png" alt="DAHA" width={220} height={97} priority
      className={cn("mx-auto block h-auto w-[220px] max-w-full", className)} />
  );
}
