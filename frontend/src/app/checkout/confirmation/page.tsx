"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatPrice, statusClass } from "@/lib/format";
import type { Order } from "@/lib/types";

function Confirmation() {
  const params = useSearchParams();
  const orderNumber = params.get("order") ?? "";
  const email = params.get("email") ?? undefined;
  const provider = params.get("provider") ?? "";

  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [awaitingWebhook, setAwaitingWebhook] = useState(provider === "stripe");

  const load = useCallback(async (): Promise<Order | null> => {
    if (!orderNumber) return null;
    try {
      const o = await api.getOrder(orderNumber, email);
      setOrder(o);
      return o;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load order");
      return null;
    }
  }, [orderNumber, email]);

  useEffect(() => {
    load();
    // The payment step is done; clear the stashed client secret.
    try {
      sessionStorage.removeItem("ec_pending_payment");
    } catch {
      /* ignore */
    }
  }, [load]);

  // After a Stripe redirect the order is paid by the webhook, which may lag a
  // moment. Poll briefly until it flips to paid.
  useEffect(() => {
    if (provider !== "stripe") return;
    let tries = 0;
    const timer = setInterval(async () => {
      tries += 1;
      const o = await load();
      if ((o && o.payment_status === "paid") || tries >= 8) {
        setAwaitingWebhook(false);
        clearInterval(timer);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [provider, load]);

  async function completeSandboxPayment() {
    setWorking(true);
    try {
      await api.devConfirmPayment(orderNumber);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Payment simulation failed");
    } finally {
      setWorking(false);
    }
  }

  if (error) return <p className="rounded-md bg-red-50 p-4 text-red-700">{error}</p>;
  if (!order) return <p className="text-brand-500">Loading order…</p>;

  const paid = order.payment_status === "paid";

  return (
    <div className="mx-auto max-w-2xl">
      <div className="card p-8 text-center">
        <div className="text-4xl">{paid ? "🎉" : "🧾"}</div>
        <h1 className="mt-3 text-2xl font-bold">
          {paid ? "Thank you for your order!" : "Order placed"}
        </h1>
        <p className="mt-1 text-brand-500">
          Order <span className="font-mono font-medium">{order.order_number}</span>
        </p>
        <span className={`badge mt-3 ${statusClass(order.status)}`}>{order.status}</span>
      </div>

      <div className="card mt-6 p-6">
        <ul className="space-y-2 text-sm">
          {order.items.map((i) => (
            <li key={i.id} className="flex justify-between">
              <span>
                {i.product_name} {i.variant_name && `(${i.variant_name})`} × {i.quantity}
              </span>
              <span>{formatPrice(i.line_total_cents, order.currency)}</span>
            </li>
          ))}
        </ul>
        <dl className="mt-4 space-y-1 border-t border-brand-100 pt-4 text-sm">
          <Row label="Subtotal" value={formatPrice(order.subtotal_cents, order.currency)} />
          <Row label="Shipping" value={formatPrice(order.shipping_cents, order.currency)} />
          <Row label="Total" value={formatPrice(order.total_cents, order.currency)} bold />
        </dl>
      </div>

      {!paid && provider === "fake" && (
        <div className="mt-6 rounded-md border border-dashed border-brand-300 bg-brand-50 p-4 text-sm">
          <p className="mb-3 font-medium">Sandbox payment</p>
          <p className="mb-3 text-brand-500">
            Running with the built-in fake payment provider. Click below to simulate a successful
            gateway payment (in production this happens via the gateway webhook).
          </p>
          <button onClick={completeSandboxPayment} disabled={working} className="btn-primary">
            {working ? "Confirming…" : "Complete sandbox payment"}
          </button>
        </div>
      )}

      {!paid && provider === "stripe" && awaitingWebhook && (
        <div className="mt-6 flex items-center gap-3 rounded-md border border-dashed border-brand-300 bg-brand-50 p-4 text-sm text-brand-600">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
          Confirming your payment with the gateway…
        </div>
      )}

      {!paid && provider === "stripe" && !awaitingWebhook && (
        <div className="mt-6 rounded-md border border-dashed border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          We haven’t received payment confirmation yet. If you completed payment, this page will
          update shortly — you can also check{" "}
          <Link href="/account/orders" className="underline">
            your orders
          </Link>
          .
        </div>
      )}

      <div className="mt-6 flex justify-center gap-3">
        <Link href="/products" className="btn-secondary">
          Continue shopping
        </Link>
        <Link href="/account/orders" className="btn-primary">
          View my orders
        </Link>
      </div>
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? "font-semibold" : ""}`}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function ConfirmationPage() {
  return (
    <Suspense fallback={<p className="text-brand-500">Loading…</p>}>
      <Confirmation />
    </Suspense>
  );
}
