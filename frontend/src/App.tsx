import { useEffect, useState } from "react";

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://127.0.0.1:8000";

interface Summary {
  accounts: number;
  records: number;
  seeded_breaks_total: number;
  seeded_breaks_caught: number;
  false_holds: number;
  total_held: number;
}

interface Exception {
  account: string;
  record_type: string;
  key: string;
  rule: string;
  disagreeing_field: string;
  custodian_value: string | null;
  book_value: string | null;
}

export function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [exceptions, setExceptions] = useState<Exception[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [summaryRes, exceptionsRes] = await Promise.all([
        fetch(`${API_BASE}/summary`),
        fetch(`${API_BASE}/exceptions`),
      ]);
      if (!summaryRes.ok) throw new Error(`GET /summary -> ${summaryRes.status}`);
      if (!exceptionsRes.ok) throw new Error(`GET /exceptions -> ${exceptionsRes.status}`);
      setSummary(await summaryRes.json());
      setExceptions(await exceptionsRes.json());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main>
      <h1>Multi-Custodian Reconciliation: Break Triage Console</h1>
      {error && <p role="alert">Failed to load: {error}</p>}
      {summary && (
        <p data-testid="summary">
          {summary.accounts} accounts, {summary.records} records reconciled,{" "}
          {summary.seeded_breaks_caught} of {summary.seeded_breaks_total} seeded breaks caught,{" "}
          {summary.false_holds} false holds.
        </p>
      )}
      <button onClick={load}>Refresh</button>
      <table>
        <thead>
          <tr>
            <th>Account</th>
            <th>Record</th>
            <th>Rule</th>
            <th>Disagreeing field</th>
            <th>Custodian value</th>
            <th>Book value</th>
          </tr>
        </thead>
        <tbody>
          {exceptions.map((e) => (
            <tr key={`${e.account}-${e.record_type}-${e.key}`} data-testid="exception-row">
              <td>{e.account}</td>
              <td>{e.record_type} {e.key}</td>
              <td data-testid="exception-rule">{e.rule}</td>
              <td data-testid="exception-field">{e.disagreeing_field}</td>
              <td>{e.custodian_value ?? "(none)"}</td>
              <td>{e.book_value ?? "(none)"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {exceptions.length === 0 && !error && <p>No exceptions.</p>}
    </main>
  );
}
