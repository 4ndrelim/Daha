export function PagePlaceholder({ title, note }: { title: string; note?: string }) {
  return (
    <div className="space-y-2">
      <h1 className="text-[22px] leading-7 font-semibold">{title}</h1>
      <p className="text-[13px] text-muted-foreground">{note ?? "Coming soon."}</p>
    </div>
  );
}
