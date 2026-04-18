# Generation 2 — Semantic Tensor Graph

This document introduces the semantic tensor graph projection used by ENVX in generation 2.

## Core idea

- every node is exported as a **matrix**
- every edge is exported as a **sense vector** and an induced **operator matrix**
- the graph remains canonical, explainable, and reversible

## Node matrix

Each node is represented as a 4 x D matrix:

1. dynamic state row
2. certainty row
3. quality row
4. semantic row

## Edge vector

Each edge keeps:

- relation
- sense vector
- precision
- freshness
- payload

## Operator view

The sense vector induces an operator matrix.
This operator can be used to transform a node row into a semantic message.

This keeps the canonical model independent from a specific ML backend while preparing clean projections for vector, matrix, graph, or future learning systems.
