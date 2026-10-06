"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useStore } from "@/context/StoreProvider";
import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";

const DELIVERY = [
  { id: "standard", label: "Standard (free over $500)", note: "5–7 business days" },
  { id: "express", label: "Express", note: "2–3 business days" },
  { id: "white_glove", label: "White glove", note: "Scheduled, assembled" },
];

export default function CheckoutPage() {
  const { cart, user, ready, refreshCart } = useStore();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    line1: "",
    line2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "US",
    phone: "",
    delivery_option: "standard",
  });

  useEffect(() => {
    if (user) setForm((f) => ({ ...f, email: user.email, full_name: user.full_name }));
  }, [user]);

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  if (ready && (!cart || cart.items.length === 0)) {
    return (
      <div className="py-20 text-center">
        <h1 className="text-2xl font-semibold">Nothing to check out</h1>
        <Link href="/products" className="btn-primary mt-6">
          Browse products
        </Link>
      </div>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!cart) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.checkout({
        cart_token: cart.token,
        email: form.email,
        delivery_option: form.delivery_option,
        shipping_address: {
          full_name: form.full_name,
          phone: form.phone,
          line1: form.line1,
          line2: form.line2,
          city: form.city,
          state: form.state,
          postal_code: form.postal_code,
          country: form.country,
        },
      });
      await refreshCart(); // cart was emptied server-side on order creation
      router.push(
        `/checkout/confirmation?order=${res.order.order_number}` +
          `&email=${encodeURIComponent(form.email)}&provider=${res.provider}`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Checkout failed. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Checkout</h1>

        <fieldset className="card space-y-4 p-6">
          <legend className="px-1 font-medium">Contact</legend>
          <Field label="Email" value={form.email} onChange={(v) => set("email", v)} type="email" required />
        </fieldset>

        <fieldset className="card grid grid-cols-2 gap-4 p-6">
          <legend className="px-1 font-medium">Shipping address</legend>
          <Field label="Full name" value={form.full_name} onChange={(v) => set("full_name", v)} required className="col-span-2" />
          <Field label="Address line 1" value={form.line1} onChange={(v) => set("line1", v)} required className="col-span-2" />
          <Field label="Address line 2" value={form.line2} onChange={(v) => set("line2", v)} className="col-span-2" />
          <Field label="City" value={form.city} onChange={(v) => set("city", v)} required />
          <Field label="State / Province" value={form.state} onChange={(v) => set("state", v)} />
          <Field label="Postal code" value={form.postal_code} onChange={(v) => set("postal_code", v)} required />
          <Field label="Country (2-letter)" value={form.country} onChange={(v) => set("country", v.toUpperCase())} required />
          <Field label="Phone" value={form.phone} onChange={(v) => set("phone", v)} className="col-span-2" />
        </fieldset>

        <fieldset className="card space-y-3 p-6">
          <legend className="px-1 font-medium">Delivery</legend>
          {DELIVERY.map((d) => (
            <label key={d.id} className="flex items-center gap-3">
              <input
                type="radio"
                name="delivery"
                checked={form.delivery_option === d.id}
                onChange={() => set("delivery_option", d.id)}
              />
              <span>
                <span className="font-medium">{d.label}</span>{" "}
                <span className="text-xs text-brand-400">· {d.note}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      </div>

      <aside className="card h-fit p-6">
        <h2 className="mb-4 text-lg font-semibold">Order summary</h2>
        {cart && (
          <>
            <ul className="space-y-2 text-sm">
              {cart.items.map((i) => (
                <li key={i.id} className="flex justify-between">
                  <span className="pr-2">
                    {i.product_name} × {i.quantity}
                  </span>
                  <span>{formatPrice(i.line_total_cents, i.currency)}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex justify-between border-t border-brand-100 pt-4 font-semibold">
              <span>Subtotal</span>
              <span>{formatPrice(cart.subtotal_cents, cart.currency)}</span>
            </div>
          </>
        )}
        <button type="submit" disabled={submitting} className="btn-primary mt-6 w-full">
          {submitting ? "Placing order…" : "Place order"}
        </button>
        <p className="mt-3 text-xs text-brand-400">
          Payments are processed securely by the gateway. No card details touch our servers.
        </p>
      </aside>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className={`block text-sm ${className}`}>
      <span className="mb-1 block font-medium">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      <input
        className="input"
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
