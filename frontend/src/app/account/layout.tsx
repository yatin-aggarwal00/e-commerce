"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useStore } from "@/context/StoreProvider";

const TABS = [
  ["/account", "Profile"],
  ["/account/orders", "Orders"],
  ["/account/addresses", "Addresses"],
] as const;

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  const { user, ready } = useStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ready && !user) router.replace("/login");
  }, [ready, user, router]);

  if (!ready || !user) return <p className="text-brand-500">Loading…</p>;

  return (
    <div className="grid gap-8 md:grid-cols-[200px_1fr]">
      <aside>
        <h2 className="mb-3 text-lg font-semibold">My account</h2>
        <nav className="flex flex-col gap-1 text-sm">
          {TABS.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className={`rounded px-3 py-2 ${
                pathname === href ? "bg-brand-100 font-medium text-brand-800" : "hover:bg-brand-100"
              }`}
            >
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <section>{children}</section>
    </div>
  );
}
