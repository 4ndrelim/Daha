"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { firstName } from "@/lib/format";
import { useMe } from "@/lib/queries/me";
import { BackButton } from "@/components/daha/back-button";
import { ItemCard } from "@/components/daha/item-card";
import { ProfileHeader } from "@/components/daha/profile-header";
import { ReviewList } from "@/components/daha/review-list";
import { EmptyState, ErrorState, ItemGridSkeleton, SectionHeader } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";

export default function PublicProfilePage() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const router = useRouter();
  const { data: me } = useMe();
  useEffect(() => { if (me && me.id === userId) router.replace("/profile"); }, [me, userId, router]);

  const user = useQuery({ queryKey: ["user", userId], queryFn: () => api.users.get(userId) });
  const items = useQuery({ queryKey: ["user-items", userId], queryFn: () => api.users.items(userId, { limit: 50 }) });
  const reviews = useQuery({ queryKey: ["reviews", userId], queryFn: () => api.users.reviews(userId) });
  const message = useMutation({
    mutationFn: () => api.conversations.direct({ user_id: userId }),
    onSuccess: (c) => router.push(`/messages/${c.id}`),
    onError: () => toast.error("Couldn't open the chat."),
  });

  if (user.isPending) return <Skeleton className="h-64 rounded-3xl" />;
  if (user.isError) {
    return user.error instanceof ApiError && user.error.status === 404
      ? <EmptyState emoji="🔍" title="No one here" actionLabel="Back home" actionHref="/home" />
      : <ErrorState onRetry={() => user.refetch()} />;
  }
  const u = user.data;
  return (
    <div className="space-y-6">
      <BackButton className="-mt-2 -mb-3" />
      <ProfileHeader user={u} />
      <button type="button" onClick={() => message.mutate()} disabled={message.isPending}
        className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-primary font-semibold text-primary-foreground disabled:opacity-60">
        <MessageCircle className="size-5" /> Message {firstName(u.name)}
      </button>
      <section>
        <SectionHeader title={`${firstName(u.name)}'s stuff`} />
        {items.isPending && <ItemGridSkeleton />}
        {items.isError && <ErrorState onRetry={() => items.refetch()} />}
        {items.data?.items.length === 0 && <EmptyState emoji="📦" title="Nothing you can see yet" body="They might share with their dorm or groups only." />}
        <div className="grid grid-cols-2 gap-3">{items.data?.items.map((i) => <ItemCard key={i.id} item={i} />)}</div>
      </section>
      <section>
        <SectionHeader title="Reviews" />
        {reviews.isPending && <Skeleton className="h-20 rounded-2xl" />}
        {reviews.data && <ReviewList reviews={reviews.data} emptyBody={`${firstName(u.name)} hasn't been reviewed yet.`} />}
      </section>
    </div>
  );
}
