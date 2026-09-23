#!/usr/bin/env python3
import pathlib,shutil,hashlib,json
R=pathlib.Path(__file__).resolve().parents[2]; O=R/'receiver_replay/native/overlay/ns3'; O.mkdir(parents=True,exist_ok=True)
S=R/'startup131/environment/csr/model'
for p in S.glob('*.h'):shutil.copy2(p,O/p.name)
p=O/'csr-phy-model.h'; t=p.read_text();assert t.count('headerBits,\n          ber.headerBer,\n          rng);')==1;assert t.count('payloadBits,\n          ber.payloadBer,\n          rng);')==1;t=t.replace('#include "csr-common.h"','#include "csr-common.h"\n#include "receiver-replay-hooks.h"');t=t.replace('headerBits,\n          ber.headerBer,\n          rng);','headerBits,\n          ber.headerBer,\n          Rpl::Draw(rng, headerBits, ber.headerBer, "header"));');t=t.replace('payloadBits,\n          ber.payloadBer,\n          rng);','payloadBits,\n          ber.payloadBer,\n          Rpl::Draw(rng, payloadBits, ber.payloadBer, "payload"));');p.write_text(t)
p=O/'csr-net-device.h'; t=p.read_text()
for seam in ['  signal.intervalStartSec = now;\n  UpdateSignalNoise (signal);','      double syncThresholdDb = DrawSyncSnrThresholdDb ();','  CsrErrorAllocation allocated = m_phy.AllocateErrors (','  signal.errorAllocation.headerBits += allocated.headerBits;','  m_mac.NotifyPhyTxStart (Seconds (duration));','  m_mac.SetReceiveState (CsrMacCore::State::TRACK);\n\n  std::cout','      WriteDifferentialTrace (rxEvent);','      WriteDifferentialTrace (missEvent);','      m_mac.DeliverRxFrameToUp (segment->Copy (),']:
 assert t.count(seam)==1,(seam,t.count(seam))
t=t.replace('  signal.intervalStartSec = now;\n  UpdateSignalNoise (signal);','  signal.intervalStartSec = now;\n  Rpl::Input(m_id, signal, Simulator::Now().GetNanoSeconds());\n  UpdateSignalNoise (signal);')
t=t.replace('      double syncThresholdDb = DrawSyncSnrThresholdDb ();','      double syncThresholdDb = Rpl::IsReplay(m_id) ? Rpl::SyncValue(incoming.id) : DrawSyncSnrThresholdDb ();\n      Rpl::Sync(m_id, incoming.id, syncThresholdDb);')
t=t.replace('  CsrErrorAllocation allocated = m_phy.AllocateErrors (','  Rpl::Context(m_id, signal.id, signal.intervalStartSec, boundedEndSec);\n  CsrErrorAllocation allocated = m_phy.AllocateErrors (')
t=t.replace('  signal.errorAllocation.headerBits += allocated.headerBits;','  Rpl::ClearContext();\n  signal.errorAllocation.headerBits += allocated.headerBits;')
t=t.replace('  m_mac.NotifyPhyTxStart (Seconds (duration));','  Rpl::OwnTx(m_id, signalId, txId, sequence, payloadBytes, packetBits, rateKbps, txPowerDbm, preamble, slot, ackable, txTime, duration, preambleSec, frameCopies);\n  m_mac.NotifyPhyTxStart (Seconds (duration));')
t=t.replace('  m_mac.SetReceiveState (CsrMacCore::State::TRACK);\n\n  std::cout','  Rpl::Event(m_id, selected->id, "track", selected->txId, selected->sequence, "", "", int(m_mac.GetState()), 2);\n  m_mac.SetReceiveState (CsrMacCore::State::TRACK);\n\n  std::cout')
t=t.replace('      WriteDifferentialTrace (rxEvent);','      Rpl::Event(m_id, signal.id, "signal_end", signal.txId, signal.sequence, decision.success ? "accepted" : "dropped", rxEvent.reason, int(m_mac.GetState()), int(m_mac.GetState()));\n      WriteDifferentialTrace (rxEvent);')
t=t.replace('      WriteDifferentialTrace (missEvent);','      Rpl::Event(m_id, signal.id, "signal_end", signal.txId, signal.sequence, "dropped", missEvent.reason, int(m_mac.GetState()), int(m_mac.GetState()));\n      WriteDifferentialTrace (missEvent);')
t=t.replace('  // OPNET MAC forwards every decoded segment to HOP', '  Rpl::Event(m_id, signal.id, "mac_receive", signal.txId, signal.sequence, "accepted", "accepted", int(m_mac.GetState()), int(m_mac.GetState()));\n  // OPNET MAC forwards every decoded segment to HOP')
t=t.replace('      m_mac.DeliverRxFrameToUp (segment->Copy (),','      CsrHeader replayHeader; segment->PeekHeader(replayHeader);\n      uint16_t replaySequence=replayHeader.GetSeq(); replayHeader.GetSequenceForDestination(m_id,replaySequence);\n      if(replayHeader.IsForDestination(m_id)) Rpl::Event(m_id, signal.id, "hop_ingress", replayHeader.GetSrc(), replaySequence, "accepted", "accepted", int(m_mac.GetState()), int(m_mac.GetState()));\n      m_mac.DeliverRxFrameToUp (segment->Copy (),')
t=t.replace('  m_txPreparationActive = true;', '  m_txPreparationActive = true; Rpl::PrepChanged(m_nodeId, true);').replace('  m_txPreparationActive = false;', '  m_txPreparationActive = false; Rpl::PrepChanged(m_nodeId, false);')
t=t.replace('CsrNetDevice::OnMacTxFinished (bool queuesEmpty)\n{', 'CsrNetDevice::OnMacTxFinished (bool queuesEmpty)\n{\n  queuesEmpty = Rpl::FinishControl(m_id, queuesEmpty, m_activeNodesForPostTx);')
t=t.replace('CsrNetDevice::CancelPostTxWait ()\n{','CsrNetDevice::CancelPostTxWait ()\n{\n  Rpl::CancelWait(m_id);')
p.write_text(t)
p=O/'csr-mac-core.h';t=p.read_text();t=t.replace('#include <algorithm>','#include <algorithm>\nnamespace Rpl { inline bool Preparation(uint32_t, bool); inline void PrepChanged(uint32_t, bool); }');t=t.replace('return m_txPreparationActive;', 'return Rpl::Preparation(m_nodeId, m_txPreparationActive);');t=t.replace('m_txPreparationActive = false;', 'm_txPreparationActive = false; Rpl::PrepChanged(m_nodeId, false);');p.write_text(t)
shutil.copy2(R/'receiver_replay/native/receiver-replay-hooks.h',O/'receiver-replay-hooks.h')
# existing observer timestamp wrapper is observational and source-pinned by prior receipt.
runner=(R/'startup131/diagnostic/observer/csr-opnet-scenario-runner.cc').read_text().replace('  for (const auto &entry : nodes) entry.second.network->StartupObservation("STOP_SNAPSHOT");','')
(O.parent.parent/'capture.cc').write_text(runner)
files=[]
for p in O.glob('*.h'):
 if (S/p.name).exists():files.append(dict(path=p.name,source_sha256=hashlib.sha256((S/p.name).read_bytes()).hexdigest(),overlay_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(O.parent.parent/'overlay-provenance.json').write_text(json.dumps(files,indent=2)+'\n')
