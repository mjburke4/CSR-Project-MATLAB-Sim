# Parity investigation status: October 29, 2026

End-to-end autonomous parity is not established. The consequential delivery and
latency target remains +/-20%; controlled agreement does not override autonomous
source-level failures. This update records selected evidence since October 15.
It changes no model, PHY/ECC, acceptance tolerance, or executable entrypoint.

## Controlled results

- **Occupied receiver case, October 22:** the independent actual-result review
  accepted one fixed-input receiver projection: 24 MATLAB checks, 80 ordered
  events, four distribution requests, eight component allocations and four
  normalized callbacks. The earlier signal was acquired and accepted; the target
  arrived while it was tracked and was never acquired. Native `prior_stage` and
  MATLAB `not_acquired` remain different labels, reconciled only using the
  observed state predicates. This is not generalized PHY, MAC or application
  delivery equivalence, nor evidence of autonomous improvement.
- **NWK/HOP capacity fixture, October 27:** the completion receipt reports four
  passing cases (two success-arm and two retry-exhaustion-arm invocations).
  Each retained closure reports engine and launcher exit zero and an empty owned
  Job. The controlled credit/release investigation does not establish autonomous
  parity; its completion receipt explicitly excludes tracing-off/on equivalence.
  The fixture boundary excludes full MAC/radio and authentication equivalence.

## Exact inputs and conditional evidence are different claims

The recovered native reverse-test review reports that exact-probability replay
failed at request 8. A separately named conditional sampled-component comparison
matched the specified admission, application and scalar-transmission projections
over [0,390 s), including the adverse source-8 outcome, while retaining probability
differences. Fractional protocol rows were excluded. That conditional result does not convert the exact-input failure
into a pass. It does not establish no-draw-branch, full-PHY, custody or total-order
equivalence. These are externally reviewed native findings; this documentation
update did not rerun or independently revalidate the native archive.

## Longer certificate: generated, not independently accepted

The October 28 deterministic sampler receipt reports 24,378 draw-taking
components, no simulation and zero RNG distribution calls. Its preserved binary
certificate is 979,216 bytes. The originating attempt nevertheless failed the
startup storage partition guard. The controller exited 1; the outer witness
reports an empty Job. No successful independent validator completion is claimed.

Independent validation of the preserved artifact is pending. It must check every
new outcome against the exact retained PHY join and every one of the 2,814
historical outcomes, together with input, source and payload bindings. A later
artifact-validation pass would not retroactively make the failed run
resource-compliant. Certificates cover draw-taking components only.

## Evidence provenance

The following SHA-256 identifiers bind retained receipts inspected for this
update. The receipts remain outside this public repository because they contain
machine-specific operational information. These identifiers provide provenance,
not a self-contained public reproduction package.

| Retained evidence | SHA-256 |
| --- | --- |
| Occupied receiver independent actual review | `44767be4a9bd916178f253ff8af41037aacee702c9d2ca411672a2c88319e3c1` |
| Four-case capacity completion | `7129c86a1d3fc79e5e900dfa1e87ba2d51ea4106e3799477a023f4f41511aedf` |
| Capacity success arm, first closure | `16931f4ad4cce0271217d8c4bd685264b50b2cbfca1e68f9dfda078ad868105b` |
| Capacity success arm, second closure | `0bbd9ae8aea20bbb42e6de39750a98747bc5e0ba1f2ac017b020b3abea3b19aa` |
| Capacity exhaustion arm, first closure | `1d4f0c7fdb47750d31f96d62a03b65f47fd93d182b89fe990ebe95b22e34737d` |
| Capacity exhaustion arm, second closure | `37a53ed124ca83c832e072aafd708370568f715a4f45911bd8d959aaba0d6b1d` |
| Longer certificate arithmetic receipt | `f21bc9c2b83a5109457b09932a14c6fa87596bd4942c37db525ab33db9b0f737` |
| Preserved longer certificate | `89dc27157f8a2f99465b4d50a7894f38145db383712dd5e29c831c6d3507199e` |
| Failed controller receipt | `ba2c5262ca14c0541a09e0556c06cda643056f9cb512424c2a399507d689829b` |
| Outer exit witness | `6dbf17f8cbf497c3071bba65f3f01a6cadf9fed0bec68262dc827cf948a7dbe9` |

No new simulation or MATLAB test was run for this documentation update. The
earlier autonomous results remain failures or incomplete where previously
classified; no fixed campaign slot is replaced or omitted. Subsequent work must
preserve failed attempts, valid zero outcomes and the distinction between
unpaired stochastic trajectories and controlled common-input comparisons.
