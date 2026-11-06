# Seven-node scenario

![Seven-node campus-multihop scenario with node positions to scale, neighbor-pair distances in kilometres, and reconstructed nominal link rates](figures/seven-node-scenario.png)

The plot shows the saved `blue_radio_campus-multihop` geometry and the frozen seed-137 neighbor snapshot.

- Node positions are to scale in simulation X/Y coordinates, in kilometres. These are not latitude/longitude coordinates.
- Distances label the straight-line separation between nodes, rounded to 0.001 km. All nodes have a height of 1 m.
- Node 1 is the gateway. The other node IDs are 2, 3, 4, 5, 7 and 8. The saved numbering is preserved; this snapshot has no node 6.
- The seven lines represent reported neighbor pairs in this snapshot. They do not imply permanent connectivity or guaranteed packet delivery.
- The 3–5 link is curved only for legibility, to separate it from the 3–1–5 links. Its labelled 5.749 km distance is the straight-line separation, not the length of the drawn curve.

## Link-rate labels

All seven plotted pairs (1–3, 1–5, 5–4, 4–2, 2–8, 8–7 and 3–5) have a reconstructed model-selected nominal rate of **8 kb/s** for the frozen seed-137 snapshot. These labels come from the saved configuration and frozen rate-selection code, not measured per-packet rate logs. They are not measured throughput or goodput.

The nominal value is the legacy `RateKeyKbps` label. At rate key 8, the PHY timing model uses a four-bit interval of 0.000510 seconds, giving `4 / 0.000510 = 7843.137... bit/s`, or **7.843 kb/s** rounded to three decimals. This timing rate is also model-derived, not a packet measurement.

Frozen source references, pinned to the baseline commit:

- [Radio-option selection](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/blob/25fcedd3dcabd411fd670dbd5b22bcacb1124e83/diagnostics/relay-custody/current-policy/component-adapter/frozen/%2Bac/DiscoveryMembershipNwk.m#L1017-L1053).
- [Link-cost rate selection](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/blob/25fcedd3dcabd411fd670dbd5b22bcacb1124e83/diagnostics/relay-custody/current-policy/component-adapter/frozen/model/%2Bcsr/%2Bnwk/linkCost.m#L23-L47).
- [Nominal key and PHY timing rate](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/blob/25fcedd3dcabd411fd670dbd5b22bcacb1124e83/diagnostics/relay-custody/current-policy/component-adapter/frozen/model/%2Bcsr/%2Bphy/rateDefinition.m#L18-L46).

This is a documentation figure, not a new simulation run or a change to the scenario configuration.
