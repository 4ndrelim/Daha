import type { Category } from "@/lib/api/types";
import { categoryInfo } from "@/lib/categories";
import { cn } from "@/lib/utils";

/** Square photo, or a category emoji tile on a soft tint (also shown while the photo loads). */
export function ItemThumb({ url, category, className, emojiClassName }: {
  url: string | null; category: Category; className?: string; emojiClassName?: string;
}) {
  const c = categoryInfo(category);
  return (
    <div className={cn("relative flex aspect-square items-center justify-center overflow-hidden", c.tint, className)}>
      <span className={cn("text-4xl select-none", emojiClassName)} aria-hidden>{c.emoji}</span>
      {url && (
        // eslint-disable-next-line @next/next/no-img-element -- photos come from the backend proxy; no optimizer needed
        <img src={url} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />
      )}
    </div>
  );
}
