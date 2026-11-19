"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { AuthResponse } from "@/lib/api/types";
import { safeNext, startSession } from "@/lib/auth";
import { BrandLogo } from "@/components/daha/brand-logo";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { UserAvatar } from "@/components/daha/user-avatar";
import { Skeleton } from "@/components/ui/skeleton";

const schema = z.object({
  email: z.string().trim().min(1, "Enter your email").email("That doesn't look like an email"),
  password: z.string().min(1, "Enter your password"),
});
type Values = z.infer<typeof schema>;

const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export function LoginScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const qc = useQueryClient();

  const onAuthed = (res: AuthResponse) => {
    startSession(qc, res);
    router.replace(next);
  };

  const { register, handleSubmit, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema) });
  const login = useMutation({
    mutationFn: (v: Values) => api.auth.login(v),
    onSuccess: onAuthed,
    onError: (e) => toast.error(e instanceof ApiError && e.status === 401 ? "Wrong email or password." : "Couldn't log in. Try again?"),
  });

  const demoUsers = useQuery({ queryKey: ["demo-users"], queryFn: () => api.auth.demoUsers(), enabled: DEMO });
  const demoLogin = useMutation({
    mutationFn: (userId: number) => api.auth.demoLogin({ user_id: userId }),
    onSuccess: onAuthed,
    onError: () => toast.error("Demo login didn't work. Is the backend running?"),
  });

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col px-4 pt-[calc(3rem+env(safe-area-inset-top))] pb-[calc(2rem+env(safe-area-inset-bottom))]">
      <BrandLogo />
      <h1 className="mt-5 text-[22px] leading-7 font-semibold">Borrow it from down the hall.</h1>
      <p className="mt-1 text-muted-foreground">Lend, borrow, give away and swap with people in your dorm.</p>

      <form onSubmit={handleSubmit((v) => login.mutate(v))} className="mt-8 space-y-4" noValidate>
        <Field label="Email" htmlFor="email" error={errors.email?.message}>
          <input id="email" type="email" autoComplete="email" inputMode="email" placeholder="you@stanford.edu"
            className={fieldClass} aria-invalid={!!errors.email} {...register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message}>
          <input id="password" type="password" autoComplete="current-password" className={fieldClass}
            aria-invalid={!!errors.password} {...register("password")} />
        </Field>
        <PrimaryButton type="submit" loading={login.isPending}>Log in</PrimaryButton>
      </form>

      <p className="mt-4 text-center text-[15px] text-muted-foreground">
        New here?{" "}
        <Link href={`/signup${next !== "/home" ? `?next=${encodeURIComponent(next)}` : ""}`} className="inline-flex min-h-11 items-center font-semibold text-primary">
          Make an account
        </Link>
      </p>

      {DEMO && (
        <section className="mt-10">
          <h2 className="text-[13px] font-semibold tracking-wide text-muted-foreground uppercase">Try a demo account</h2>
          <div className="mt-2 overflow-hidden rounded-2xl bg-card ring-1 ring-border/60">
            {demoUsers.isPending &&
              Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="m-3 h-10 rounded-xl" />)}
            {demoUsers.isError && <p className="p-4 text-[13px] text-muted-foreground">Demo accounts aren&apos;t available right now.</p>}
            {demoUsers.data?.slice(0, 8).map((u) => (
              <button
                key={u.id}
                type="button"
                disabled={demoLogin.isPending}
                onClick={() => demoLogin.mutate(u.id)}
                className="flex min-h-14 w-full items-center gap-3 border-b border-border/60 px-3.5 py-2 text-left last:border-b-0 active:bg-muted disabled:opacity-60"
              >
                <UserAvatar user={u} className="size-9" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{u.name}</span>
                  <span className="block truncate text-[13px] text-muted-foreground">{u.dorm_name ?? "No dorm"} · {u.level_name}</span>
                </span>
                <span className="text-[13px] font-semibold text-primary">Log in</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
