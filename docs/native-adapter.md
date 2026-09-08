# Optional R2026a native integration

Status: implemented candidate; MATLAB R2026a execution is pending. R2025a
portable execution does not validate these classes or Wireless Network Toolbox.

Tranche 1 contains two deliberately separate integrations:

| Component | What MATLAB owns | What CSR owns | Runtime gate |
|---|---|---|---|
| `Backend = 'wireless-clock'` | Simulation clock, calls to a real `wnet.Node` | Event ordering, all protocol/PHY work, propagation and packet delivery | Native clock tests and controlled scenario equality |
| `csr.sim.native.probePacketTransport` | Node invocation, transmit-buffer pull, relevance checks, custom-channel invocation, packet push | Logical frame, airtime, controlled fixture attenuation/delay, completion accounting | Separate native packet lifecycle test |

The scenario backend does **not** use native packet transport. Its `ClockNode`
never emits or receives packets; the existing CSR channel/SignalEngine remains
the sole RF path. The separate `PacketNode` fixture exercises actual native
packet transport and does not construct a CSR `Simulation` or `SignalEngine`.
This prevents duplicate propagation, duplicated receptions, and a second random
success decision. Connecting that transport to the full CSR SignalEngine is a
follow-on integration gate, not an already completed capability.

## Run and capture evidence

Install/enable Wireless Network Toolbox on the R2026a machine. From the repository
root, in a fresh MATLAB session, run:

```matlab
run_validation
validate_native
```

`validate_native` explicitly fails if the required symbols, license, or execution
are unavailable. It writes logs, test results, runtime version, a native probe,
and a status report to `results/native_validation/`. A passing probe demonstrates
the documented lifecycle only on the actual tested installation. It does not
certify full native CSR transport, interference/ECC integration, or native versus
ns-3 parity.

Use the optional clock with an ordinary scenario:

```matlab
config = csr.scenario.smallNetwork();
config.Backend = 'wireless-clock';
result = csr.runScenario(config);
```

The portable default remains suitable for R2025a. Native subclasses are confined
to `+csr/+sim/+native/` and tests are in `tests/native/`, which the portable runner
must exclude from discovery. Merely placing these package files on the path does
not load `wnet.Node` into portable protocol classes.

## Clock contract and limitations

`NativeScheduler` reuses the portable scheduler heap. Its real native `ClockNode`
drains due CSR callbacks from `run(node,currentTime)` and returns the earliest
remaining event. Equal-time CSR callbacks therefore retain insertion order,
including callback-created events. No zero-node or callback-only behavior is
assumed. `EventScheduler.nextTime()` skips canceled entries and returns `Inf`
when empty. The MathWorks custom-node example uses `Inf` for an idle node.

Construct and run one native scenario at a time: `wirelessNetworkSimulator.init`
resets the shared simulator instance. The adapter detects replacement before
running. Each `NativeScheduler` permits one `run`, matching current CSR Scenario
execution. After a run or exception, create a new scenario; continuation and
exception recovery are not native adapter capabilities. The overall callback
budget still stops event loops. On budget exhaustion the native run is terminal,
so pending-work recovery differs from the reusable portable scheduler.

Callbacks at the simulation horizon must execute through native node invocation.
The adapter checks for missed due events before advancing an empty CSR clock to
the horizon; it will not disguise a native scheduling failure by running pending
work afterward on the portable scheduler.

## Packet boundary and integration follow-up

`wrapPacket` creates the public `wirelessPacket` structure with `Abstraction=true`,
`TechnologyType=wnet.TechnologyType.Custom1`, and the CSR frame in `Data.CSRFrame`.
Native transmitter IDs and 24-bit CSR addresses are separate. The wrapper sets
position, velocity, carrier, bandwidth, power, start time, antenna count, and CSR
airtime. `DirectToDestination=0` ensures the custom channel is exercised.

The controlled probe sends 8 and 500 kbps packets to an addressed receiver and an
overhearer, with a fourth node on another carrier. It checks packet identity,
24-bit CSR IDs, relevance, attenuation, distance delay, completion timing, and
scheduled-action cancellation. Fixed 50 dB attenuation and 915 MHz are interface
fixture choices, not assertions about the authoritative CSR scenario. Completion
means the duration elapsed; the probe has no BER/ECC or MAC success decision.

The full native transport integration should move the SignalEngine's per-peer
receive injection behind the native channel and `pushReceivedPacket` boundary,
while retaining exactly one channel calculation and one CSR error process. It
must include controlled collision and same-time receive/transmit tests before
claiming equivalent observable behavior. Native packet distribution occurs before
scheduled actions, so simply enqueueing transmissions in `scheduleAction` does
not establish correct node wakeup or same-time behavior.

## Official interface evidence

Interfaces checked against MathWorks documentation on 2026-09-08:

- [wnet.Node](https://www.mathworks.com/help/wireless-network/ref/wnet.node-class.html):
  public R2026a custom node, constructor position/name, native ID ownership.
- [Node run](https://www.mathworks.com/help/wireless-network/ref/wnet.node.run.html):
  current time and next absolute invocation time.
- [Custom-node example](https://www.mathworks.com/help/wireless-network/ug/create-and-simulate-wireless-network-of-custom-nodes.html):
  concrete supported lifecycle, buffering, idle `Inf`.
- [Packet pull](https://www.mathworks.com/help/wireless-network/ref/wnet.node.pulltransmittedpacket.html),
  [packet push](https://www.mathworks.com/help/wireless-network/ref/wnet.node.pushreceivedpacket.html),
  [relevance](https://www.mathworks.com/help/wireless-network/ref/wnet.node.ispacketrelevant.html):
  packet structures and receiver channel information.
- [wirelessPacket](https://www.mathworks.com/help/wireless-network/ref/wirelesspacket.html):
  abstracted PHY envelope and channel metadata.
- [Custom channel](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.addchannelmodel.html):
  receiver-info/transmit-packet callback and field ownership.
- [Simulator execution order](https://www.mathworks.com/help/wireless-network/ug/working_of_wireless_network.html):
  node execution, packet distribution, then scheduled actions.
- [Scheduling](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.scheduleaction.html)
  and [cancellation](https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.cancelaction.html):
  explicit one-shot actions in the packet probe.
