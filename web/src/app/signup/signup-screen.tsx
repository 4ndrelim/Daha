"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Search } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, getToken } from "@/lib/api";
import { startSession } from "@/lib/auth";
import { meKey } from "@/lib/queries/me";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { ErrorState } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const schema = z.object({
  name: z.string().trim().min(1, "What should people call you?").max(60),
  email: z.string().trim().toLowerCase().email("That doesn't look like an email")
    .refine((e) => e.endsWith("@stanford.edu"), "Use your @stanford.edu email"),
  password: z.string().min(8, "At least 8 characters"),
});
type Values = z.infer<typeof schema>;

const shell = "mx-auto flex min-h-dvh max-w-md flex-col px-4 pt-[calc(2.5rem+env(safe-area-inset-top))] pb-[calc(2rem+env(safe-area-inset-bottom))]";

export function SignupScreen() {
  const params = useSearchParams();
  const step = params.get("step") === "dorm" && getToken() ? "dorm" : "account";
  return step === "dorm" ? <DormStep /> : <AccountStep />;
}

/** Step 1: name, Stanford email, password → account created (no dorm yet; the dorm list needs a login). */
function AccountStep() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const ref = Number(params.get("ref")) || null;

  const { register, handleSubmit, setError, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema) });
  const signup = useMutation({
    mutationFn: (v: Values) => api.auth.signup({ ...v, ref_user_id: ref }),
    onSuccess: (res) => {
      startSession(qc, res);
      const q = new URLSearchParams({ step: "dorm" });
      const dorm = params.get("dorm");
      if (dorm) q.set("dorm", dorm);
      router.replace(`/signup?${q}`);
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) setError("email", { message: "That email already has an account. Log in instead?" });
      else if (e instanceof ApiError && e.status === 400) toast.error(e.detail);
      else toast.error("Couldn't create your account. Try again?");
    },
  });

  return (
    <main className={shell}>
      <p className="text-[28px] leading-none font-extrabold tracking-tight text-primary">daha</p>
      <h1 className="mt-4 text-[22px] leading-7 font-semibold">Join your dorm on DAHA</h1>
      <p className="mt-1 text-muted-foreground">Takes 30 seconds. Then snap your desk and we&apos;ll list what you can share.</p>

      <form onSubmit={handleSubmit((v) => signup.mutate(v))} className="mt-7 space-y-4" noValidate>
        <Field label="Your name" htmlFor="name" error={errors.name?.message}>
          <input id="name" autoComplete="name" placeholder="Sam Lee" className={fieldClass} aria-invalid={!!errors.name} {...register("name")} />
        </Field>
        <Field label="Stanford email" htmlFor="email" error={errors.email?.message} hint="Only @stanford.edu emails can join.">
          <input id="email" type="email" inputMode="email" autoComplete="email" placeholder="you@stanford.edu"
            className={fieldClass} aria-invalid={!!errors.email} {...register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message} hint="At least 8 characters.">
          <input id="password" type="password" autoComplete="new-password" className={fieldClass}
            aria-invalid={!!errors.password} {...register("password")} />
        </Field>
        <PrimaryButton type="submit" loading={signup.isPending}>Next: pick your dorm</PrimaryButton>
      </form>
      <p className="mt-4 text-center text-[15px] text-muted-foreground">
        Already on DAHA? <Link href="/login" className="inline-flex min-h-11 items-center px-1 font-semibold text-primary">Log in</Link>
      </p>
    </main>
  );
}

/** Step 2: searchable dorm picker (preselects ?dorm=<slug> from invite links) → PATCH /me → onboarding. */
function DormStep() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const dorms = useQuery({ queryKey: ["communities", { kind: "dorm" }], queryFn: () => api.communities.list({ kind: "dorm" }) });
  const presetSlug = params.get("dorm");
  const [picked, setPicked] = useState<number | null>(null);
  const preset = dorms.data?.find((d) => d.slug === presetSlug)?.id ?? null;
  const selected = picked ?? preset;

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = (dorms.data ?? []).filter((d) => !needle || d.name.toLowerCase().includes(needle));
    // An invite link's dorm goes first so it's visible without scrolling.
    return preset === null ? list : [...list.filter((d) => d.id === preset), ...list.filter((d) => d.id !== preset)];
  }, [dorms.data, q, preset]);

  const save = useMutation({
    mutationFn: (dormId: number) => api.me.update({ dorm_id: dormId }),
    onSuccess: (me) => {
      qc.setQueryData(meKey, me);
      router.replace("/onboarding");
    },
    onError: () => toast.error("Couldn't save your dorm. Try again?"),
  });

  return (
    <main className={shell}>
      <h1 className="text-[22px] leading-7 font-semibold">Where do you live?</h1>
      <p className="mt-1 text-muted-foreground">You&apos;ll see your dorm&apos;s stuff first. We only ever show your dorm, never your room.</p>

      <div className="relative mt-5">
        <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search dorms" aria-label="Search dorms"
          className={cn(fieldClass, "pl-10")} />
      </div>

      <div className="mt-3 flex-1 space-y-2 pb-24">
        {dorms.isPending && Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-14 rounded-2xl" />)}
        {dorms.isError && <ErrorState onRetry={() => dorms.refetch()} />}
        {filtered.map((d) => {
          const on = d.id === selected;
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => setPicked(d.id)}
              aria-pressed={on}
              className={cn(
                "flex min-h-14 w-full items-center gap-3 rounded-2xl bg-card px-4 text-left ring-1 transition",
                on ? "ring-2 ring-primary" : "ring-border/60 active:bg-muted",
              )}
            >
              <span className="text-xl" aria-hidden>{d.emoji ?? "🏠"}</span>
              <span className="flex-1">
                <span className="block font-medium">{d.name}</span>
                <span className="block text-[13px] text-muted-foreground">{d.id === preset ? "You were invited here · " : ""}{d.member_count} {d.member_count === 1 ? "neighbor" : "neighbors"}</span>
              </span>
              {on && <Check className="size-5 text-primary" />}
            </button>
          );
        })}
        {dorms.data && filtered.length === 0 && <p className="py-6 text-center text-muted-foreground">No dorm called that. Try &quot;Off-campus&quot;?</p>}
      </div>

      <div className="pb-safe fixed inset-x-0 bottom-0 border-t border-border/60 bg-background/95 backdrop-blur">
        <div className="mx-auto max-w-md px-4 py-3">
          <PrimaryButton type="button" disabled={selected === null} loading={save.isPending} onClick={() => selected !== null && save.mutate(selected)}>
            Continue
          </PrimaryButton>
        </div>
      </div>
    </main>
  );
}
