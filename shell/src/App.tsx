import { useEffect, useState } from "react";
import { Branding, DEFAULT_BRANDING, applyBranding, loadBranding } from "./branding";

// Layout tokens from @agent-authority/tokens v0.3: chat pane 380px, preview >= 480px.
// The <agent-authority> element comes from its pinned npm package (publish pending on
// Agent Authority's side); until then the Audit record tab shows a placeholder.

type SessionStatus =
  | { status: "idle" }
  | { status: "running" | "passed" | "failed" | "blocked"; sessionId: string }
  | { status: "needs_approval"; sessionId: string; approval: { tool: string; reasons: string[] } }
  | { status: "paused"; sessionId: string; reason: string };

export function App() {
  const [brand, setBrand] = useState<Branding>(DEFAULT_BRANDING);
  const [session, setSession] = useState<SessionStatus>({ status: "idle" });
  const [request, setRequest] = useState("");
  const [tab, setTab] = useState<"preview" | "audit">("preview");

  useEffect(() => {
    loadBranding().then((b) => {
      setBrand(b);
      applyBranding(b);
    });
  }, []);

  async function start() {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: "demo", request }),
    });
    setSession(await res.json());
  }

  async function answer(approved: boolean) {
    if (session.status !== "needs_approval") return;
    const res = await fetch(`/api/sessions/${session.sessionId}/approval`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    });
    setSession(await res.json());
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "380px minmax(480px, 1fr)", height: "100vh" }}>
      <aside aria-label="Chat" style={{ borderRight: "1px solid var(--aa-border, #ddd)", padding: 16 }}>
        <header style={{ fontWeight: 600, marginBottom: 12 }}>
          {brand.logoUrl ? <img src={brand.logoUrl} alt="" height={20} /> : null} {brand.productName}
        </header>
        <textarea value={request} onChange={(e) => setRequest(e.target.value)} rows={5} style={{ width: "100%" }}
          placeholder="Describe the app you need" />
        <button onClick={start} disabled={!request.trim()}>Build</button>

        {session.status === "needs_approval" && (
          <section role="alert" aria-label="Needs approval" style={{ marginTop: 16 }}>
            <p><strong>Needs approval:</strong> {session.approval.tool}</p>
            <ul>{session.approval.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            <button onClick={() => answer(true)}>Approve</button>{" "}
            <button onClick={() => answer(false)}>Reject</button>
          </section>
        )}
        {session.status === "paused" && (
          <p role="status">Paused: governance unreachable. Nothing ran past the last check; retrying.</p>
        )}
      </aside>

      <main>
        <nav role="tablist">
          <button role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>Preview</button>
          <button role="tab" aria-selected={tab === "audit"} onClick={() => setTab("audit")}>Audit record</button>
        </nav>
        {tab === "preview" ? (
          <iframe title="Preview" sandbox="allow-scripts allow-forms" style={{ width: "100%", height: "90%", border: 0 }} />
        ) : (
          <p>Audit record: embeds &lt;agent-authority view="audit"&gt; once its npm package is published.</p>
        )}
      </main>
    </div>
  );
}
