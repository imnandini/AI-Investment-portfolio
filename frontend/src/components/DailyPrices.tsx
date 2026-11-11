import type { DailyPriceOverview } from "../services/api";
import { formatMoney } from "./AllocationList";

export function DailyPrices({ overview, currency }: { overview?: DailyPriceOverview | null; currency: string }) {
  if (!overview) return null;
  return <section className="surface-card research-card daily-prices" aria-label="Daily price updates">
    <div className="daily-prices-heading"><div><span className="section-kicker">DAILY CLOSING PRICES</span><h2>Your portfolio, updated automatically</h2></div>
      <span className="currency-chip">{overview.covered_positions} / {overview.position_count} with daily history</span></div>
    {overview.configured ? <p>We check for completed daily closes through {overview.requested_through}. Prices refresh when you open your portfolio and in the background while the app is running. No daily price entry needed.</p>
      : <p>Automatic daily prices are not connected. Imported prices remain visible; no current price is estimated.</p>}
    {overview.latest_date && <p><b>Covered holdings have closes dated {overview.latest_date} or later.</b> Each holding shows its own price date below. Weekends and exchange holidays can have no new close.</p>}
    {overview.checked_at && <small>Last check: {new Date(overview.checked_at).toLocaleString()} · {overview.provider}</small>}
    {overview.comparisons.length > 0 && <>
      <h3>How have prices changed?</h3>
      <div className="table-scroll"><table className="daily-price-comparisons"><thead><tr><th>Comparison</th><th>Earlier value</th><th>Latest value</th><th>Price change</th></tr></thead><tbody>
        {overview.comparisons.map(item => <tr key={item.label}>
          <td><b>{item.label}</b><small>{item.from_date} → {item.to_date}</small></td>
          <td>{formatMoney(item.previous_value, currency)}</td><td>{formatMoney(item.latest_value, currency)}</td>
          <td>{formatMoney(item.change, currency)}{item.change_pct !== null && <small>{Number(item.change_pct) > 0 ? "+" : ""}{item.change_pct}%</small>}</td>
        </tr>)}
      </tbody></table></div>
      <p>{overview.comparison_basis}</p>
    </>}
    {overview.notes.length > 0 && <details open={overview.covered_positions < overview.position_count}><summary>Price coverage &amp; update details</summary><ul>{overview.notes.map(note => <li key={note}>{note}</li>)}</ul></details>}
  </section>;
}
