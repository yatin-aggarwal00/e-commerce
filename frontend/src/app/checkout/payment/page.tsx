"use client";

import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";

interface Pending {
  orderNumber: string;
  clientSecret: string;
  email: string;
}

function readPending(): Pending | null {
  try {
    const raw = sessionStorage.getItem("ec_pending_payment");
    return raw ? (JSON.parse(raw) as Pending) : null;
  } catch {
    return null;
  }
}

export default function PaymentPage() {
  const router = useRouter();
  const [pending, setPending] = useState<Pending | null>(null);
  const [stripePromise, setStripePromise] = useState<Promise<Stripe | null> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const p = readPending();
    if (!p) {
      router.replace("/cart");
      return;
    }
    setPending(p);
    (async () => {
      try {
        const cfg = await api.paymentConfig();
        if (cfg.provider !== "stripe" || !cfg.publishable_key) {
          setError(
            "Card payments are not configured. Set STRIPE_PUBLISHABLE_KEY on the API.",
          );
          return;
        }
        setStripePromise(loadStripe(cfg.publishable_key));
      } catch {
        setError("Could not load the payment form. Please try again.");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  const options = useMemo(
    () => (pending ? { clientSecret: pending.clientSecret } : undefined),
    [pending],
  );

  if (loading && !error) return <p className="text-brand-500">Loading payment…</p>;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <p className="rounded-md bg-red-50 p-4 text-red-700">{error}</p>
        <Link href="/cart" className="btn-secondary mt-4 inline-block">
          Back to cart
        </Link>
      </div>
    );
  }
  if (!pending || !stripePromise || !options) return null;

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-6 text-2xl font-semibold">Payment</h1>
      <p className="mb-4 text-sm text-brand-500">
        Order <span className="font-mono">{pending.orderNumber}</span>. Enter your card details
        below — they go straight to Stripe and never touch our servers.
      </p>
      <Elements stripe={stripePromise} options={options}>
        <PayForm pending={pending} />
      </Elements>
    </div>
  );
}

function PayForm({ pending }: { pending: Pending }) {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;
    setSubmitting(true);
    setMessage(null);

    const returnUrl =
      `${window.location.origin}/checkout/confirmation` +
      `?order=${pending.orderNumber}&email=${encodeURIComponent(pending.email)}&provider=stripe`;

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: returnUrl },
    });

    // Only reached if confirmPayment fails before redirect (e.g. card declined
    // or validation error). On success Stripe redirects to return_url.
    if (error) {
      setMessage(error.message ?? "Payment could not be completed.");
      setSubmitting(false);
      try {
        sessionStorage.removeItem("ec_pending_payment");
      } catch {
        /* ignore */
      }
    }
  }

  return (
    <form onSubmit={onSubmit} className="card space-y-5 p-6">
      <PaymentElement />
      {message && <p className="text-sm text-red-600">{message}</p>}
      <button type="submit" disabled={!stripe || submitting} className="btn-primary w-full">
        {submitting ? "Processing…" : "Pay now"}
      </button>
    </form>
  );
}
