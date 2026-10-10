# Architecture

Where things are decided:

- **Product, go-to-market, MVP scope:** the [app builder plan](https://claude.ai/artifact/MwkGJb4Dx7Qjwj3nLm6q2R).
- **Joint architecture and every contract with Agent Authority:** the *Joint architecture* section of the [Agent Authority plan](https://claude.ai/code/artifact/a73fa789-5dca-4b59-a197-5c7eec1a61b4). Single source of truth; not copied here.
- **Azure sandbox security:** the Sandbox Platform Blueprint.
- **This file:** how the app builder's own code is put together.

## Request flow

```
shell (React) ──> control plane (FastAPI) ──> LangGraph harness
                                                 │  route ─ draft ─ apply ─ evaluate ─ learn
                                                 │            │        │         │        │
                                     LiteLLM gateway   sandbox tools   judge   catalog (pending)
                                                 │
                         Agent Authority: /check before every tool, /route before every model call,
                         lineage for every step, card at export, merge webhook closes the chain
```

## The harness

| Part | File | What it does | Who has the final say |
| --- | --- | --- | --- |
| Policy gate | `harness/governed.py` | `/check` before every tool; needs-approval becomes `interrupt()`; the approver is the signed-in user | Agent Authority's Cedar policies |
| Router | `harness/router.py` | Scores step complexity and asks for `cost`, `balanced` or `quality`; escalates one tier after each failed attempt | Agent Authority's `/route` picks the model from the permitted set |
| Judge | `harness/judge.py` | Deterministic checks first; a rubric judge only if they pass; missing scores count as zero | Failed tests always win over the judge |
| Learning | `harness/learning.py` | After a clearly good run (score ≥ 0.85), proposes a skill to the catalog as pending | A tenant admin approves it; every use is policy-checked |
| Graph | `harness/graph.py` | Wires the above; draft and apply are separate so an approval resume never repeats a model call | — |

## Failure behaviour

- Agent Authority unreachable: the session pauses ("governance unreachable"). Nothing runs unchecked.
- An unrecognised policy answer is treated as unreachable, not as permission.
- Branding unavailable: the shell uses defaults.
- Three failed attempts: the session ends as `failed` with the eval reasons.

## The connected-apps estate

Every app the builder exports carries an `AppManifest` (`app/estate.py`). The manifest lists what the app reads, what it writes, what interfaces it exposes, which other apps it calls, and which Entra groups can use it. Together the manifests make one estate-wide picture: data flow between apps, dependencies, and access control.

- **Store of record: Agent Authority, not a second database.** The manifest goes into the app's registered card (`params.app`) and into the deploy run's OpenLineage inputs and outputs. The estate is the same graph as the data pipelines, with apps as nodes alongside tables and jobs.
- **Observed, not just declared.** Data inputs come from the connectors the session actually read (`RunContext.record_read`). A builder declares access and interfaces but can't leave out a source the agent used.
- **Checked at export.** An app needs at least one Entra group. An app touching client data or PII can't be open to everyone. Outputs keep the data classes of their inputs. A manifest that fails stops the export.
