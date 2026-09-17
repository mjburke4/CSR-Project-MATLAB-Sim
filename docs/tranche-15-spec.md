# Tranche 15: paired transport-time policies in the loss/relay benchmark

## Objective

Determine whether the transport-time representation isolated by Tranche 14 materially changes actual sender admission, relay custody and reliable service under continued traffic. Tranche 14 measured a one-ULP binary64 ingress residual that selected the older ACK first, delayed the updated ACK by 26 ms and caused an extra ACK. The femtosecond value describes numerical spacing, not physical timestamp instrumentation.

## Paired experiment

Run all four existing Tranche 13 cases twice: `ok`, `data`, `ack`, and `out`. Each lasts 64 simulated seconds, with the original application generation through 28 seconds and admission polling before 40 seconds. The topology, offered identities, payloads, fixed 128 kbps/+33 dBm profile, prescribed draws, loss policies and final horizon remain unchanged. Each policy still makes its actual loss decisions from that run's emitted aggregates and TX times.

- `continuous`, folder `c`: `tx + duration + propagation`, preserving the accepted fixture's arithmetic and evaluation order.
- `nanoseconds`, folder `n`: independently round the three components to integer nanoseconds, add them, and convert the result back to seconds for the unchanged MATLAB scheduler.

This is a declared local transport conversion over the bounded fixture inputs. It is not a universal reimplementation of ns-3 Time conversion for arbitrary half-nanosecond or extreme floating-point values. It does not snap all scheduled callbacks, change MAC slot arithmetic, or align the separate native startup phase.

The new fixture is mechanically derived from the validated loss fixture, with the timing calculation and observation/export additions explicitly reviewable. The original `lossContract.m`, all production layers and the entire 285-file Tranche 14 source snapshot remain unchanged.

## Evidence

Each branch preserves the original events, draws, usage, transport, terminal and structural-check tables and its case summaries. Additional timing observations retain actual TX time, airtime, propagation, both computed arrival policies, the selected arrival and the difference, as full-precision decimal and binary64 hexadecimal values. Semantic-event precision records retain actual callback times. Text columns are explicit string columns; exact identifiers and ACK/DACK bitmaps retain uint64 precision.

Each case writes its tables and result before branch aggregation. Exceptions and partial artifacts remain visible in the returned ZIP. The independent return checker validates source/reference identities, exact test names, all artifact hashes, structural outcomes, per-case aggregation, timing arithmetic and full-precision encodings.

The continuous branch must reproduce the accepted Tranche 13 observations exactly as parsed table cells. Both policies are compared against the same bound native reference. The historical one-nanosecond comparison is retained as a disclosed legacy report; strict comparisons and explicit outcome metrics determine the new analysis. Positional unmatched-row totals are not an error rate or the sole measure of improvement.

Measure generated/admitted/delivered identities, genuine undelivered applications, actual terminal failures, retries, DATA and ACK/DACK overhead, DACK-held capacity, release timing, admission delay, end-to-end delivery latency and final pending queues. A delivered application with failed sender retirement remains explicitly distinguishable from an undelivered application. Do not infer terminal failure from silence or force all loss cases to deliver.

The retained release callback records identify the node and peer, but not the application ID. Release counts and per-node timing are observable; per-application release latency is not inferred from those records.

## Provenance and decision

Current native main was rechecked at CSR `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, engine `6b5cd24ea80713ce16d88575869aedd6f432bdae`. The original native loss inputs and implementation are unchanged, so the experiment reuses their bound native execution evidence after verification. No new native execution is claimed.

The preserved owner checkpoint is Tranche 14 r2 candidate `4bb51710031ead9d8d7c6b718fb41fd9224156b46076111e4e9c161aebbcc69f`, with 109/109 MATLAB tests and 222/222 focused checks. Its reviewed evidence is included under `evidence/t14`.

The new MATLAB experiment remains pending until the owner returns `t15.zip`. Adopt any production timing change only if the paired outcomes and retained regressions support it. Controlled loss and pre-admitted fixed routes do not validate RF interference, neighbor discovery, routing reconvergence, campus population parity or the excluded battery/supervisory/BBN layers.
