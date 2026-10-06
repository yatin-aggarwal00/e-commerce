"use client";

import { useEffect } from "react";

/**
 * Client-side error tracking. Initialises Sentry only when
 * NEXT_PUBLIC_SENTRY_DSN is configured, so dev/CI builds without a DSN are a
 * complete no-op (and never require a Sentry auth token at build time).
 */
export function SentryInit() {
  useEffect(() => {
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (!dsn) return;
    import("@sentry/nextjs")
      .then((Sentry) => {
        if (Sentry.getClient?.()) return; // already initialised
        Sentry.init({
          dsn,
          environment: process.env.NEXT_PUBLIC_SENTRY_ENV ?? "production",
          tracesSampleRate: 0.1,
        });
      })
      .catch(() => undefined);
  }, []);

  return null;
}
