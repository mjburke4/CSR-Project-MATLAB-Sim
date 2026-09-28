# Control-wire evidence

These files document native packet/component experiments and static source review; they are not additional owner commands. Run only `report = run_autonomous_tests` from the kit root.

The native probe exercised 12 packet/header/envelope cases, including the captured63-byte transmission, compact REQUEST16 versus raw-section REQUEST23, metadata NoPath16 versus a real three-byte body19, and native PHY airtime arithmetic. It ran no full network. Native NoPath sender behavior is source verified; its live sender path was not executed, and the accepted network fixture contains no NoPath.

The compile command refers to the separate pinned native build environment; that environment is not required or bundled in this MATLAB kit. Source pins, fixture hashes and exact candidate review are in the JSON receipts. `routing_sizes.csv` and `size_audit.json` audit the native fixture against the supplied MATLAB return. The MATLAB component review is static; six REQUEST and three NoPath checks await owner runtime execution.
