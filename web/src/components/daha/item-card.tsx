import Link from "next/link";
import type { ItemCard as ItemCardT } from "@/lib/api/types";
import { AvailabilityLine, DistanceChip, StatusBadge, TxTypeChip, ValueChips } from "./chips";
import { ItemThumb } from "./item-thumb";
import { UserAvatar } from "./user-avatar";
import { cn } from "@/lib/utils";
import { VALUE_EXCHANGE, worthLabel } from "@/lib/value";

export function ItemCard({ item, className, onClick }: { item: ItemCardT; className?: string; onClick?: () => void }) {
  return (
    <Link
      href={`/items/${item.id}`}
      onClick={onClick}
      className={cn("group block overflow-hidden rounded-2xl bg-card shadow-sm ring-1 ring-border/60 transition active:scale-[0.98]", className)}
    >
      <ItemThumb url={item.thumbnail_url} category={item.category} />
      <div className="space-y-1.5 p-2.5">
        {/* Value exchange: the value comes first, before the title. */}
        {VALUE_EXCHANGE && <ValueChips value={item.value_usd} />}
        <p className="line-clamp-2 text-[15px] leading-5 font-medium">
          {item.quantity > 1 && <span className="text-muted-foreground">{item.quantity}× </span>}
          {item.name}
        </p>
        {!VALUE_EXCHANGE && item.value_usd != null && <p className="truncate text-[12px] text-muted-foreground">{worthLabel(item.value_usd)}</p>}
        <div className="flex flex-wrap items-center gap-1">
          <TxTypeChip type={item.transaction_type} />
          {item.status !== "available" && <StatusBadge status={item.status} />}
        </div>
        <AvailabilityLine item={item} />
        <div className="flex items-center justify-between gap-1">
          <DistanceChip min={item.distance_min} label={item.same_dorm ? item.owner.dorm_name?.split(" ")[0] ?? undefined : item.community_label} className="min-w-0 truncate" />
          <UserAvatar user={item.owner} className="size-6 shrink-0" />
        </div>
      </div>
    </Link>
  );
}
