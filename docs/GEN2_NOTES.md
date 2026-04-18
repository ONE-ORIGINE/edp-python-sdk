## v2a8
- deeper group negotiation
- collective attention
- phenomenon/circumstance pressure
- attention inspection commands

# Generation 2 Notes

This snapshot fixes cross-platform path handling issues discovered on Windows and starts extracting the resilient LLM-agent layer from the research prototypes into `mep_tools.llm_runtime`.

Highlights:
- robust path normalization for `source`, `lint`, `compile`, `export envx`, `save sqlite`, `load sqlite`
- portable `/tmp` bootstrap for Windows test environments
- canonical save now creates parent directories safely
- initial `CircuitBreaker`, `RobustDecisionParser`, `SemanticIntelligenceLayer` for provider-backed MEP agents

## 2.0.0a3
- integrated agent/LLM runtime inspired by the research prototypes
- multi-provider provider abstraction (demo / ollama / openai / anthropic)
- semantic negotiation over candidate actions
- reactive attention map and contrastive memory
- natural goal commands in the CLI

- iteration a4 adds semantic tensor graph projection and canonical causal dataset export


## v2a7
- concrete store export/load adapters
- deeper graph/tensor queries
- `mep_llm` becomes the primary agent-layer package, with compatibility wrapper in `mep_tools.llm_runtime`
