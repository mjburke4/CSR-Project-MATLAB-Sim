> Historical repair note: the owner subsequently passed this native import/preflight and accepted-A reuse. The current G/H kit preserves that successful repair unchanged. New candidate runtime validation remains pending.

# Native CSV harness repair

The returned R2025a run completed natural case A at 330 seconds and passed all three exact prefix gates. Native-input case B stopped at 10.01 seconds, before consuming a sample or transmitting a packet, with `MATLAB:string:CannotConvertMissingElementToChar` in `Streams.take`.

`component` describes a PHY header/payload binomial request. It is intentionally empty for all 928 MAC rows and all 1,960 SYNC rows. MATLAB imported those blank cells as missing strings. The old matcher called `char(expected.component)` unconditionally on the first MAC request.

The new `ac.Fixture` importer explicitly types all text/numeric columns, normalizes legitimate optional text blanks to empty strings, and checks required fields by random purpose and packet/control kind. A blank PHY component, MAC state, SYNC mean, DATA lineage, routing section or relevant control subtype remains an error. Empty peer/node/target lists remain valid. Numeric blanks remain NaN and fail required-field checks; they are never replaced with zero. Hexadecimal ACK/DACK bitmaps remain exact strings.

Only the native constructor/import path and native-only matcher region in `ac.Streams` changed. All 99 model files and the natural producer helpers are byte-identical. `TxSignature` itself is unchanged; its optional text consumers receive normalized strings after scoped validation. No RNG samples, traffic offers, admission decisions, receiver states, timers, retries, rates, or protocol thresholds were changed.

The new native-import regression preflight loads both complete fixtures, exercises the original first MAC request with its valid empty component, and checks four malformed required-field rejections. It uses an independent empty scheduler, schedules no callback, consumes no production simulation random stream, and runs no network.

The accepted natural result is reused only after file/source/input hash checks, the same runtime version/release/computer, matching behavioral configuration, and a fresh execution of the unchanged exact three-table comparison. Only the provenance filename `SharedScenario.SourcePath` is canonicalized to allow extraction into a new directory. Every other configuration field is compared after identical JSON roundtripping. A runtime/configuration mismatch causes a fresh natural run. The reusable tables are the actual accepted return, not manufactured expected outputs.

The repaired native-input network run is pending owner MATLAB execution. Neither this harness correction nor accepted natural instrumentation fidelity establishes ±15% network parity.
