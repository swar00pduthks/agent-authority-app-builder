# Governed AI App Builder

An AI app builder for regulated firms on Azure. Business and data teams turn a prompt into a working internal app. It runs inside the customer's own Azure tenant, with Entra sign-in, policy checks before every action, and an audit record a risk team can sign off.

Governance, lineage and the audit record come from [Agent Authority](https://github.com/swar00pduthks/agent-authority), which this product embeds. The contracts between the two products are agreed in Agent Authority's *Joint architecture* section. This repo implements the app builder's side of those contracts and links to them rather than copying them.

> Status: first scaffold. The structure, the governance seams and their tests are in place; the agent's real tools, the sandbox client and the editor UI are stubs.

## Layout

| Path | What it is |
| --- | --- |
| `control-plane/` | FastAPI control plane and our own LangGraph harness (Python 3.12) |
| `shell/` | React + Vite shell: chat pane, preview, embedded `<agent-authority>` views |
| `gateway/` | LiteLLM model gateway config, with Agent Authority's routing and cost callback |
| `sandbox/` | Container image for per-project sandboxes (Azure Container Apps dynamic sessions) |
| `infra/` | Bicep for the one-command install into a customer tenant |
| `scripts/` | Pipeline helpers, including the promotion check |
| `docs/` | Architecture notes and the Agent Authority contract checklist |

## Governance rules this code enforces

- **Policy before every action.** Every tool call asks `POST /api/authority/check`. *Needs approval* pauses the graph with LangGraph's `interrupt()`. The approval card lives in the chat pane, and the approver is recorded.
- **Fail closed.** If Agent Authority can't be reached, the session pauses ("governance unreachable") rather than acting unchecked. Branding is the one exception: it's cosmetic, so it falls back to the defaults.
- **Sticky data classes.** Once a connector result enters a session, its data classes stay with that session. Every model call afterwards carries their union, and a builder can't lower them.
- **One session per build.** `thread_id` is the build session id, so pausing and resuming stay one session.
- **The control plane emits all lineage.** The sandbox is untrusted and never holds an Ingest token.
- **Export closes the chain.** The pull request carries the `agent-authority-session:` marker; the merge webhook records the named human approver. Each generated agent's signed A2A card is registered at export.

## Run the control plane tests

```bash
cd control-plane
pip install -e ".[dev]"
pytest
```

## Licence

Proprietary. All rights reserved. Agent Authority itself is Apache 2.0 and is used as a dependency.
