# MATLAB release compatibility

Documentation checked: 2026-09-08. No MATLAB runtime was available during this assessment.

**Decision:** Tranche 0 uses a deterministic portable MATLAB scheduler and release-independent CSR classes. Build a native R2026a `wnet.Node` adapter in parallel with the Tranche 1 PHY/traffic work. R2025a keeps the portable backend until its installed library's supported integration contract is inspected and exercised. This preserves useful work-machine operation without making newer classes core dependencies.

| Capability | R2025a | R2026a | Port decision |
|---|---|---|---|
| `wirelessNetworkSimulator` | Communications Toolbox Wireless Network Simulation Library add-on | Wireless Network Toolbox | Detect installation; release alone does not establish availability |
| `init`, `run`, `scheduleAction`, `cancelAction` | Existing public APIs | Existing public APIs | Candidate common integration surface, subject to execution |
| Public custom-node base `wnet.Node` | Unavailable | Introduced in R2026a | Optional native adapter; no inheritance in CSR core |
| Public `wirelessPacket` template | Unavailable | Introduced in R2026a | Translate independent CSR packets only at adapter boundary |
| Custom channel callback | Available | Available; schema evolving | Share channel calculations, adapt packet fields |
| Zero-node callback-only simulation | Not established by documentation | Not established by documentation | Probe only; not an implemented or validated backend |
| Portable CSR scheduler/core | Implementation target | Implementation target | Same scenario/configuration format on both releases |

The simulator and scheduling references document the R2026a move from the earlier library. An official R2025a manual demonstrates `wirelessnetworkSupportPackageCheck` followed by `wirelessNetworkSimulator.init`. Sources: [simulator reference](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.html), [scheduling reference](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.scheduleaction.html), [R2025a getting-started manual](https://www.mathworks.com/help/releases/r2025a/pdf_doc/bluetooth/bluetooth_gs.pdf).

## Integration contracts

The documented scheduling surface is:

```matlab
sim = wirelessNetworkSimulator.init;
id = scheduleAction(sim, callbackFcn, userData, absoluteTimeSeconds);
cancelAction(sim, id);
run(sim, durationSeconds);
% Callback signature: callbackFcn(actionID, userData)
```

Positive periodicity schedules repeated actions; zero periodicity means clock-advance callbacks. CSR timers should use explicit one-shot events. Sources: [scheduleAction](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.scheduleaction.html), [cancelAction](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.cancelaction.html).

The planned R2026a native adapter will implement `run(node,currentTime)`, `pullTransmittedPacket(node)`, `pushReceivedPacket(node,packet)`, and `isPacketRelevant(node,packet)`. The first returns the next absolute invocation time. Keep actual CSR addresses separate from `wnet.Node.ID`, which is automatically assigned and privately set. Sources: [wnet.Node](https://www.mathworks.com/help/wireless-network/ref/wnet.node-class.html), [node run](https://www.mathworks.com/help/wireless-network/ref/wnet.node.run.html).

Use `wirelessPacket` with `Abstraction=true` and CSR frame information in its `Data` structure; waveform samples are unnecessary. Set transmission time, duration, power, carrier, bandwidth, antenna count, position, and simulator transmitter ID in the wrapper. Select `wnet.TechnologyType.Custom1` for CSR. Source: [wirelessPacket](https://www.mathworks.com/help/wireless-network/ref/wirelesspacket.html).

Custom channels use `rxPacket = channelFcn(receiverInfo,txPacket)`. R2026a replaces the older `Type` field with `TechnologyType`; contain that difference in the adapter. Source: [addChannelModel](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.addchannelmodel.html).

The native simulator processes nodes and packet distribution before scheduled actions. Do not assume this matches ns-3 ordering for events at equal times. Preserve required CSR ordering internally and compare controlled exchanges across backends. Source: [simulator execution order](https://www.mathworks.com/help/wireless-network/ug/working_of_wireless_network.html).

## Runtime checks

From the repository root, before starting any simulation:

```matlab
addpath(pwd);
report = csr.sim.probeWirelessScheduler();
disp(report);
```

The probe tests zero-node scheduling, a callback-created follow-up event, and cancellation using documented methods. It reports the actual MATLAB release, observations, and any full MATLAB exception. Its status is `supported`, `failed`, or `unavailable`; **`supported` means only that this small probe succeeded on that installation**, not that a CSR wireless adapter exists or that MathWorks guarantees callback-only operation.

Calling `wirelessNetworkSimulator.init` resets any existing wireless simulator instance. Run this probe in a fresh MATLAB session or before creating a scenario. It does not change CSR backend defaults. Preserve the report alongside validation results; test R2025a and R2026a separately. No native integration or MATLAB execution is certified by generated code or static review.
