"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useStore } from "@/context/StoreProvider";
import { api, ApiError } from "@/lib/api";
import { formatPrice, statusClass } from "@/lib/format";
import type { Category, Order, ProductDetail } from "@/lib/types";

const ORDER_STATUSES = [
  "pending",
  "paid",
  "processing",
  "shipped",
  "delivered",
  "cancelled",
  "failed",
];

export default function AdminPage() {
  const { user, ready } = useStore();
  const router = useRouter();

  useEffect(() => {
    if (ready && (!user || !user.is_admin)) router.replace("/");
  }, [ready, user, router]);

  if (!ready || !user?.is_admin) return <p className="text-brand-500">Loading…</p>;

  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-semibold">Admin dashboard</h1>
      <Stats />
      <ProductManager />
      <OrderManager />
    </div>
  );
}

/* --------------------------------- stats --------------------------------- */
function Stats() {
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  useEffect(() => {
    api.adminStats().then(setStats).catch(() => setStats(null));
  }, []);
  if (!stats) return null;
  const tiles: [string, string][] = [
    ["Products", String(stats.active_products)],
    ["Orders", String(stats.orders)],
    ["Paid orders", String(stats.paid_orders)],
    ["Revenue", formatPrice(stats.revenue_cents)],
    ["Low stock", String(stats.low_stock)],
  ];
  return (
    <section className="grid grid-cols-2 gap-4 md:grid-cols-5">
      {tiles.map(([label, value]) => (
        <div key={label} className="card p-4">
          <p className="text-xs uppercase tracking-wide text-brand-400">{label}</p>
          <p className="mt-1 text-xl font-semibold">{value}</p>
        </div>
      ))}
    </section>
  );
}

/* ----------------------------- product manager --------------------------- */
function ProductManager() {
  const [products, setProducts] = useState<ProductDetail[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [p, c] = await Promise.all([api.adminListProducts(), api.listCategories()]);
    setProducts(p.items);
    setCategories(c);
  }, []);

  useEffect(() => {
    reload().catch(() => undefined);
  }, [reload]);

  async function deactivate(id: string) {
    await api.adminDeactivateProduct(id);
    await reload();
  }

  async function setInventory(variantId: string, quantity: number) {
    await api.adminSetInventory(variantId, quantity);
    setMsg("Inventory updated");
    await reload();
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Products</h2>
        {msg && <span className="text-sm text-emerald-700">{msg}</span>}
      </div>

      <CreateProduct categories={categories} onCreated={reload} onCategories={reload} />

      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-brand-400">
            <tr>
              <th className="py-2">Product</th>
              <th>Variant / SKU</th>
              <th>Price</th>
              <th>Stock</th>
              <th></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-50">
            {products.map((p) =>
              p.variants.map((v, idx) => (
                <tr key={v.id}>
                  <td className="py-2">
                    {idx === 0 ? (
                      <span className={p.is_active ? "" : "text-brand-300 line-through"}>
                        {p.name}
                      </span>
                    ) : (
                      ""
                    )}
                  </td>
                  <td className="text-brand-500">
                    {v.name} · {v.sku}
                  </td>
                  <td>{formatPrice(v.price_cents, v.currency)}</td>
                  <td>
                    <InventoryEditor
                      initial={v.available}
                      onSave={(q) => setInventory(v.id, q)}
                    />
                  </td>
                  <td>
                    {idx === 0 && p.is_active && (
                      <button
                        onClick={() => deactivate(p.id)}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
        {products.length === 0 && <p className="py-6 text-brand-400">No products yet.</p>}
      </div>
    </section>
  );
}

function InventoryEditor({ initial, onSave }: { initial: number; onSave: (q: number) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        className="input w-20 py-1"
      />
      {value !== initial && (
        <button onClick={() => onSave(value)} className="text-xs text-brand-700 hover:underline">
          Save
        </button>
      )}
    </div>
  );
}

function CreateProduct({
  categories,
  onCreated,
  onCategories,
}: {
  categories: Category[];
  onCreated: () => Promise<void>;
  onCategories: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newCategory, setNewCategory] = useState("");
  const [f, setF] = useState({
    name: "",
    slug: "",
    category_id: "",
    room_type: "",
    material: "",
    description: "",
    image: "",
    sku: "",
    price: "",
    quantity: "0",
  });

  async function addCategory() {
    if (!newCategory.trim()) return;
    const slug = newCategory.trim().toLowerCase().replace(/\s+/g, "-");
    await api.adminCreateCategory({ name: newCategory.trim(), slug });
    setNewCategory("");
    await onCategories();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.adminCreateProduct({
        name: f.name,
        slug: f.slug || f.name.toLowerCase().replace(/\s+/g, "-"),
        description: f.description,
        category_id: f.category_id,
        room_type: f.room_type,
        material: f.material,
        is_active: true,
        images: f.image ? [{ url: f.image, alt: f.name, position: 0 }] : [],
        variants: [
          {
            sku: f.sku,
            name: "Default",
            price_cents: Math.round(Number(f.price) * 100),
            currency: "usd",
            quantity: Number(f.quantity),
          },
        ],
      });
      setF({
        name: "", slug: "", category_id: "", room_type: "", material: "",
        description: "", image: "", sku: "", price: "", quantity: "0",
      });
      setOpen(false);
      await onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create product");
    }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn-secondary">
        + New product
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card grid grid-cols-2 gap-3 p-6 text-sm">
      <div className="col-span-2 flex items-end gap-2">
        <label className="flex-1">
          <span className="mb-1 block font-medium">New category</span>
          <input className="input" value={newCategory} onChange={(e) => setNewCategory(e.target.value)} />
        </label>
        <button type="button" onClick={addCategory} className="btn-secondary">
          Add
        </button>
      </div>

      <L label="Name"><input className="input" value={f.name} required onChange={(e) => setF({ ...f, name: e.target.value })} /></L>
      <L label="Slug (optional)"><input className="input" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} /></L>
      <L label="Category">
        <select className="input" value={f.category_id} required onChange={(e) => setF({ ...f, category_id: e.target.value })}>
          <option value="">Select…</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </L>
      <L label="Image URL"><input className="input" value={f.image} onChange={(e) => setF({ ...f, image: e.target.value })} /></L>
      <L label="Room type"><input className="input" value={f.room_type} onChange={(e) => setF({ ...f, room_type: e.target.value })} /></L>
      <L label="Material"><input className="input" value={f.material} onChange={(e) => setF({ ...f, material: e.target.value })} /></L>
      <L label="SKU"><input className="input" value={f.sku} required onChange={(e) => setF({ ...f, sku: e.target.value })} /></L>
      <L label="Price (USD)"><input className="input" type="number" step="0.01" value={f.price} required onChange={(e) => setF({ ...f, price: e.target.value })} /></L>
      <L label="Quantity"><input className="input" type="number" value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} /></L>
      <L label="Description" className="col-span-2">
        <textarea className="input" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      </L>
      {error && <p className="col-span-2 text-red-600">{error}</p>}
      <div className="col-span-2 flex gap-2">
        <button className="btn-primary">Create product</button>
        <button type="button" onClick={() => setOpen(false)} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}

function L({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block font-medium">{label}</span>
      {children}
    </label>
  );
}

/* ------------------------------ order manager ---------------------------- */
function OrderManager() {
  const [orders, setOrders] = useState<Order[]>([]);

  const reload = useCallback(async () => {
    const res = await api.adminListOrders();
    setOrders(res.items);
  }, []);

  useEffect(() => {
    reload().catch(() => undefined);
  }, [reload]);

  async function changeStatus(orderNumber: string, status: string) {
    await api.adminUpdateOrderStatus(orderNumber, status);
    await reload();
  }

  return (
    <section>
      <h2 className="mb-3 text-xl font-semibold">Orders</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-brand-400">
            <tr>
              <th className="py-2">Order</th>
              <th>Email</th>
              <th>Total</th>
              <th>Payment</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-50">
            {orders.map((o) => (
              <tr key={o.id}>
                <td className="py-2 font-mono">{o.order_number}</td>
                <td className="text-brand-500">{o.email}</td>
                <td>{formatPrice(o.total_cents, o.currency)}</td>
                <td>
                  <span className={`badge ${statusClass(o.payment_status)}`}>{o.payment_status}</span>
                </td>
                <td>
                  <select
                    className="input py-1"
                    value={o.status}
                    onChange={(e) => changeStatus(o.order_number, e.target.value)}
                  >
                    {ORDER_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {orders.length === 0 && <p className="py-6 text-brand-400">No orders yet.</p>}
      </div>
    </section>
  );
}
