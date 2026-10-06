"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useStore } from "@/context/StoreProvider";

export function Navbar() {
  const { itemCount, user, logout } = useStore();
  const router = useRouter();
  const [q, setQ] = useState("");

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    router.push(term ? `/products?q=${encodeURIComponent(term)}` : "/products");
  }

  return (
    <header className="sticky top-0 z-30 border-b border-brand-100 bg-brand-50/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Link href="/" className="whitespace-nowrap text-lg font-bold text-brand-800">
          🛋️ Haus<span className="text-brand-500">&amp;</span>Home
        </Link>

        <form onSubmit={onSearch} className="hidden flex-1 md:block">
          <input
            aria-label="Search products"
            className="input"
            placeholder="Search sofas, beds, tables…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </form>

        <nav className="ml-auto flex items-center gap-4 text-sm">
          <Link href="/products" className="hover:text-brand-600">
            Shop
          </Link>
          <Link href="/cart" className="relative hover:text-brand-600">
            Cart
            {itemCount > 0 && (
              <span className="absolute -right-3 -top-2 rounded-full bg-brand-700 px-1.5 text-xs text-white">
                {itemCount}
              </span>
            )}
          </Link>
          {user ? (
            <>
              <Link href="/account" className="hover:text-brand-600">
                Account
              </Link>
              {user.is_admin && (
                <Link href="/admin" className="font-medium text-brand-700 hover:text-brand-900">
                  Admin
                </Link>
              )}
              <button onClick={logout} className="text-brand-500 hover:text-brand-700">
                Sign out
              </button>
            </>
          ) : (
            <Link href="/login" className="hover:text-brand-600">
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
