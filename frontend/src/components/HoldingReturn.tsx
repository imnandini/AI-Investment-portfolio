import type { HoldingAnalytics } from "../services/api";
import { formatMoney } from "./AllocationList";

export function formatReturn(value: string | null | undefined) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

export function HoldingReturn({ position, currency }: { position?: HoldingAnalytics; currency: string }) {
  const usable = position?.price_status === "available";
  const percent = usable ? position?.unrealized_return_pct : null;
  const reason = !usable ? "A usable dated price is needed for a return percentage."
    : position?.average_cost == null ? "Purchase cost is unknown."
    : Number(position.average_cost) === 0 ? "Return percentage is undefined when purchase cost is zero."
    : "Cumulative price return on average purchase cost; excludes dividends, realized trades, fees and taxes. Not annualized.";
  const tone = percent != null && Number(percent) !== 0 ? Number(percent) > 0 ? "return-positive" : "return-negative" : "";
  return <>
    <td>{formatMoney(usable ? position?.unrealized_pl ?? null : null, currency)}</td>
    <td className={tone} title={reason}><b>{formatReturn(percent)}</b>{percent == null && <small>Unavailable</small>}</td>
  </>;
}
