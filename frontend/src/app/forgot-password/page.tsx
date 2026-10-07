"use client";

import Link from "next/link";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold">Reset your password</h1>
      {sent ? (
        <div className="card space-y-3 p-6 text-sm text-brand-600">
          <p>
            If an account exists for <span className="font-medium">{email}</span>, we’ve sent a
            link to reset your password. Check your inbox.
          </p>
          <Link href="/login" className="text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="card space-y-4 p-6">
          <p className="text-sm text-brand-500">
            Enter your email and we’ll send you a link to reset your password.
          </p>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Email</span>
            <input
              className="input"
              type="email"
              value={email}
              required
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}
    </div>
  );
}
