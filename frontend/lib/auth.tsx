"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, getToken, login as apiLogin, setToken, type User } from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
  canApprove: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      if (!getToken()) {
        if (!cancelled) setLoading(false)
        return
      }
      try {
        const u = await api.me()
        if (!cancelled) setUser(u)
      } catch {
        setToken(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null)
      router.replace("/login")
    }
    window.addEventListener("klarnova:unauthorized", onUnauthorized)
    return () => window.removeEventListener("klarnova:unauthorized", onUnauthorized)
  }, [router])

  const login = useCallback(async (username: string, password: string) => {
    const { access_token } = await apiLogin(username, password)
    setToken(access_token)
    const u = await api.me()
    setUser(u)
    return u
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login,
      logout,
      canApprove: Boolean(user) && /admin|engineer/i.test(user?.role ?? ""),
    }),
    [user, loading, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
