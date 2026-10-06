"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import type { Category, Facets } from "@/lib/types";

const SORTS = [
  ["newest", "Newest"],
  ["price_asc", "Price: Low to High"],
  ["price_desc", "Price: High to Low"],
  ["name", "Name"],
] as const;

export function Filters({ facets, categories }: { facets: Facets; categories: Category[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      next.delete("page"); // reset paging on any filter change
      router.push(`${pathname}?${next.toString()}`);
    },
    [params, pathname, router],
  );

  const current = (key: string) => params.get(key) ?? "";

  return (
    <aside className="space-y-6 text-sm">
      <div>
        <h3 className="mb-2 font-semibold">Sort</h3>
        <select
          className="input"
          value={current("sort") || "newest"}
          onChange={(e) => setParam("sort", e.target.value)}
        >
          {SORTS.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <FilterGroup
        title="Category"
        options={categories.map((c) => [c.slug, c.name] as const)}
        selected={current("category")}
        onSelect={(v) => setParam("category", v)}
      />
      <FilterGroup
        title="Room"
        options={facets.room_types.map((r) => [r, r] as const)}
        selected={current("room_type")}
        onSelect={(v) => setParam("room_type", v)}
      />
      <FilterGroup
        title="Material"
        options={facets.materials.map((m) => [m, m] as const)}
        selected={current("material")}
        onSelect={(v) => setParam("material", v)}
      />
      <FilterGroup
        title="Color"
        options={facets.colors.map((c) => [c, c] as const)}
        selected={current("color")}
        onSelect={(v) => setParam("color", v)}
      />

      <div>
        <h3 className="mb-2 font-semibold">Availability</h3>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={current("in_stock") === "true"}
            onChange={(e) => setParam("in_stock", e.target.checked ? "true" : null)}
          />
          In stock only
        </label>
      </div>

      <button
        className="btn-secondary w-full"
        onClick={() => router.push(pathname)}
      >
        Clear filters
      </button>
    </aside>
  );
}

function FilterGroup({
  title,
  options,
  selected,
  onSelect,
}: {
  title: string;
  options: readonly (readonly [string, string])[];
  selected: string;
  onSelect: (value: string | null) => void;
}) {
  if (options.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 font-semibold">{title}</h3>
      <ul className="space-y-1">
        {options.map(([value, label]) => (
          <li key={value}>
            <button
              onClick={() => onSelect(selected === value ? null : value)}
              className={`w-full rounded px-2 py-1 text-left capitalize ${
                selected === value ? "bg-brand-100 font-medium text-brand-800" : "hover:bg-brand-100"
              }`}
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
