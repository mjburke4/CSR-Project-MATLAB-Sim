# Independent T16 runner review

No open blocking finding remains in the reviewed files. This was static inspection; no MATLAB or native simulation was executed.

The current runner correctly treats the original T15 baseline as path/sha256 records, using optional byte checks only for the two declared integration changes. It also binds all current source files except the candidate self-reference. The earlier baseline-schema concern is closed against the hashes recorded in runner.json.

The contract uses stable scalar string columns for combined checks and summaries. Its arguments and fields match the retained exportResearchCase, performanceSummary and benchmarkAggregates interfaces. Short storage keys do not change canonical Config or native case labels.

There are 16 structural checks per run, yielding 192 over 12 runs and 9360 simulated seconds. They require conservation, complete traces and correct timing arithmetic; they do not require continuous traffic to drain at the horizon. Timing-record counts correctly include receiver attempts scheduled beyond that horizon.

Detailed service records use the retained [300,320) observer window; feedback and admission records retain full-run scope. The three scenario tests and nine core tests add twelve methods to the 117 retained methods, giving 129 prepared methods.

The completed-result failure fallback now preserves raw observations if researchSummary rejects a result before normal export. Partial failures remain failures, and the runner packages available evidence before rethrowing. An interrupted simulation cannot supply a fabricated complete result; timing and failure records remain available.

Final candidate/package hashes and actual R2025a execution remain outside this static review and must be checked at freeze and return respectively.
