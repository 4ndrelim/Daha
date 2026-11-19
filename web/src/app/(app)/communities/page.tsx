"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Community, GroupType } from "@/lib/api/types";
import { useJoin } from "@/lib/queries/communities";
import { plural } from "@/lib/format";
import { ChoicePills } from "@/components/daha/choice-pills";
import { CommunityRow } from "@/components/daha/community-row";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { EmptyState, ErrorState, SectionHeader } from "@/components/daha/states";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const GROUP_TYPES: { value: GroupType; label: string; emoji: string }[] = [
  { value: "club", label: "Club", emoji: "🎯" }, { value: "class", label: "Class", emoji: "📖" },
  { value: "research", label: "Lab", emoji: "🔬" }, { value: "team", label: "Team", emoji: "🚀" },
  { value: "org", label: "Org", emoji: "🏛️" }, { value: "other", label: "Other", emoji: "👥" },
];

function CreateGroupSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<GroupType>("club");
  const [isPrivate, setPrivate] = useState(false);
  const [created, setCreated] = useState<Community | null>(null);
  const create = useMutation({
    mutationFn: () => api.communities.create({
      name: name.trim(), description: description.trim() || null, group_type: type, is_private: isPrivate,
      emoji: GROUP_TYPES.find((g) => g.value === type)?.emoji ?? null,
    }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["communities"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      if (c.join_code) setCreated(c);
      else { onOpenChange(false); toast.success(`${c.name} is ready!`); router.push(`/communities/${c.slug}`); }
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't create the group."),
  });
  return (
    <Sheet open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setCreated(null); }}>
      <SheetContent side="bottom" className="mx-auto max-h-[90dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader><SheetTitle className="text-[17px]">{created ? "Your group is ready 🎉" : "Start a group"}</SheetTitle></SheetHeader>
        {created ? (
          <div className="space-y-4 px-4 text-center">
            <p className="text-muted-foreground">It&apos;s private. Share this code so people can join:</p>
            <p className="rounded-2xl bg-primary-soft py-4 font-mono text-3xl font-bold tracking-[0.3em] text-accent-foreground select-all">{created.join_code}</p>
            <PrimaryButton type="button" onClick={() => { onOpenChange(false); router.push(`/communities/${created.slug}`); }}>Go to {created.name}</PrimaryButton>
          </div>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }} className="space-y-4 px-4">
            <Field label="Name" htmlFor="g-name">
              <input id="g-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. CS 161 study group" className={fieldClass} maxLength={80} />
            </Field>
            <ChoicePills<GroupType> label="Type" value={type} onChange={setType} options={GROUP_TYPES.map((g) => ({ value: g.value, label: `${g.emoji} ${g.label}` }))} />
            <Field label="What's it for? (optional)" htmlFor="g-desc">
              <textarea id="g-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className={cn(fieldClass, "h-auto py-3")} maxLength={300} />
            </Field>
            <label className="flex min-h-12 items-center justify-between gap-3">
              <span><span className="block font-medium">Private</span><span className="block text-[13px] text-muted-foreground">People need a code to join</span></span>
              <Switch checked={isPrivate} onCheckedChange={setPrivate} />
            </label>
            <PrimaryButton type="submit" disabled={!name.trim()} loading={create.isPending}>Create group</PrimaryButton>
          </form>
        )}
      </SheetContent>
    </Sheet>
  );
}

function JoinButton({ c }: { c: Community }) {
  const router = useRouter();
  const [ask, setAsk] = useState(false);
  const [code, setCode] = useState("");
  const join = useJoin((joined) => { setAsk(false); router.push(`/communities/${joined.slug}`); });
  return (
    <>
      <button type="button" disabled={join.isPending}
        onClick={() => (c.is_private ? setAsk(true) : join.mutate({ id: c.id }))}
        className="h-10 shrink-0 rounded-full bg-primary-soft px-4 text-[14px] font-semibold text-accent-foreground disabled:opacity-60">
        {c.is_private ? "Have a code?" : "Join"}
      </button>
      {c.is_private && (
        <Dialog open={ask} onOpenChange={setAsk}>
          <DialogContent className="max-w-sm rounded-3xl">
            <DialogHeader>
              <DialogTitle>Join {c.name}</DialogTitle>
              <DialogDescription>It&apos;s private. Ask a member for the 6-character code.</DialogDescription>
            </DialogHeader>
            <form onSubmit={(e) => { e.preventDefault(); if (code.trim()) join.mutate({ id: c.id, code: code.trim().toUpperCase() }); }} className="space-y-3">
              <input value={code} onChange={(e) => setCode(e.target.value)} autoCapitalize="characters" autoComplete="off" maxLength={12}
                placeholder="ABC123" aria-label="Join code" className={cn(fieldClass, "text-center font-mono text-xl tracking-[0.25em] uppercase")} />
              <PrimaryButton type="submit" disabled={!code.trim()} loading={join.isPending}>Join</PrimaryButton>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}

export default function CommunitiesPage() {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [creating, setCreating] = useState(false);
  useEffect(() => { const t = setTimeout(() => setDebounced(q.trim()), 300); return () => clearTimeout(t); }, [q]);

  const mine = useQuery({ queryKey: ["communities", { mine: true }], queryFn: () => api.communities.list({ mine: true }) });
  const discover = useQuery({
    queryKey: ["communities", { kind: "group", q: debounced }],
    queryFn: () => api.communities.list({ kind: "group", q: debounced || undefined }),
  });
  const dorm = mine.data?.find((c) => c.kind === "dorm");
  const campus = mine.data?.find((c) => c.kind === "campus");
  const groups = mine.data?.filter((c) => c.kind === "group") ?? [];
  const others = discover.data?.filter((c) => !c.is_member) ?? [];

  return (
    <div className="space-y-7">
      <h1 className="text-[22px] leading-7 font-semibold">Communities</h1>

      {mine.isError && <ErrorState onRetry={() => mine.refetch()} />}
      {mine.isPending && <Skeleton className="h-32 rounded-3xl" />}
      {dorm && (
        <Link href={`/communities/${dorm.slug}`} className="block rounded-3xl bg-gradient-to-br from-brand-500 to-brand-deep p-5 text-white shadow-lg shadow-brand-600/20 active:scale-[0.99]">
          <p className="text-[13px] font-semibold tracking-wide text-brand-100 uppercase">Your dorm</p>
          <p className="mt-1 flex items-center gap-2 text-[22px] font-semibold"><span aria-hidden>{dorm.emoji ?? "🏠"}</span> {dorm.name}</p>
          <p className="mt-1 text-brand-50">{plural(dorm.member_count, "neighbor")} · {plural(dorm.item_count, "thing")} to share · {plural(dorm.open_request_count, "open ask")}</p>
          <span className="mt-4 inline-flex h-10 items-center gap-1 rounded-full bg-white/95 px-4 text-[14px] font-semibold text-brand-700">Open channel <ChevronRight className="size-4" /></span>
        </Link>
      )}
      {mine.data && !dorm && (
        <EmptyState emoji="🏠" title="You haven't picked a dorm" body="Pick one in your profile to see your neighbors' stuff first." actionLabel="Go to profile" actionHref="/profile" />
      )}
      {campus && <CommunityRow c={campus} />}

      <section>
        <SectionHeader title="Your groups" action={
          <button type="button" onClick={() => setCreating(true)} className="flex h-10 items-center gap-1 rounded-full px-3 text-[14px] font-semibold text-primary active:bg-muted">
            <Plus className="size-4" /> New group
          </button>
        } />
        {mine.data && groups.length === 0 && <p className="text-[14px] text-muted-foreground">Clubs, classes, labs, teams: join one below or start your own.</p>}
        <div className="space-y-2">{groups.map((c) => <CommunityRow key={c.id} c={c} />)}</div>
      </section>

      <section>
        <SectionHeader title="Discover groups" />
        <div className="relative mb-3">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search groups" aria-label="Search groups" className={cn(fieldClass, "pl-10")} />
        </div>
        {discover.isPending && <div className="space-y-2"><Skeleton className="h-16 rounded-2xl" /><Skeleton className="h-16 rounded-2xl" /></div>}
        {discover.isError && <ErrorState onRetry={() => discover.refetch()} />}
        {discover.data && others.length === 0 && (
          <p className="rounded-2xl border border-dashed border-border px-4 py-5 text-center text-[14px] text-muted-foreground">
            {debounced ? `No group called "${debounced}". Start it?` : "You're in every group. Nice."}
          </p>
        )}
        <div className="space-y-2">{others.map((c) => <CommunityRow key={c.id} c={c} action={<JoinButton c={c} />} />)}</div>
      </section>

      <CreateGroupSheet open={creating} onOpenChange={setCreating} />
    </div>
  );
}
