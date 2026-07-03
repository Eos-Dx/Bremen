# ADR-0002: Twin Product Document Separation

**Status**: Accepted

## Separation policy

Bremen and Aramis are permanently separate forks/products/final deliverables.

## Aramis in Bremen

- Aramis may appear in Bremen only as historical/provenance context (fork origin).
- Aramis is not an active dependency, runtime, shared feature set, API, or configuration target for Bremen.

## Shared technical surface

The only shared technical surface between the two products is the upstream XRD-preprocessing repository.

## Prohibition

- No Aramis-specific architecture, endpoints, or configuration should be added to Bremen as a result of this or any future PR.
