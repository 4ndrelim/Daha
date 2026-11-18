import Link from "next/link";
import { ChevronRight } from "lucide-react";

const OPTIONS = [
  { href: "/add/scan", emoji: "📸", title: "Snap your stuff", body: "Take a photo. AI lists everything in it, you pick what to share.", primary: true },
  { href: "/add/item", emoji: "📝", title: "List one item", body: "Add a single thing by hand." },
  { href: "/add/request", emoji: "🙋", title: "Ask for something", body: "\"Anyone have a black binder I can borrow Wednesday?\"" },
];

export default function AddPage() {
  return (
    <div className="space-y-3">
      <h1 className="mb-4 text-[22px] leading-7 font-semibold">What do you want to do?</h1>
      {OPTIONS.map((o) => (
        <Link
          key={o.href}
          href={o.href}
          className={
            o.primary
              ? "flex min-h-24 items-center gap-4 rounded-3xl bg-gradient-to-br from-emerald-500 to-teal-700 p-5 text-white shadow-lg shadow-emerald-600/20 active:scale-[0.99]"
              : "flex min-h-24 items-center gap-4 rounded-3xl bg-card p-5 shadow-sm ring-1 ring-border/60 active:bg-muted"
          }
        >
          <span className="text-4xl" aria-hidden>{o.emoji}</span>
          <span className="flex-1">
            <span className="block text-[17px] font-semibold">{o.title}</span>
            <span className={o.primary ? "block text-[14px] text-emerald-50" : "block text-[14px] text-muted-foreground"}>{o.body}</span>
          </span>
          <ChevronRight className="size-5 opacity-70" />
        </Link>
      ))}
    </div>
  );
}
