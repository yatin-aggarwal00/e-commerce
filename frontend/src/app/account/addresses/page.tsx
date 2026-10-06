"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Address } from "@/lib/types";

const EMPTY = {
  label: "Home",
  full_name: "",
  phone: "",
  line1: "",
  line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "US",
  is_default: false,
};

export default function AddressesPage() {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setAddresses(await api.listAddresses());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createAddress(form);
      setForm({ ...EMPTY });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save address");
    }
  }

  async function remove(id: string) {
    await api.deleteAddress(id);
    await load();
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Saved addresses</h1>

      {loading ? (
        <p className="text-brand-500">Loading…</p>
      ) : addresses.length === 0 ? (
        <p className="mb-6 text-brand-500">No saved addresses yet.</p>
      ) : (
        <ul className="mb-6 grid gap-4 sm:grid-cols-2">
          {addresses.map((a) => (
            <li key={a.id} className="card p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{a.label}</span>
                {a.is_default && <span className="badge bg-brand-100 text-brand-700">Default</span>}
              </div>
              <p className="mt-1">{a.full_name}</p>
              <p className="text-brand-500">
                {a.line1}
                {a.line2 && `, ${a.line2}`}
                <br />
                {a.city}, {a.state} {a.postal_code}, {a.country}
              </p>
              <button onClick={() => remove(a.id)} className="mt-2 text-xs text-red-600 hover:underline">
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={add} className="card grid grid-cols-2 gap-3 p-6 text-sm">
        <h2 className="col-span-2 font-medium">Add an address</h2>
        <Input label="Label" value={form.label} onChange={(v) => setForm({ ...form, label: v })} />
        <Input label="Full name" value={form.full_name} onChange={(v) => setForm({ ...form, full_name: v })} required />
        <Input label="Line 1" value={form.line1} onChange={(v) => setForm({ ...form, line1: v })} required className="col-span-2" />
        <Input label="Line 2" value={form.line2} onChange={(v) => setForm({ ...form, line2: v })} className="col-span-2" />
        <Input label="City" value={form.city} onChange={(v) => setForm({ ...form, city: v })} required />
        <Input label="State" value={form.state} onChange={(v) => setForm({ ...form, state: v })} />
        <Input label="Postal code" value={form.postal_code} onChange={(v) => setForm({ ...form, postal_code: v })} required />
        <Input label="Country" value={form.country} onChange={(v) => setForm({ ...form, country: v.toUpperCase() })} required />
        <label className="col-span-2 flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.is_default}
            onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
          />
          Set as default
        </label>
        {error && <p className="col-span-2 text-red-600">{error}</p>}
        <button className="btn-primary col-span-2">Save address</button>
      </form>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  required,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block font-medium">{label}</span>
      <input className="input" value={value} required={required} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
