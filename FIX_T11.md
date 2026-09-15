# Tranche 11 repair (r1)

The first R2025a run stopped in all four cases before the first gateway ACK transmission. No MATLAB test classes ran. All 662 recorded service events and 20 contention draws matched the native reference up to truncation, using the declared 1 ns timing tolerance. These partial matches do not establish completed replay parity.

The new diagnostic harness omitted the normal radio-adapter step that fills an ACK's empty transmit power. This repair supplies the fixture's pinned +33 dBm before MAC enqueue, retains explicitly supplied power, and preserves all 124 accepted MATLAB source files. It also keeps exception stacks in the evidence and strengthens the existing ACK/radio assertions. The native reference and replay inputs are unchanged.

## Apply the small patch

Extract **t11fix.zip directly into your existing csr11 folder**, the folder containing `run_tranche11_validation.m`. Allow the included files to replace the matching files. The ZIP has no enclosing directory. Do not extract it into a new subfolder.

Alternatively, extract the complete **csr11r.zip** into a new short folder such as `C:\CSR\csr11r` and use that folder in MATLAB.

In MATLAB, make the chosen package folder current, then run:

```matlab
clear functions
report = run_tranche11_validation;
```

The runner still executes four 8-second cases and 52 focused MATLAB tests. Upload the new **t11.zip** whose path it prints. The previous failed evidence is preserved with this repair, and a new run uses a separate short results directory.

The repaired files passed static checks and independent review. MATLAB execution of this repair remains pending. The prescribed MAC/HOP experiment uses controlled transport and a synthetic HOP admission driver; it does not establish RF, full NWK, or campus parity.
