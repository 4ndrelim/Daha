"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Camera, Compass, House, Plus, User, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/home", label: "Home", icon: House },
  { href: "/explore", label: "Explore", icon: Compass },
  { href: "/add", label: "Add", icon: Camera },
  { href: "/communities", label: "Communities", icon: Users },
  { href: "/profile", label: "Profile", icon: User },
] as const;

export function BottomNav() {
  const pathname = usePathname();
  // Inside a chat the composer takes the bottom of the screen.
  if (/^\/messages\/\d+/.test(pathname)) return null;
  return (
    <nav className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-card/95 backdrop-blur">
      <ul className="mx-auto flex h-16 max-w-md items-stretch justify-around px-2">
        {tabs.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          if (href === "/add") {
            return (
              <li key={href} className="flex items-start justify-center">
                <Link
                  href={href}
                  aria-label="Add: snap, list or ask"
                  className="relative -mt-5 flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 ring-4 ring-background transition active:scale-95"
                >
                  <Camera className="size-6" />
                  <span className="absolute right-2.5 bottom-2.5 flex size-4 items-center justify-center rounded-full bg-points text-foreground">
                    <Plus className="size-3" strokeWidth={3} />
                  </span>
                </Link>
              </li>
            );
          }
          return (
            <li key={href} className="flex flex-1">
              <Link
                href={href}
                className={cn(
                  "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <Icon className="size-[22px]" strokeWidth={active ? 2.4 : 2} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
