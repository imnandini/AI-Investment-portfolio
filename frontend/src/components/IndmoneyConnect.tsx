import { useEffect, useRef, useState } from "react";
import { Link2, LoaderCircle, RefreshCw, Unplug } from "lucide-react";
import { apiDelete, apiGet, apiPost } from "../services/api";
import { formatMoney, formatQuantity } from "./AllocationList";

type Connection = { configured: boolean; connected: boolean; last_sync_at: string | null };
type Preview = {
  preview_id: string; expires_at: string; mode: string; warnings: string[];
  rows: { symbol: string; display_name?: string | null; kind?: "balance"; asset_type?: string; exchange?: string; currency: string; quantity?: string; average_cost?: string | null; market_value?: string; conflict: boolean }[];
};
type SyncResult = { added: number; updated: number; skipped: number; warnings: string[] };
const base = "/integrations/indmoney";
const assetLabel = (value: string) => ({ IND_STOCK: "Indian stocks", US_STOCK: "US stocks", MF: "Mutual funds", EPF: "EPF · Employee provident fund", PPF: "PPF · Public provident fund" }[value] || value.replaceAll("_", " "));

// Share a one-use code exchange across StrictMode effect replay.
let callbackPromise: Promise<unknown> | null = null;
function completeCallback() {
  const url = new URL(window.location.href);
  if (url.searchParams.has("state") && (url.searchParams.has("code") || url.searchParams.has("error"))) {
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");
    const denied = url.searchParams.has("error");
    ["code", "state", "error", "error_description", "iss"].forEach(key => url.searchParams.delete(key));
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    const expected = sessionStorage.getItem("indmoney_oauth_state");
    sessionStorage.removeItem("indmoney_oauth_state");
    callbackPromise = denied ? Promise.reject(new Error("INDmoney connection was cancelled. You can connect again."))
      : !state || state !== expected ? Promise.reject(new Error("INDmoney sign-in did not match this browser session. Connect again."))
      : apiPost(base + "/callback", { code, state });
  }
  return callbackPromise;
}

export function IndmoneyConnect({ portfolioId, onSynced }: { portfolioId: string; onSynced: () => Promise<void> }) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [assets, setAssets] = useState<string[]>([]);
  const [asset, setAsset] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const currentPortfolio = useRef(portfolioId);
  currentPortfolio.current = portfolioId;

  async function refreshConnection() {
    const status = await apiGet<Connection>(base);
    setConnection(status);
    if (status.connected) {
      const result = await apiGet<{ asset_types: string[] }>(base + "/assets");
      setAssets(result.asset_types);
      setAsset(current => result.asset_types.includes(current) ? current : result.asset_types[0] || "");
    }
  }

  useEffect(() => {
    let active = true;
    setBusy(true);
    const callback = completeCallback();
    (async () => {
      try {
        if (callback) await callback;
        if (active) await refreshConnection();
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Could not check INDmoney connection."); }
      finally {
        if (active && callbackPromise === callback) callbackPromise = null;
        if (active) setBusy(false);
      }
    })();
    return () => { active = false; };
  }, []);

  useEffect(() => { setPreview(null); setMessage(""); setWarnings([]); }, [portfolioId, asset]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "INDmoney request failed."); }
    finally { setBusy(false); }
  }

  async function connect() {
    await run(async () => {
      const result = await apiPost<{ authorization_url: string; state: string }>(base + "/connect");
      if (new URL(result.authorization_url).origin !== "https://mcp.indmoney.com") throw new Error("Unexpected INDmoney sign-in address.");
      sessionStorage.setItem("indmoney_oauth_state", result.state);
      window.location.assign(result.authorization_url);
    });
  }

  async function fetchPreview() {
    setPreview(null); setWarnings([]);
    const targetId = portfolioId;
    await run(async () => {
      const result = await apiPost<Preview>(`${base}/portfolios/${targetId}/preview`, { asset_type: asset });
      if (currentPortfolio.current === targetId) { setPreview(result); setWarnings(result.warnings); }
    });
  }

  async function sync() {
    if (!preview) return;
    const targetId = portfolioId;
    await run(async () => {
      const result = await apiPost<SyncResult>(`${base}/portfolios/${targetId}/sync`, { preview_id: preview.preview_id });
      if (currentPortfolio.current !== targetId) return;
      setPreview(null); setWarnings(result.warnings);
      setMessage(`INDmoney: ${result.added} added, ${result.updated} updated, ${result.skipped} skipped.`);
      await onSynced();
      const status = await apiGet<Connection>(base); setConnection(status);
    });
  }

  return <section className="surface-card indmoney-card" aria-label="INDmoney connection" aria-busy={busy}>
    <div className="indmoney-heading"><div><h2><Link2 size={18} />Connect your INDmoney holdings</h2>
      <p>Sign in on INDmoney, then preview and import your positions. Access is read-only.</p></div>
      <div className="indmoney-actions">
        <button className="button button-primary" type="button" disabled={busy} onClick={connect}>
          {busy ? <LoaderCircle size={15} className="spin" /> : <Link2 size={15} />}{connection?.connected ? "Reconnect INDmoney" : "Connect INDmoney"}
        </button>
        {connection?.connected && <button className="button button-secondary" type="button" disabled={busy} onClick={() => run(async () => {
          await apiDelete(base); setConnection({ configured: true, connected: false, last_sync_at: null });
          setAssets([]); setPreview(null); setWarnings([]); setMessage("INDmoney disconnected. Imported holdings are retained. You can also revoke consent in INDmoney settings.");
        })}><Unplug size={15} />Disconnect</button>}
      </div>
    </div>
    {connection && !connection.configured && <p>One-time setup: configure INDMONEY_TOKEN_KEY on the backend to protect your connection.</p>}
    {connection?.connected && <div className="indmoney-actions">
      <span className="freshness-pill freshness-available">Connected</span>
      <label htmlFor="indmoney-asset">Asset type</label><select id="indmoney-asset" value={asset} disabled={busy} onChange={event => setAsset(event.target.value)}>
        {assets.map(value => <option key={value} value={value}>{assetLabel(value)}</option>)}
      </select>
      <button className="button button-secondary" type="button" disabled={busy || !portfolioId || !asset} onClick={fetchPreview}><RefreshCw size={15} />Preview holdings</button>
      {assets.length === 0 && <button className="button button-secondary" type="button" disabled={busy} onClick={() => run(refreshConnection)}>Retry connection</button>}
      {connection.last_sync_at && <small>Last import: {new Date(connection.last_sync_at).toLocaleString()}</small>}
    </div>}
    {connection?.connected && <p>Each import covers the selected asset type. For your provident fund, select EPF (or PPF), then preview and import its reported balance.</p>}
    {!portfolioId && <p>Create a portfolio to import your connected holdings.</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {preview && <div className="indmoney-preview"><p>{preview.mode}</p>
      {preview.rows.length > 0 ? <><div className="table-scroll"><table><thead><tr><th>Instrument / account</th><th>Quantity / account</th><th>Average cost / balance</th><th>Import action</th></tr></thead>
        <tbody>{preview.rows.map(row => <tr key={`${row.symbol}:${row.exchange}`}><td>{row.display_name || row.symbol}<small>{row.kind === "balance" ? `${row.asset_type} account` : `${row.symbol} · ${row.exchange === "UNKNOWN" ? "Exchange not supplied" : row.exchange}`} · {row.currency}</small></td><td>{row.kind === "balance" ? "Account balance" : formatQuantity(row.quantity || "0")}</td><td>{formatMoney(row.kind === "balance" ? row.market_value ?? null : row.average_cost ?? null, row.currency)}</td><td>{row.conflict ? "Skip existing manual holding" : row.kind === "balance" ? "Add / refresh PF balance" : "Add / refresh INDmoney holding"}</td></tr>)}</tbody>
      </table></div><button className="button button-primary" type="button" disabled={busy || preview.rows.every(row => row.conflict)} onClick={sync}>Import reviewed holdings</button></>
        : <p>{preview.warnings.length > 0
          ? "INDmoney returned holdings, but none could be imported. Review the import notes below."
          : "No holdings returned by INDmoney for this asset type."}</p>}
      <small>Preview expires at {new Date(preview.expires_at).toLocaleTimeString()}. Positions absent from this import are retained; remove closed positions manually.</small>
    </div>}
    {warnings.length > 0 && <details className="indmoney-warnings" open><summary>Import notes ({warnings.length})</summary><ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
  </section>;
}
