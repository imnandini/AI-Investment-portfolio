import { useEffect, useState } from "react";
import { Check, CircleAlert, LoaderCircle } from "lucide-react";
import { getHealth } from "../services/api";

type Status = "loading" | "connected" | "error";

export function ApiStatus({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<Status>("loading");
  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then((result) => setStatus(result.status === "ok" ? "connected" : "error"))
      .catch((error: unknown) => { if (!(error instanceof DOMException && error.name === "AbortError")) setStatus("error"); });
    return () => controller.abort();
  }, []);

  const copy = status === "loading" ? "Checking API" : status === "connected" ? "API connected" : "API unavailable";
  const Icon = status === "loading" ? LoaderCircle : status === "connected" ? Check : CircleAlert;
  return <span className={`api-status ${status}${compact ? " compact" : ""}`} role="status" aria-live="polite"><Icon size={14} className={status === "loading" ? "spin" : ""} />{copy}</span>;
}
