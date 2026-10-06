"use client";

import Image from "next/image";
import Link from "next/link";

import { useStore } from "@/context/StoreProvider";
import { formatPrice } from "@/lib/format";

export default function CartPage() {
  const { cart, ready, updateItem, removeItem } = useStore();

  if (!ready) return <p className="text-brand-500">Loading your cart…</p>;

  if (!cart || cart.items.length === 0) {
    return (
      <div className="py-20 text-center">
        <h1 className="text-2xl font-semibold">Your cart is empty</h1>
        <Link href="/products" className="btn-primary mt-6">
          Continue shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <section>
        <h1 className="mb-4 text-2xl font-semibold">Your cart</h1>
        <ul className="divide-y divide-brand-100 rounded-lg border border-brand-100 bg-white">
          {cart.items.map((item) => (
            <li key={item.id} className="flex gap-4 p-4">
              <div className="relative h-20 w-20 flex-none overflow-hidden rounded-md bg-brand-100">
                {item.thumbnail && (
                  <Image src={item.thumbnail} alt={item.product_name} fill sizes="80px" className="object-cover" />
                )}
              </div>
              <div className="flex-1">
                <Link href={`/products/${item.product_slug}`} className="font-medium hover:underline">
                  {item.product_name}
                </Link>
                <p className="text-xs text-brand-400">{item.variant_name}</p>
                <div className="mt-2 flex items-center gap-3">
                  <input
                    type="number"
                    min={1}
                    max={item.available}
                    value={item.quantity}
                    onChange={(e) => updateItem(item.id, Math.max(1, Number(e.target.value)))}
                    className="input w-20"
                    aria-label={`Quantity for ${item.product_name}`}
                  />
                  <button
                    onClick={() => removeItem(item.id)}
                    className="text-sm text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </div>
              </div>
              <div className="text-right font-medium">
                {formatPrice(item.line_total_cents, item.currency)}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <aside className="card h-fit p-6">
        <h2 className="mb-4 text-lg font-semibold">Summary</h2>
        <div className="flex justify-between text-sm">
          <span>Subtotal</span>
          <span>{formatPrice(cart.subtotal_cents, cart.currency)}</span>
        </div>
        <p className="mt-1 text-xs text-brand-400">Shipping calculated at checkout.</p>
        <Link href="/checkout" className="btn-primary mt-6 w-full">
          Proceed to checkout
        </Link>
      </aside>
    </div>
  );
}
