"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, cartToken, tokenStore } from "@/lib/api";
import type { Cart, User } from "@/lib/types";

interface StoreContextValue {
  cart: Cart | null;
  user: User | null;
  ready: boolean;
  itemCount: number;
  refreshCart: () => Promise<void>;
  addToCart: (variantId: string, quantity?: number) => Promise<void>;
  updateItem: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
}

const StoreContext = createContext<StoreContextValue | null>(null);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const persistCart = useCallback((c: Cart) => {
    cartToken.set(c.token);
    setCart(c);
  }, []);

  const refreshCart = useCallback(async () => {
    const c = await api.getCart();
    persistCart(c);
  }, [persistCart]);

  // Initial hydrate: load current user (if signed in) and the cart.
  useEffect(() => {
    (async () => {
      try {
        if (tokenStore.access) {
          try {
            setUser(await api.me());
          } catch {
            tokenStore.clear();
          }
        }
        await refreshCart();
      } finally {
        setReady(true);
      }
    })();
  }, [refreshCart]);

  const addToCart = useCallback(
    async (variantId: string, quantity = 1) => {
      persistCart(await api.addToCart(variantId, quantity));
    },
    [persistCart],
  );

  const updateItem = useCallback(
    async (itemId: string, quantity: number) => {
      persistCart(await api.updateCartItem(itemId, quantity));
    },
    [persistCart],
  );

  const removeItem = useCallback(
    async (itemId: string) => {
      persistCart(await api.removeCartItem(itemId));
    },
    [persistCart],
  );

  const afterAuth = useCallback(async () => {
    setUser(await api.me());
    // Merge the guest cart into the account cart, then reload.
    const guest = cartToken.get();
    if (guest) {
      try {
        persistCart(await api.mergeCart(guest));
        return;
      } catch {
        /* fall through to a plain refresh */
      }
    }
    await refreshCart();
  }, [persistCart, refreshCart]);

  const login = useCallback(
    async (email: string, password: string) => {
      tokenStore.set(await api.login(email, password));
      await afterAuth();
    },
    [afterAuth],
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      tokenStore.set(await api.register(email, password, fullName));
      await afterAuth();
    },
    [afterAuth],
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo<StoreContextValue>(
    () => ({
      cart,
      user,
      ready,
      itemCount: cart?.item_count ?? 0,
      refreshCart,
      addToCart,
      updateItem,
      removeItem,
      login,
      register,
      logout,
    }),
    [cart, user, ready, refreshCart, addToCart, updateItem, removeItem, login, register, logout],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreContextValue {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used within <StoreProvider>");
  return ctx;
}
