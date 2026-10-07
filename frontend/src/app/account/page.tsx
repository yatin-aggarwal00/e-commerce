"use client";

import { useStore } from "@/context/StoreProvider";
import { formatDate } from "@/lib/format";

export default function ProfilePage() {
  const { user } = useStore();
  if (!user) return null;

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Profile</h1>
      <dl className="card space-y-3 p-6 text-sm">
        <Row label="Name" value={user.full_name || "—"} />
        <Row label="Email" value={user.email} />
        <Row label="Phone" value={user.phone_number || "—"} />
        <Row label="Member since" value={formatDate(user.created_at)} />
        <Row label="Role" value={user.is_admin ? "Administrator" : "Customer"} />
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-brand-50 pb-2 last:border-0">
      <dt className="text-brand-400">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
