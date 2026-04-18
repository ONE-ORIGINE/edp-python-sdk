# Generation 2 Agent Layer

This module integrates the strongest ideas from the research agent prototypes into the stable canonical stack without collapsing the canon into an LLM-specific architecture.

## Included
- multi-provider provider abstraction
- circuit breaker
- error budget / graceful degradation
- robust decision parser
- semantic negotiation over ranked actions
- reactive attention map
- contrastive memory
- goal-to-context navigation

## CLI
- `llm config provider=<demo|ollama|openai|anthropic> model=<name> [inject_memory=true] [inject_situation=true] [retries=<n>] [timeout=<s>]`
- `llm status`
- `goal preview <alias> [@iface] [ctx=<name>] :: <natural goal>`
- `goal <alias> [@iface] [ctx=<name>] :: <natural goal>`
