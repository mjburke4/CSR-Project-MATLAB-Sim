# Receiver timer evidence

Run only `report = run_autonomous_tests` from the kit root. No native build or commands are needed.

The native arithmetic probe and unchanged captured geometry establish the integer-nanosecond scheduling boundary. The MATLAB component preflight uses the unchanged public allocator and real receiver/MAC component callbacks; its execution remains pending until this kit is run. The accepted prior J result remains historical evidence, not a new execution.

K supplements the existing TransportTiming arrival/preamble/end policy with acquisition, the source-confirmed rejected-return 28 ns delay, and paired PHY/MAC transmission completion. It retains MATLAB's PHY-first callback decomposition and uses one deadline for PHY TxUntil and both completion callbacks. Generic MAC after(), raw physical geometry, bit truncation, BER and common-input guards remain unchanged.

Conversion uses integer nanoseconds divided by 1e9. Native GetSeconds differs by one binary64 ULP at 2 of 10,301 captured ticks; neither exception changes any of the 1,542 sampled component counts or 4,070 complete captured interval counts. The rejected-return path has no observed callback in this capture and is covered by source binding and a pure target calculation only.
