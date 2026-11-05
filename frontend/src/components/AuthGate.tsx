import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { useAuth } from "../app/AuthContext";
import { AuthPanel } from "./AuthPanel";

export function AuthGate({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-loading"><LoaderCircle className="spin" size={18} /> Checking your session…</div>;
  return user ? <>{children}</> : <div className="auth-gate"><AuthPanel /></div>;
}
