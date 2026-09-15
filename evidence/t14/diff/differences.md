# Tranche 14: independent ACK-boundary return comparison

Source: owner `t14(2).zip`, candidate `4bb51710031ead9d8d7c6b718fb41fd9224156b46076111e4e9c161aebbcc69f`, compared with its pinned `evidence/tranche-14-edge-reference`. This review re-reads raw CSVs and scheduler traces; it does not execute MATLAB or rerun native code. Reproduce with `python t14a/diff/analyze.py`.

All six cases finish with the same three unique gateway deliveries and empty final ACK/DATA queues. The five controlled timing cases have identical semantic events and full-precision event times to native. Ordinary continuous transport exposes one service-changing timing boundary.

| Case | First ACK sequence/bitmap: MATLAB | Native | Gateway ACK transmissions: MATLAB/native | Updated ACK delay against native |
| --- | --- | --- | --- | --- |
| tie_early | 3 / 7 | 3 / 7 | 5 / 5 | 0 |
| tie_late | 2 / 3 | 2 / 3 | 6 / 6 | 0 |
| before | 3 / 7 | 3 / 7 | 5 / 5 | 0 |
| after | 2 / 3 | 2 / 3 | 6 / 6 | 0 |
| continuous | 2 / 3 | 3 / 7 | 6 / 5 | 26 ms |
| quantized | 3 / 7 | 3 / 7 | 5 / 5 | 0 |

In `continuous`, the actual gateway ACK opportunity is binary64 `400928e15011904b`, or 3.1449609999999999 s. MATLAB transport schedules ingress at `400928e15011904c`, or 3.1449610000000003 s: exactly one ULP, **4.4408920985006262e-16 s**, later. Both round to 3,144,961,000 ns in the nanosecond export. The actual scheduler executes ACK callback ID 61 before ingress ID 59 because time takes precedence over insertion order. Native integer-nanosecond ingress ties the opportunity and runs before ACK service.

This first changes ACK selection at 3.144961 s: MATLAB emits the old receive window (sequence 2/bitmap 3); native emits sequence 3/bitmap 7. MATLAB emits the updated window at **3.170961 s**, a **26,000,000 ns** delay. It also emits one extra final ACK at **3.274961 s** versus native's last ACK at **3.248961 s** and consumes one extra gateway advertisement draw. MATLAB has 35 semantic events/13 draws in this case versus native's 33/12; all other cases have matching row counts and draw usage.

The all-case boundary mismatch has a separate representation component: actual duration is `3f998f1d3ed527e6` (0.024960000000000003 s), while native integer `Time` exports `3f998f1d3ed527e5` (0.02496 s), a **3.4694469519536142e-18 s** difference. This duration field differs in all six cases without changing behavior in five. A binary64 arithmetic probe confirms that substituting native's exported duration alone still yields the same late `...904c` arrival; it is insufficient to fix the service boundary. The local nanosecond conversion case restores arrival to the exact native tie and matching event sequence. It leaves the original duration observation visible.

The 28 reported differences are **11 semantic rows + 6 boundary rows + 9 precision rows + 1 draw row + 1 usage row**. These overlap across comparison views and are not 28 independent defects or an error percentage. Local scheduler IDs are intentionally excluded from cross-runtime equality; native semantic callback IDs are unavailable (zero). MATLAB trace IDs independently establish insertion and execution order in each case.

The isolated diagnostic establishes the boundary mechanism, not improved sender admission or full-network recovery. Source HOP custody is unseeded, transport is controlled successful delivery, and the separately observed 28 ns Tranche 13 startup phase is excluded by fixture epochs. The next useful investigation is a paired default-versus-local-nanosecond transport experiment in the continued-traffic DATA/ACK-loss and relay-recovery harness, measuring actual sender custody, retries, capacity release and latency against the pinned native trace. Preserve the global scheduler and PHY/ECC, keep the default accepted path, and keep the startup phase separately reported until the experiment supports a production change.
