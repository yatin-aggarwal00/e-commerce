import type {
  Address,
  Cart,
  Category,
  CheckoutResponse,
  Facets,
  Order,
  Page,
  ProductDetail,
  ProductListItem,
  TokenPair,
  User,
} from "./types";

// Browser calls go to NEXT_PUBLIC_API_URL; Server Components use the internal
// URL (same host when running locally, the compose service name in Docker).
const BROWSER_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const SERVER_BASE =
  process.env.API_URL_INTERNAL ?? BROWSER_BASE;

export const ACCESS_KEY = "ec_access";
export const REFRESH_KEY = "ec_refresh";
export const CART_TOKEN_KEY = "ec_cart_token";

function base(): string {
  return typeof window === "undefined" ? SERVER_BASE : BROWSER_BASE;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/* ----------------------------- token storage ---------------------------- */
export const tokenStore = {
  get access() {
    return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const cartToken = {
  get() {
    return typeof window === "undefined" ? null : localStorage.getItem(CART_TOKEN_KEY);
  },
  set(token: string) {
    if (typeof window !== "undefined") localStorage.setItem(CART_TOKEN_KEY, token);
  },
  clear() {
    if (typeof window !== "undefined") localStorage.removeItem(CART_TOKEN_KEY);
  },
};

/* ------------------------------- core fetch ------------------------------ */
interface Opts {
  method?: string;
  body?: unknown;
  auth?: boolean;
  cart?: boolean;
  // Next.js fetch cache hints (server only).
  revalidate?: number;
  retry?: boolean;
}

async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (opts.auth && tokenStore.access) {
    headers["Authorization"] = `Bearer ${tokenStore.access}`;
  }
  if (opts.cart && cartToken.get()) {
    headers["X-Cart-Token"] = cartToken.get() as string;
  }

  const res = await fetch(`${base()}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body != null ? JSON.stringify(opts.body) : undefined,
    next: opts.revalidate != null ? { revalidate: opts.revalidate } : undefined,
    cache: opts.revalidate != null ? undefined : "no-store",
  });

  // Transparent one-shot refresh on expiry for authenticated requests.
  if (res.status === 401 && opts.auth && opts.retry !== false && tokenStore.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, { ...opts, retry: false });
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const pair = await request<TokenPair>("/auth/refresh", {
      method: "POST",
      body: { refresh_token: tokenStore.refresh },
      retry: false,
    });
    tokenStore.set(pair);
    return true;
  } catch {
    tokenStore.clear();
    return false;
  }
}

/* -------------------------------- catalog -------------------------------- */
export interface ProductQuery {
  q?: string;
  category?: string;
  room_type?: string;
  material?: string;
  color?: string;
  price_min?: number;
  price_max?: number;
  in_stock?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  // Catalog (cacheable on the server for SSR/ISR).
  listProducts: (query: ProductQuery = {}) =>
    request<Page<ProductListItem>>(
      `/catalog/products${qs(query as Record<string, unknown>)}`,
      { revalidate: 60 },
    ),
  getProduct: (slug: string) =>
    request<ProductDetail>(`/catalog/products/${slug}`, { revalidate: 60 }),
  listCategories: () =>
    request<Category[]>("/catalog/categories", { revalidate: 300 }),
  getFacets: () => request<Facets>("/catalog/facets", { revalidate: 300 }),
  autocomplete: (q: string) =>
    request<{ name: string; slug: string }[]>(`/catalog/autocomplete${qs({ q })}`),

  // Cart (guest + authenticated).
  getCart: () => request<Cart>("/cart", { cart: true, auth: true }),
  addToCart: (variant_id: string, quantity = 1) =>
    request<Cart>("/cart/items", {
      method: "POST",
      body: { variant_id, quantity },
      cart: true,
      auth: true,
    }),
  updateCartItem: (itemId: string, quantity: number) =>
    request<Cart>(`/cart/items/${itemId}`, {
      method: "PATCH",
      body: { quantity },
      cart: true,
      auth: true,
    }),
  removeCartItem: (itemId: string) =>
    request<Cart>(`/cart/items/${itemId}`, { method: "DELETE", cart: true, auth: true }),
  mergeCart: (guest_token: string) =>
    request<Cart>(`/cart/merge${qs({ guest_token })}`, { method: "POST", auth: true }),

  // Auth.
  register: (email: string, password: string, full_name: string) =>
    request<TokenPair>("/auth/register", {
      method: "POST",
      body: { email, password, full_name },
    }),
  login: (email: string, password: string) =>
    request<TokenPair>("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request<User>("/auth/me", { auth: true }),

  // Checkout + orders.
  checkout: (body: {
    cart_token: string;
    email: string;
    address_id?: string;
    shipping_address?: Record<string, unknown>;
    delivery_option: string;
  }) => request<CheckoutResponse>("/checkout", { method: "POST", body, auth: true }),
  listOrders: () => request<Order[]>("/orders", { auth: true }),
  getOrder: (orderNumber: string, email?: string) =>
    request<Order>(`/orders/${orderNumber}${qs({ email })}`, { auth: true }),
  // Dev-only: confirm a sandbox payment (fake provider). No-op in production.
  devConfirmPayment: (orderNumber: string) =>
    request<{ status: string }>(`/payments/dev/confirm/${orderNumber}`, { method: "POST" }),

  // Addresses.
  listAddresses: () => request<Address[]>("/addresses", { auth: true }),
  createAddress: (body: Partial<Address>) =>
    request<Address>("/addresses", { method: "POST", body, auth: true }),
  deleteAddress: (id: string) =>
    request<{ detail: string }>(`/addresses/${id}`, { method: "DELETE", auth: true }),

  // Admin.
  adminStats: () => request<Record<string, number>>("/admin/stats", { auth: true }),
  adminListProducts: (page = 1) =>
    request<Page<ProductDetail>>(`/admin/products${qs({ page })}`, { auth: true }),
  adminCreateCategory: (body: { name: string; slug: string; description?: string }) =>
    request<Category>("/admin/categories", { method: "POST", body, auth: true }),
  adminCreateProduct: (body: unknown) =>
    request<ProductDetail>("/admin/products", { method: "POST", body, auth: true }),
  adminDeactivateProduct: (id: string) =>
    request<{ detail: string }>(`/admin/products/${id}`, { method: "DELETE", auth: true }),
  adminSetInventory: (variantId: string, quantity: number) =>
    request(`/admin/variants/${variantId}/inventory`, {
      method: "PUT",
      body: { quantity },
      auth: true,
    }),
  adminListOrders: (page = 1) =>
    request<Page<Order>>(`/admin/orders${qs({ page })}`, { auth: true }),
  adminUpdateOrderStatus: (orderNumber: string, status: string) =>
    request<Order>(`/admin/orders/${orderNumber}/status`, {
      method: "PATCH",
      body: { status },
      auth: true,
    }),
};
