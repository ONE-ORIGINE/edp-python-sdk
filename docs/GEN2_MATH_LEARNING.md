# Generation 2 — Mathematical body + learning projections

This iteration pushes generation 2 beyond interface-level refinements.

## Added

- explicit `ContextMatrix` (`M_C`) in the contextualizer
- context-weighted semantic projection for signals
- contextualizer history and explain/export surface
- richer `ImpactMatrix` with:
  - per-action profiles
  - per-context profiles
  - matrix export
  - session vector
  - learning projection
- canonical ENVX exports now include:
  - `exports.contextualizer`
  - `exports.learning`
  - enriched mathematical body fields `M_C` and `L_t`

## New CLI commands

```bash
show context matrix
show learning
show learning action case.open
show contextualize Main battery 15 unit=%
show math body
```

## Why this matters

Generation 2 now has a stronger mathematical core:

- **contextualization is no longer only rule-driven**
  semantic projections are modulated by a context operator
- **impact is no longer only descriptive**
  it becomes a learning surface over actions, reactions and contexts
- **canonical export is closer to a trainable body**
  because the environment now exposes both contextual operators and learned action surfaces

## Notes

This is still not the final form of native specialized stores.
The goal of this step is to strengthen the mathematical body so that future stores and learning backends have a coherent projection target.
