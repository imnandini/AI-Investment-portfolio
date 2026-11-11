import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { apiGet, apiPost, type TokenResponse, type User, type VerificationResponse } from "../services/api";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, confirmPassword: string) => Promise<VerificationResponse>;
  verifyEmail: (email: string, password: string, code: string) => Promise<void>;
  resendVerification: (email: string, password: string) => Promise<VerificationResponse>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const acceptToken = useCallback(async (token: string) => {
    sessionStorage.setItem("northstar_access_token", token);
    try {
      const current = await apiGet<User>("/auth/me");
      setUser(current);
    } catch (error) {
      sessionStorage.removeItem("northstar_access_token");
      setUser(null);
      throw error;
    }
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem("northstar_access_token");
    if (!token) { setLoading(false); return; }
    void acceptToken(token).catch(() => undefined).finally(() => setLoading(false));
  }, [acceptToken]);

  const signIn = useCallback(async (email: string, password: string) => {
    const token = await apiPost<TokenResponse>("/auth/login", { email, password });
    await acceptToken(token.access_token);
  }, [acceptToken]);

  const register = useCallback((email: string, password: string, confirmPassword: string) =>
    apiPost<VerificationResponse>("/auth/register", { email, password, confirm_password: confirmPassword }), []);

  const resendVerification = useCallback((email: string, password: string) =>
    apiPost<VerificationResponse>("/auth/resend-verification", { email, password }), []);

  const verifyEmail = useCallback(async (email: string, password: string, code: string) => {
    const token = await apiPost<TokenResponse>("/auth/verify-email", { email, password, code });
    await acceptToken(token.access_token);
  }, [acceptToken]);

  const signOut = useCallback(() => {
    sessionStorage.removeItem("northstar_access_token");
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, signIn, register, verifyEmail, resendVerification, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}
