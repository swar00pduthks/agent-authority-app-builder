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
