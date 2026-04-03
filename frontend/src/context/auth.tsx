import api from "@/lib/api";
import type { UserRole } from "@/types/api";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface User {
  username: string;
  role: UserRole;
}

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  loginFromCallback: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function parseJwt(token: string): { role: UserRole; email: string } {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return { role: payload.role ?? "user", email: payload.email ?? "" };
  } catch {
    return { role: "user", email: "" };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return null;
    const { role, email } = parseJwt(token);
    if (!email) return null;
    return { username: email, role };
  });

  const loginFromCallback = useCallback(
    (accessToken: string, refreshToken: string) => {
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken);
      const { role, email } = parseJwt(accessToken);
      setUser({ username: email, role });
    },
    [],
  );

  const logout = useCallback(() => {
    const accessToken = localStorage.getItem("access_token");
    const refreshToken = localStorage.getItem("refresh_token");

    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);

    if (accessToken) {
      api
        .post(
          "/api/v1/auth/logout",
          { refresh_token: refreshToken || undefined },
          { headers: { Authorization: `Bearer ${accessToken}` } },
        )
        .catch(() => {});
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isAdmin: user?.role === "admin",
      loginFromCallback,
      logout,
    }),
    [user, loginFromCallback, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
