# Technical Architecture

This document describes the generation-1 canonical line of the SDK.

## Layers

1. `edp_sdk.semantics` — vectors, harmony, semantic operators
2. `edp_sdk.contextualizer` — contextual transformation `Ψ`
3. `edp_sdk.savoir` — certainty and belief layers
4. `edp_sdk.core` — environment, contexts, actions, reactions, causal memory
5. `edp_sdk.protocol` — MEP packets, runtime orchestration, distributed execution
6. `edp_sdk.persistence` — JSON and SQLite stores
7. `edp_sdk.canonical` — ENVX canonical body and projections
8. `drone_edp` — drone specialization over the canonical runtime

## Runtime Topology

A `MultiAgentRuntime` exposes:
- agents and their active/accessible contexts
- group orchestration
- delegation, negotiation, consensus
- formal and distributed plans
- leases/locks and execution state

## Canonical Stability

The canonical ENVX body is treated as the non-specialized source of truth.
Vector, matrix and graph projections derive from it but do not replace it.
