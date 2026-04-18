# Generation 2 — mep_llm separation

This generation makes `mep_llm` the primary home of the agent/LLM layer while keeping `mep_tools.llm_runtime` as a compatibility wrapper.

Goals:
- keep the EDP/MEP/SAVOIR canon independent from providers and LLM volatility
- allow separate packaging and future acceleration of the LLM layer
- preserve backwards compatibility for older imports
