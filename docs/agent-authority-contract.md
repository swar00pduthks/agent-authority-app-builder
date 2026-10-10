# Agent Authority contract checklist

The app builder's side of each agreed contract, and where it lives in this repo. The
contracts themselves are owned in Agent Authority's *Joint architecture* section.

| Contract | App builder side | Code | State |
| --- | --- | --- | --- |
| Policy decision point | `/check` before every tool call; fail closed | `app/governance.py`, `app/harness/governed.py` | Built, tested with a fake |
| Approvals | `interrupt()` + `Command(resume={"approved", "by"})`; card in the chat pane | `app/main.py`, `shell/src/App.tsx` | Built |
| Session mapping | session id = `thread_id`; control plane emits lineage, sandbox never does | `app/harness/context.py` | Seam in place; emitter next |
| Data classes | project + connector classes, sticky, union on every model call | `app/data_classes.py`, `app/harness/router.py` | Built |
| Cost and routing | preference hint + metadata to LiteLLM; `/route` decides | `app/harness/router.py`, `gateway/` | Hint built; callback to pin |
| Catalog | register own tools at build; learned skills as pending; check before using a skill | `app/harness/learning.py` | Built for skills; own-tool registration next |
| Agent cards | A2A card with the governance extension at export; tools registered | `app/export.py` | Built; Key Vault signing in hardening |
| Human approval | `agent-authority-session:` marker in the PR body | `app/export.py` | Built |
| Promotion check | pipeline step; untested-in-prod blocks, regression warns | `scripts/promotion_check.py` | Waits on Agent Authority gap 11 |
| Branding | read `/branding`, apply under `:root`, defaults on failure | `shell/src/branding.ts` | Built |
| Estate manifest | app reads, writes, exposes, depends on, access; in the card and in OpenLineage I/O | `app/estate.py`, `app/export.py` | Built; proposed to Agent Authority for an estate view |
| Embed | pinned `<agent-authority>` npm package | `shell/` | Waits on npm publish |
| Identity | Entra token validation; role mapping | `app/main.py` (`current_user`) | Next: dev-only stub refuses outside dev |
