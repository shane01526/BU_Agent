'use client';

import { createContext, useContext, useEffect, useState } from 'react';

const COOKIE_KEY = 'x-dev-user-id';

interface AuthState {
  userId: string | null;
  login: (userId: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  userId: null,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const match = document.cookie.match(new RegExp(`${COOKIE_KEY}=([^;]+)`));
    if (match) setUserId(decodeURIComponent(match[1]));
  }, []);

  const login = (id: string) => {
    document.cookie = `${COOKIE_KEY}=${encodeURIComponent(id)}; path=/; max-age=${60 * 60 * 24}`;
    setUserId(id);
  };
  const logout = () => {
    document.cookie = `${COOKIE_KEY}=; path=/; max-age=0`;
    setUserId(null);
  };

  return (
    <AuthContext.Provider value={{ userId, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export function getStoredUserId(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`${COOKIE_KEY}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : null;
}
