"use client";

import { useState } from "react";

import { useStore } from "@/context/StoreProvider";
import { ApiError } from "@/lib/api";
import type { Variant } from "@/lib/types";

export function AddToCart({ variants }: { variants: Variant[] }) {
  const { addToCart } = useStore();
  const available = variants.filter((v) => v.in_stock);
  const [variantId, setVariantId] = useState(available[0]?.id ?? variants[0]?.id ?? "");
  const [qty, setQty] = useState(1);
  const [status, setStatus] = useState<"idle" | "adding" | "added">("idle");
  const [error, setError] = useState<string | null>(null);

  const selected = variants.find((v) => v.id === variantId);
  const disabled = !selected || !selected.in_stock;

  async function onAdd() {
    if (!selected) return;
    setStatus("adding");
    setError(null);
    try {
      await addToCart(selected.id, qty);
      setStatus("added");
      setTimeout(() => setStatus("idle"), 1500);
    } catch (e) {
      setStatus("idle");
      setError(e instanceof ApiError ? e.message : "Could not add to cart");
    }
  }

  return (
    <div className="space-y-4">
      {variants.length > 1 && (
        <div>
          <label className="mb-1 block text-sm font-medium">Options</label>
          <div className="flex flex-wrap gap-2">
            {variants.map((v) => (
              <button
                key={v.id}
                type="button"
                disabled={!v.in_stock}
                onClick={() => setVariantId(v.id)}
                className={`rounded-md border px-3 py-1.5 text-sm ${
                  v.id === variantId
                    ? "border-brand-600 bg-brand-100"
                    : "border-brand-200 bg-white"
                } disabled:opacity-40`}
              >
                {v.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        <label htmlFor="qty" className="text-sm font-medium">
          Qty
        </label>
        <input
          id="qty"
          type="number"
          min={1}
          max={selected?.available ?? 1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, Number(e.target.value)))}
          className="input w-20"
        />
        <span className="text-xs text-brand-400">
          {selected?.in_stock ? `${selected.available} in stock` : "Unavailable"}
        </span>
      </div>

      <button onClick={onAdd} disabled={disabled || status === "adding"} className="btn-primary w-full">
        {status === "adding" ? "Adding…" : status === "added" ? "Added ✓" : "Add to cart"}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
