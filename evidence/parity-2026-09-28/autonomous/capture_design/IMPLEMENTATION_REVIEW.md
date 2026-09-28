# Independent review of the autonomous test boundary

25 September 2026. Review of the source-bound validation kit and native capture.

## Native reference

The executed native capture reports exact preservation of the canonical [0,330) seed-132 prefix: 48,919 rows and all 30 fields. The new capture includes 928 MAC returned integers, 1,960 actual SYNC threshold samples and 1,542 PHY binomial uniforms. Its scope is all seven campus nodes from time zero.

This reviewer independently compared the new normalized MAC samples against the older accepted fixture. All 928 rows match exactly on time, node, ordinal, inclusive lower/upper bound and returned value (`native_tape_review.json`). Event numbers are intentionally excluded because new observations are interleaved into a shared observer ordinal.

The normalized receiver-history file is a subset containing state, boundary and device timer records. Preserve the full observation TSV for detailed signal/acquisition/interval and control-child joins. Native device timer capture records schedule/cancel with deadlines and callback entry/exit causes; it does not claim universal cross-engine scheduler event-ID equality. Native SYNC values are actual sampled thresholds in dB, not standard-normal samples.

## MATLAB observer transformation

`instrument_observers.py` inserts diagnostics into pristine validation copies of `EventScheduler`, MAC `Layer`, and `SignalEngine`; exact source hashes are required before transformation. The script validates all inputs before writing. Reversing all 35 insertions recovers the original source bytes exactly. `observer_generator_check.json` records these static checks.

The added code snapshots existing scalar/struct state and writes to `ac.Trace.record`. It does not schedule/cancel events or draw random values. Scheduler records preserve local event IDs, deadlines and callback names. MAC records provide state, queue depths, reservations, active/reported population and timer IDs at method boundaries. PHY records include receiver state, SYNC presence, active/tracked signal identity and acquisition/TX timers. Local event IDs are comparison aids within one engine, not a cross-engine identity assumption.

These static checks do not substitute for the owner-run natural prefix gate. The diagnostic case must match the existing MATLAB 6,000-second prefix before the common-input case executes.

## Sampler and runner review

The natural-mode provider uses one original `randi` call for each MAC request, one original `randn` for each stochastic SYNC threshold, and one original `rand` for each eligible binomial sample. Production no-draw branches remain no-draw branches. The PHY allocator adapter leaves the allocation/BER arithmetic in the source-bound production file and changes the sampling call site. The physical-transmission mapping `source * 2^32 + source-transmission ordinal` agrees with the native signal-ID construction; it is an alignment coordinate, not proof that the two transmitted packet contents agree.

The runner starts the full seven-node campus configuration from zero, preserves fixed traffic attempts and all endogenous admissions, and supplies no recorded receiver-state or feedback events. It stops the exact common-input path on an unsupported draw context, preserves the partial trace, and still creates the owner ZIP. A time difference is observed rather than forcibly scheduled or suppressed. These are the correct boundaries for this investigation.

The runner's exact natural prefix comparison covers protocol, PHY and application-admission tables with the same import options and exclusive stop cutoff. It checks omitted-record counters, observer completeness and runtime file binding. The MATLAB runtime remains the execution authority; parser success alone cannot establish runtime dispatch or numeric equivalence.

## Review items sent to the builder

1. Match MAC profile/population/reservation context in addition to draw bounds; identical bounds alone do not establish identical request state.
2. Report expected-but-unused native draw channels, including channels with zero MATLAB use, and distinguish complete consumption from an intentional diagnostic stop.
3. Avoid a broad absolute BER tolerance that would treat large relative changes in very small probabilities as equal; use a tight relative/ULP check and report the exact tolerance.
4. Distinguish run completion from packet/event equivalence or the ±15% network result. A TX ordinal is not an independent packet-content comparison.
5. Avoid serializing `archive_completed=false` into an archive that is subsequently created successfully without explaining that the creation receipt is written afterward.

The builder has implemented MAC profile/active-population/reservation-state checks. Reported population remains diagnostic-only because pinned profile 4 does not use that input. Native channels with zero use are included in the summary, and normal common-case completion requires draw and TX context exhaustion. BER comparison now uses a relative tolerance of 1e-12 and zero absolute tolerance. The runner labels semantic divergence separately from harness errors and keeps numerical network parity false. The archived report no longer contains a misleading false archive-completion flag.

The TX check now compares actual ordered children and selected semantic fields: HOP identity, DATA source/destination and source attempt/flow identity, application size, ACK/DACK masks, grouping, routing section bytes and SNMP command. Capture-local IDs alone are not accepted as packet-content evidence. This is a semantic comparison rather than a byte-for-byte equality claim for every raw compatibility envelope. Native REQUEST compatibility headers are explicitly normalized to the equivalent ARL REQUEST section; actual serialized bytes remain in the evidence.

The builder also separated requested and consumed draw counts: a rejected request is no longer counted as an injected native variate. Application-generation times are recorded separately from source attempt/flow identity and are not used as a time-only semantic stop. The previously discussed approximately 28-ns offset belongs to HOP admission/enqueue, not application generation.

## Full final-model source check

`check_final_transform.py` was rerun after the builder froze the model source. It reversed every sampler/export edit recorded in `source_transform.json`, then reversed the passive observer insertions. **All 99 model artifacts recover exactly to the original baseline bytes; 94 are unchanged in the kit and five contain declared validation transformations.** The corresponding hashes and edit counts are in `final_transform_review.json`. This covers the combined observer and sampler/export model transformation, not just the observer-only generator. Helper classes, runner and fixtures are bound separately by the kit manifest.

No production algorithm correction is recommended by this review. The MATLAB runtime result remains pending and the ±15% network target remains unmet.
