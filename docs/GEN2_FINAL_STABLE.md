# Generation 2 Final Stable

The `2.0.0` line freezes the Generation 2 architecture around five stable pillars:

1. **Canonical ENVX body** with mathematical projection and transport-safe release metadata.
2. **SAVOIR** as the native epistemic layer for certainty, belief, revision and explanation.
3. **Contextualizer + ContextMatrix (`M_C`)** as explicit contextual weighting rather than implicit heuristics only.
4. **Impact Matrix + Learning Projection (`L_t`)** as the bridge from observed effects to reusable priors.
5. **Persistent native stores** for context, learning and causal datasets with merge/reload support.

## Stable invariants

- release metadata tells the truth of the repository
- package modules export the same public version
- the release channel is `stable`
- local build emits verifiable artifacts
- the CLI can inspect learning, scoring and persistent store state

## Stable commands worth checking

```bash
show context matrix
show learning
show learning backend
show score alice :: open a high severity case INC-950
persist stores ./var/ops_gen2
show release
```
