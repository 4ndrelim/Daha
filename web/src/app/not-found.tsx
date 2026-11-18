import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-6 text-center">
      <span className="text-5xl" aria-hidden>🧭</span>
      <h1 className="mt-3 text-[22px] font-semibold">Nothing here</h1>
      <p className="mt-1 text-muted-foreground">That page doesn&apos;t exist. Maybe someone down the hall has what you&apos;re looking for?</p>
      <Link href="/home" className="mt-6 flex h-12 items-center rounded-full bg-primary px-6 font-semibold text-primary-foreground">Back to DAHA</Link>
    </main>
  );
}
