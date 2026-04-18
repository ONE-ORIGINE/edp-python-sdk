# Distributed Runtime

The distributed runtime layer coordinates multiple EDP runtimes through MEP packets.

## Main concerns

- protocol negotiation
- runtime heartbeats
- runtime state export/import
- preflight validation for remote plans
- merge of journal, groups, locks, peers and active executions

## Merge Policy

Iteration 25 introduces an explicit merge report with:
- imported counts
- skipped records
- conflicts
- lock replacements
- execution replacements

The runtime does not assume perfect symmetry. It merges conservatively and preserves conflict details.
