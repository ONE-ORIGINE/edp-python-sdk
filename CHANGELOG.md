# Changelog

## 2.0.0

- release polish for Generation 2 publication readiness
- unified versioning across `pyproject`, package modules and release manifest
- upgraded release channel metadata for stable publishing
- added `edp-build-release` local packaging helper
- strengthened release audit with version consistency checks
- expanded GitHub/PyPI publishing documentation and release checklist
- refreshed README and citation metadata for the Generation 2 stable line

## 2.0.0a10

- specialized native stores for context matrix, learning backend, causal dataset, runtime persistence
- persistent learning backend with record append/save/load and latest projection snapshots
- deeper causal scoring wired into action ranking and impact recording
- CLI: `persist stores`, `load stores`, `show stores`, `show learning backend`, `show score <alias> :: <goal>`
- canonical ENVX exports now include persistent backend projection `S_t`

## 2.0.0a9

- enriched generation 2 contextualizer with explicit `ContextMatrix (M_C)`
- added context-weighted semantic projection and contextualizer explain/history exports
- expanded `ImpactMatrix` into a richer learning surface with action/context profiles and session vectors
- added canonical learning projection export and mathematical body fields `M_C` / `L_t`
- enriched CLI with `show context matrix`, `show learning`, `show learning action`, `show contextualize`, and `show math body`
- fixed `/impact` to read the actual environment impact tracker
- added iteration 9 tests and technical documentation

## 2.0.0a8

- complete green suite
- cleaned caches and archives
- deeper multi-agent negotiation
- collective attention, member alignment, phenomenon pressure and circumstance pressure
- new attention views in the CLI

## 2.0.0a6

- added semantic tensor graph projection for ENVX
- added canonical causal dataset projection
- enriched semantic annotations with epistemic status and source trust
- strengthened generation 2 agent layer attention scaffolding

## 2.0.0a3

- integrated generation 2 agent layer with multi-provider runtime, semantic negotiation and natural goal CLI

## 1.0.0

- freeze of the generation-1 canonical line
- stable canonical ENVX body and release manifests
- GitHub/PyPI publication assets completed
- technical and user-facing documentation completed
- setup.py fallback added for packaging compatibility
