// Shapes mirror the FastAPI response models (app/schemas/*).

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string;
  image_url: string;
  parent_id: string | null;
}

export interface ProductListItem {
  id: string;
  name: string;
  slug: string;
  room_type: string;
  material: string;
  category_id: string;
  thumbnail: string | null;
  min_price_cents: number | null;
  currency: string;
  in_stock: boolean;
}

export interface Variant {
  id: string;
  sku: string;
  name: string;
  color: string;
  size: string;
  price_cents: number;
  currency: string;
  dimensions: string;
  weight_kg: number;
  in_stock: boolean;
  available: number;
}

export interface ProductImage {
  id: string;
  url: string;
  alt: string;
  position: number;
}

export interface ProductDetail {
  id: string;
  name: string;
  slug: string;
  description: string;
  category_id: string;
  room_type: string;
  material: string;
  is_active: boolean;
  category: Category | null;
  images: ProductImage[];
  variants: Variant[];
}

export interface Facets {
  room_types: string[];
  materials: string[];
  colors: string[];
  price_min_cents: number;
  price_max_cents: number;
}

export interface CartItem {
  id: string;
  variant_id: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  variant_name: string;
  sku: string;
  thumbnail: string | null;
  unit_price_cents: number;
  currency: string;
  quantity: number;
  line_total_cents: number;
  available: number;
  in_stock: boolean;
}

export interface Cart {
  id: string;
  token: string;
  items: CartItem[];
  subtotal_cents: number;
  currency: string;
  item_count: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface Address {
  id: string;
  label: string;
  full_name: string;
  phone: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  is_default: boolean;
}

export interface OrderItem {
  id: string;
  product_name: string;
  variant_name: string;
  sku: string;
  unit_price_cents: number;
  quantity: number;
  line_total_cents: number;
}

export interface Order {
  id: string;
  order_number: string;
  email: string;
  status: string;
  payment_status: string;
  subtotal_cents: number;
  shipping_cents: number;
  total_cents: number;
  currency: string;
  delivery_option: string;
  created_at: string;
  items: OrderItem[];
}

export interface CheckoutResponse {
  order: Order;
  payment_client_secret: string;
  payment_intent_id: string;
  provider: string;
}

export interface PaymentConfig {
  provider: string;
  publishable_key: string;
}

export interface UploadResult {
  url: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
