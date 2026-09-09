# Tranche 3 application and security profiles

Tranche 3 makes profile selection explicit so legacy application settings and
security byte accounting cannot silently share one ambiguous default. Scenario
normalization accepts exactly these application profile names:

| `ApplicationProfile` | Configuration contract in this candidate |
| --- | --- |
| `current-send-only` | Current profile label; DSCP values 0 through 255 remain available. |
| `legacy-send-only-no-dscp` | Legacy send-only provenance; every configured traffic DSCP must be zero. |
| `legacy-send-to-from-no-dscp` | Legacy send-to/from provenance; every configured traffic DSCP must be zero. |

An absent or empty value normalizes to `current-send-only`. A scalar MATLAB
string is normalized to a character vector; all other names, spellings and
types fail with `csr:scenario:ApplicationProfile`. At this gate the two legacy
labels enforce the no-DSCP distinction and preserve provenance. Source-exact
application attempt accounting, first-gateway caching and directional traffic
generation remain outside this profile selector until their own differential
tests exist; choosing a label does not claim those behaviors today.

Network-stack scenarios accept exactly one atomic NWK security profile:

```text
behavioral-production-pairwise16-size-only
```

It requires `Radio.EnvelopeProfile='pairwise16-size-only'`. The atomic contract
combines the behavioral neighbor-admission lifecycle with source-backed wire
byte counts. DATA and ACK envelopes gain five modeled bytes. Control sizes are
computed by `csr.nwk.controlWireBytes` and are already complete modeled on-air
sizes; HOP copies them without adding security a second time.
The NWK security-profile value is deliberately an exact character-vector
contract; MATLAB string values and aliases are rejected instead of normalized.

| Control | One-target modeled bytes |
| --- | ---: |
| DISCOVER | 19: standalone Hello 12 + GroupEstablish 7 |
| KEY_REQUEST | 18: standalone Routes 11 + key record 7 |
| KEY_UPDATE | 62: standalone Routes 11 + key record 51 |
| NEIGHBOR_CHECK | 16; 19 for `no_path` |
| ROUTING | 16 plus routing-section bytes |
| SNMP_START / SNMP_DONE | 31: MAC 17 + HOP 8 + fixed SNMP 6 |

Control groups are limited to ten destinations. Their destination/sequence
lists are compatibility-header metadata and add no modeled on-air bytes.
Likewise, SNMP scan node lists remain logical compatibility content; the frozen
source annotates every SNMP frame with the fixed 31-byte envelope. The source
uses standalone Hello/Routes models for the other controls, not an additional
common MAC/HOP wrapper. These counts follow `csr-opnet-envelope.h`,
`CsrHopLayer::SendNeighborCheck`, and `CsrGetOpnetWireSize` at source commit
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. This corrects the earlier candidate's
invented universal wrapper, per-target overhead and variable SNMP byte count.
The only supported profile fails closed for an
unknown profile, an incompatible bare radio envelope, malformed routing bytes,
or an invalid SNMP node list.

The word "security" here describes lifecycle behavior and byte accounting.
Decoded controls are trusted simulation inputs. This tranche implements no
authentication, encryption, real key material or cryptographic replay
protection. The neighbor component's `behavioral-admission` snapshot/payload
label names that narrower local state machine and does not supersede the
scenario-level atomic profile.

An authenticated security-count change calls `Neighbors.securityReset`.
It clears active/check state, received/sent key proof, key-valid flags,
discovery-sequence validity and the failure count. To match the audited source
path, it deliberately preserves an in-flight key-send owner, its scheduled
retry, generation, key request/send timing histories, and overheard-check
validity/timing history. These otherwise surprising retained fields have a
focused regression in `tests/TestNeighbors.m`.

`tests/TestNetworkConfig.m` covers exact application-profile names, legacy
DSCP rejection, the NWK/radio compatibility gate and exported metadata.
`tests/TestControlWireProfile.m` covers exact control sizes, group-size invariance,
DATA/ACK pairwise overhead, no double-counting at HOP and fail-closed inputs.
These are prepared MATLAB tests; they are not execution evidence until the
Tranche 3 runner records an R2025a or R2026a run.
