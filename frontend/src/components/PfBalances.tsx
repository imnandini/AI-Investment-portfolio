import type { BalanceAsset } from "../services/api";
import { formatMoney } from "./AllocationList";
import { HoldingResearchLink } from "./HoldingResearchLink";

export function PfBalances({ balances }: { balances: BalanceAsset[] }) {
  return <section className="surface-card positions-card" aria-label="Provident fund balances">
    <div className="table-heading"><div><span className="section-kicker">RETIREMENT ACCOUNTS</span><h2>PF balances</h2></div></div>
    <p className="balance-explanation">Import your provident fund using EPF (or PPF) in the INDmoney asset selector. These are account balances, shown separately from security quantities and stock allocation totals.</p>
    {balances.length === 0 ? <p className="balance-explanation">No PF balance imported yet.</p> : <div className="table-scroll"><table><thead><tr><th>Account</th><th>Invested amount reported</th><th>Balance reported</th><th>Balance date</th><th>Research</th></tr></thead>
      <tbody>{balances.map(balance => <tr key={balance.symbol}><td><b>{balance.display_name}</b><small>{balance.asset_type} · INDmoney</small></td><td>{formatMoney(balance.invested_amount, balance.currency)}</td><td>{formatMoney(balance.market_value, balance.currency)}</td><td>{balance.as_of ? new Date(balance.as_of).toLocaleDateString() : "Not supplied by INDmoney"}<small>Imported {new Date(balance.imported_at).toLocaleString()}</small></td><td><HoldingResearchLink symbol={balance.symbol} name={balance.display_name} /></td></tr>)}</tbody>
    </table></div>}
  </section>;
}
