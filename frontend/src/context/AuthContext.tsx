import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { authApi, tokenKey } from "../services/api";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signIn: (
    email: string,
    password: string,
    remember?: boolean
  ) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: (password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    authApi
      .me()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    const onUnauthorized = () => setUser(null);
    window.addEventListener("scholar:unauthorized", onUnauthorized);
    return () => {
      active = false;
      window.removeEventListener("scholar:unauthorized", onUnauthorized);
    };
  }, []);

  async function saveSession(
    request: Promise<{ access_token: string; user: User }>,
    remember = true
  ) {
    const session = await request;
    const storage = remember ? localStorage : sessionStorage;
    const otherStorage = remember ? sessionStorage : localStorage;
    storage.setItem(tokenKey, session.access_token);
    storage.setItem("scholar_user", JSON.stringify(session.user));
    otherStorage.removeItem(tokenKey);
    otherStorage.removeItem("scholar_user");
    setUser(session.user);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn: (email, password, remember) =>
          saveSession(authApi.login(email, password, remember), remember),
        signUp: (name, email, password) =>
          saveSession(authApi.register(name, email, password)),
        signOut: async () => {
          try {
            await authApi.logout();
          } finally {
            setUser(null);
          }
        },
        deleteAccount: async (password) => {
          await authApi.deleteAccount(password);
          setUser(null);
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
