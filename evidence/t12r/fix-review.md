# Independent repair review

Approved for owner MATLAB rerun. The exact repair changes three callback registrations and adds three nested lookup wrappers in `+csr/+validation/relayContract.m`. Both broken NWK queries now resolve the current layer through the shared `runCase` workspace. The HOP capacity query uses the same pattern. Constructors finish before event processing invokes these callbacks.

The repaired tree changes no other MATLAB file, no production capacity thresholds or scheduler behavior, and no relay/clock scenarios or native reference bytes. Existing tests remain unchanged. They are meaningful regression coverage because the original R2025a return demonstrates the integrated relay tests fail at this defect, and successful relay traffic necessarily exercises both live NWK queries.

MATLAB execution was not available to this reviewer. This approval covers the bounded fixture repair and handoff; Tranche 12 structural acceptance remains pending a real owner rerun.
