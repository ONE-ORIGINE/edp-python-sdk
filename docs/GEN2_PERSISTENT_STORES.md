# Generation 2 — Persistent Native Stores

Generation 2 iteration 10 introduces **native specialized stores** that persist the mathematical and causal body rather than only exporting projections.

## Stores

- `SQLiteContextMatrixStore`
  - persists `M_C` snapshots
  - query latest row weights by context kind
- `SQLiteLearningStore`
  - persists `ImpactRecord` rows with score components
  - stores latest learning projection snapshot
- `SQLiteCausalDatasetStore`
  - persists canonical causal dataset snapshots
  - query by action, correlation, phenomenon category
- `NativeSpecializedStoreSuite`
  - bundles graph, events, runtime, context, learning and dataset backends

## Why this matters

The environment now supports:

- persistence of the contextual operator `M_C`
- persistence of learning projection `L_t`
- persistent causal datasets usable for later training or analysis
- richer causal score signals beyond a fixed success/failure constant

## CLI

```bash
persist stores ./var/ops_gen2
show stores
show learning backend
show score alice :: open a high severity case INC-950
```

## Mathematical note

The canonical body now exposes:

- `M_C`: context operator
- `L_t`: learning projection summary
- `S_t`: persistent backend projection / store summary

This pushes Generation 2 toward a real **learning-ready environment body** instead of a purely in-memory runtime.
