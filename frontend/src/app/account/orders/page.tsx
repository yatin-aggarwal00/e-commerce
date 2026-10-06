"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDate, formatPrice, statusClass } from "@/lib/format";
import type { Order } from "@/lib/types";

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);

  useEffect(() => {
    api
      .listOrders()
      .then(setOrders)
      .catch(() => setOrders([]));
  }, []);

  if (orders === null) return <p className="text-brand-500">Loading orders…</p>;

  if (orders.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold">Orders</h1>
        <p className="text-brand-500">
          You have no orders yet.{" "}
          <Link href="/products" className="text-brand-700 hover:underline">
            Start shopping
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Orders</h1>
      <ul className="space-y-4">
        {orders.map((o) => (
          <li key={o.id} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-mono font-medium">{o.order_number}</p>
                <p className="text-xs text-brand-400">{formatDate(o.created_at)}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`badge ${statusClass(o.status)}`}>{o.status}</span>
                <span className="font-semibold">{formatPrice(o.total_cents, o.currency)}</span>
              </div>
            </div>
            <ul className="mt-3 border-t border-brand-50 pt-3 text-sm text-brand-600">
              {o.items.map((i) => (
                <li key={i.id}>
                  {i.product_name} {i.variant_name && `(${i.variant_name})`} × {i.quantity}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
