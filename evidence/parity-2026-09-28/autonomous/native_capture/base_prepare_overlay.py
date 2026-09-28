#!/usr/bin/env python3
"""Construct a hash-bound read-only observer overlay for native seed 132.

The generator never writes to the original CSR source checkout. Its strict
anchors intentionally fail on source drift. `--stock` supports offline patch
validation with the exact-hash reference recovered by recover_reference.py.
"""
import argparse
import hashlib
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
HASHES = {
    'csr-mac-core.h': '64a71ad280ba14ab2b00d5d2b9dac708fabea939dfa385ad62dd73e5e40203e9',
    'csr-net-device.h': '112f9ac73e2ced44a40d6fcc3dc0a8d2cf19996f4f1d52adb0b9a5fbfe103dfb',
    'csr-hop-layer.h': '0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b',
    'csr-nwk-layer.h': 'bc871898c628eec08c82636507cb23cbf6b29d80a3738be18466cb0a9525ecfc',
    'csr-phy-model.h': 'd690b4c572491a9ea8c48735b1726770938b118dcbcd931e92920e602cae18fc',
}


def replace_one(source, before, after):
    count = source.count(before)
    assert count == 1, f'unexpected anchor count {count}: {before[:110]!r}'
    return source.replace(before, after)


def prepare(stock: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    for name, expected in HASHES.items():
        source = stock/name
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest == expected, f'{name}: expected {expected}, got {digest}'
    for source in stock.glob('*.h'):
        shutil.copy2(source, output/source.name)
    for name in ['mac-replay-hooks.h', 'source5-observer.h']:
        shutil.copy2(HERE/name, output/name)

    p = output/'csr-mac-core.h'
    s = p.read_text()
    s = replace_one(s, '#include <algorithm>', '#include <algorithm>\n#include "csr-opnet-packet-model.h"\n#include "mac-replay-hooks.h"\n#include "source5-observer.h"')
    for signature, action in [
        ('SetReceiveState (State state)', 'if (!Mr::internalState) Mr::Input(m_nodeId,"receiver_state",StateName(state));'),
        ('SetSyncPresent (bool present)', 'Mr::Input(m_nodeId,"sync",present);'),
        ('NoteReportedActiveNodes (uint32_t n)', 'Mr::Input(m_nodeId,"reported",n);')]:
        s = replace_one(s, signature+'\n  {', signature+'\n  {\n    '+action)
    s = replace_one(s, 'State previous = m_state;\n        m_state = state;',
                    'State previous = m_state;\n        Sc::Record (m_nodeId, "mac", "receiver_state",\n'
                    '                    {Sc::V ("state_before", StateName (previous)),\n'
                    '                     Sc::V ("state_after", StateName (state)),\n'
                    '                     Sc::V ("mac_ack_depth", m_ackQueue.size ()),\n'
                    '                     Sc::V ("mac_data_depth", m_queue.size ())});\n'
                    '        m_state = state;')
    s = replace_one(s, 'void SetSyncPresent (bool present)\n  {\n    Mr::Input(m_nodeId,"sync",present);\n    m_syncPresent = present;',
                    'void SetSyncPresent (bool present)\n  {\n    Mr::Input(m_nodeId,"sync",present);\n'
                    '    Sc::Record (m_nodeId, "mac", "sync_change",\n'
                    '                {Sc::V ("state_before", m_syncPresent),\n'
                    '                 Sc::V ("state_after", present)});\n'
                    '    m_syncPresent = present;')
    # Exactly two active historic-profile draws; no commented-out branches.
    assert s.count('rng->GetInteger (0, slotRange)') == 2
    s = s.replace('rng->GetInteger (0, slotRange)', 'Mr::Draw(rng,m_nodeId,0,slotRange)')
    p.write_text(s)

    p = output/'csr-net-device.h'
    s = p.read_text()
    s = replace_one(s, '    m_mac.SetDevice (this);\n  }',
                    '    m_mac.SetDevice (this);\n'
                    '    if (m_id == 4)\n'
                    '      { Simulator::Schedule (Seconds (300.0),\n'
                    '                             &CsrNetDevice::RecordSource5Boundary, this); }\n'
                    '  }')
    s = replace_one(s, '  CsrMacCore& GetMac ()\n  {',
                    '  void RecordSource5Boundary ()\n'
                    '  {\n'
                    '    std::ostringstream active;\n'
                    '    for (const auto &[signalId, signal] : m_rxSignals)\n'
                    '      { if (active.tellp () > 0) { active << ","; } active << signalId; }\n'
                    '    Sc::Record (m_id, "phy", "boundary_state",\n'
                    '      {Sc::V ("state_before", CsrMacCore::StateName (m_mac.GetState ())),\n'
                    '       Sc::V ("rx_signal_count", m_rxSignals.size ()),\n'
                    '       Sc::V ("rx_signal_ids", active.str ()),\n'
                    '       Sc::V ("tracked_id", m_trackedSignalId),\n'
                    '       Sc::V ("acquisition_pending", m_acquisitionEvent.IsPending ()),\n'
                    '       Sc::V ("done_rx_pending", m_doneRxEvent.IsPending ()),\n'
                    '       Sc::V ("signal_wake_pending", m_signalWakeEvent.IsPending ()),\n'
                    '       Sc::V ("pending_tx_wake_pending", m_pendingTxWakeEvent.IsPending ()),\n'
                    '       Sc::V ("periodic_wake_pending", m_opnetPeriodicWakeEvent.IsPending ()),\n'
                    '       Sc::V ("sleep_pending", m_sleepEvent.IsPending ()),\n'
                    '       Sc::V ("post_tx_wait_pending", m_postTxWaitEvent.IsPending ()),\n'
                    '       Sc::V ("post_tx_wait_active", m_postTxWaitActive),\n'
                    '       Sc::V ("force_awake_end_pending", m_forceAwakeEndEvent.IsPending ()),\n'
                    '       Sc::V ("sync_present", m_mac.IsSyncPresent ()),\n'
                    '       Sc::V ("sync_override", m_syncThresholdOverrideDb.has_value ()),\n'
                    '       Sc::V ("uniform_draws_before", Sc::uniformOrdinal[m_id]),\n'
                    '       Sc::V ("normal_draws_before", Sc::normalOrdinal[m_id]),\n'
                    '       Sc::V ("mac_ack_depth", m_mac.GetAckQueuedFrameCount ()),\n'
                    '       Sc::V ("mac_data_depth", m_mac.GetDataQueuedFrameCount ())});\n'
                    '  }\n\n'
                    '  CsrMacCore& GetMac ()\n  {')
    s = replace_one(s, '  CsrAnnotateOpnetEnvelope (frame);',
                    '  CsrAnnotateOpnetEnvelope (frame);\n  Mr::Enqueue(m_nodeId,frame,dest,dscp,ackable);')
    s = replace_one(s, '  uint64_t completedBitmap = ackBitmap | dackBitmap;',
                    '  Mr::Input(m_nodeId,"cancel_ack",neighbor,baseSeq,ackBitmap,dackBitmap);\n'
                    '  uint64_t completedBitmap = ackBitmap | dackBitmap;')
    s = replace_one(s, 'CsrMacCore::CancelQueuedFramesByType (CsrNodeId neighbor, uint8_t type)\n{',
                    'CsrMacCore::CancelQueuedFramesByType (CsrNodeId neighbor, uint8_t type)\n{\n'
                    '  Mr::Input(m_nodeId,"cancel_type",neighbor,unsigned(type));')
    s = replace_one(s, '  m_activeNodesForPostTx = active;',
                    '  Mr::Input(m_nodeId,"active",active);\n  m_activeNodesForPostTx = active;')
    s = replace_one(s, '  m_mac.NoteHeardFrom (signal.txId, now);',
                    '  Mr::Input(m_id,"received",signal.txId,now,decision.pathlossDb,signal.reservedSlot);\n'
                    '  m_mac.NoteHeardFrom (signal.txId, now);')
    s = replace_one(s, '  SetReceiveState (State::SEARCH);\n  ActivateTxPreparation (true);',
                    '  Mr::internalState=true;\n  SetReceiveState (State::SEARCH);\n'
                    '  Mr::internalState=false;\n  ActivateTxPreparation (true);')
    s = replace_one(s, '  std::vector<SelectedTxFrame> selected;\n  uint32_t byteCount = 0;',
                    '  Sc::Record (m_nodeId, "mac",\n'
                    '              m_nodeId == 5 ? "node5_mac_service" : "mac_service",\n'
                    '              {Sc::V ("mac_ack_depth", m_ackQueue.size ()),\n'
                    '               Sc::V ("mac_data_depth", m_queue.size ()),\n'
                    '               Sc::V ("state_before", StateName (m_state)),\n'
                    '               Sc::V ("sync_present", m_syncPresent),\n'
                    '               Sc::V ("tx_holdoff_over", m_txHoldoffOver)});\n'
                    '  std::vector<SelectedTxFrame> selected;\n  uint32_t byteCount = 0;')
    # The native packing stop is the exact ACK-priority/byte-limit decision.
    data_oversize = ('          if (!FitsConcatFrame (entry.frame,\n'
                     '                                rate,\n'
                     '                                byteCount,\n'
                     '                                aggregateRateKbps))\n'
                     '            {\n              packingStopped = true;\n'
                     '              break;\n            }\n\n'
                     '          aggregateRateKbps = std::min (aggregateRateKbps, rate);\n'
                     '          byteCount += CsrGetOpnetWireSize (entry.frame);\n'
                     '          selected.push_back ({entry.frame->Copy (),\n'
                     '                               entry.dest,\n'
                     '                               entry.ackable,')
    s = replace_one(s, data_oversize,
                    data_oversize.replace('              packingStopped = true;',
                     '              Sc::Record (m_nodeId, "mac",\n'
                     '                          m_nodeId == 5 ? "node5_mac_pack_blocked" : "mac_pack_blocked",\n'
                     '                          {Sc::V ("kind", "data"),\n'
                     '                           Sc::V ("peer", entry.dest),\n'
                     '                           Sc::V ("mac_ack_depth", m_ackQueue.size ()),\n'
                     '                           Sc::V ("mac_data_depth", m_queue.size ()),\n'
                     '                           Sc::V ("aggregate_bytes", byteCount),\n'
                     '                           Sc::V ("candidate_bytes", CsrGetOpnetWireSize (entry.frame)),\n'
                     '                           Sc::V ("candidate_rate", rate),\n'
                     '                           Sc::V ("aggregate_rate", aggregateRateKbps)});\n'
                     '              packingStopped = true;', 1))
    s = replace_one(s, '  NS_ASSERT_MSG (!frames.empty (), "cannot transmit an empty CSR aggregate");',
                    '  Mr::Tx(m_id,frames,rateKbps,txPowerDbm,int(preamble),slot,m_mac.GetLastTxOpportunitySlot());\n'
                    '  NS_ASSERT_MSG (!frames.empty (), "cannot transmit an empty CSR aggregate");')
    s = replace_one(s, '  uint64_t signalId = (static_cast<uint64_t> (m_id) << 32)\n'
                    '                    | (++m_nextTxSignalId & 0xffffffffULL);',
                    '  uint64_t signalId = (static_cast<uint64_t> (m_id) << 32)\n'
                    '                    | (++m_nextTxSignalId & 0xffffffffULL);\n'
                    '  Sc::Record (m_id, "mac", m_id == 5 ? "node5_mac_tx" : "mac_tx",\n'
                    '              {Sc::V ("tx_id", signalId),\n'
                    '               Sc::V ("peer", hdrOnTx.GetDst ()),\n'
                    '               Sc::V ("sequence", hdrOnTx.GetSeq ()),\n'
                    '               Sc::V ("kind", unsigned (hdrOnTx.GetType ())),\n'
                    '               Sc::V ("segments", frameCopies.size ()),\n'
                    '               Sc::V ("preamble", int (preamble)),\n'
                    '               Sc::V ("duration_sec", duration),\n'
                    '               Sc::V ("mac_ack_depth", m_mac.GetAckQueuedFrameCount ()),\n'
                    '               Sc::V ("mac_data_depth", m_mac.GetDataQueuedFrameCount ())});')
    s = replace_one(s, '  // A direct SendToPeer call and a queued MAC transmission both occupy the',
                    '  for (size_t childIndex = 0; childIndex < frameCopies.size (); ++childIndex)\n'
                    '    {\n'
                    '      CsrHeader childHeader; frameCopies[childIndex]->PeekHeader (childHeader);\n'
                    '      Mr::FrameTag childTag; frameCopies[childIndex]->PeekPacketTag (childTag);\n'
                    '      Sc::Record (m_id, "mac", "mac_tx_child",\n'
                    '                  {Sc::V ("tx_id", signalId),\n'
                    '                   Sc::V ("frame_id", childTag.id),\n'
                    '                   Sc::V ("child_index", childIndex),\n'
                    '                   Sc::V ("kind", unsigned (childHeader.GetType ())),\n'
                    '                   Sc::V ("peer", childHeader.GetDst ()),\n'
                    '                   Sc::V ("sequence", childHeader.GetSeq ()),\n'
                    '                   Sc::V ("wirebytes", CsrGetOpnetWireSize (frameCopies[childIndex]))});\n'
                    '    }\n\n'
                    '  // A direct SendToPeer call and a queued MAC transmission both occupy the')
    s = replace_one(s, '  CsrMacCore& GetMac ()',
                    '  void ConfigureMacReplay() {m_dutyCycleEnabled=true;m_opnetAlignedDutyCycle=true;m_wakePhaseSec=0.0;}\n\n'
                    '  CsrMacCore& GetMac ()')
    for signature in ['CsrNetDevice::OnMacTxFinished (bool queuesEmpty)',
                      'CsrNetDevice::RefreshDutyState ()',
                      'CsrNetDevice::SchedulePendingTxWake ()']:
        s = replace_one(s, signature+'\n{', signature+'\n{\n  if(Mr::replay) return;')
    s = replace_one(s, '  CsrErrorAllocation allocated = m_phy.AllocateErrors (',
                    '  Sc::RxContext drawContext (m_id, signal.id);\n'
                    '  Sc::ErrorIntervalContext errorContext\n'
                    '    (m_id, signal.id, interval.startSec, interval.endSec,\n'
                    '     interval.noisePowerWatts, interval.jsrDb,\n'
                    '     interval.timeOffsetSeconds, interval.collisionCount,\n'
                    '     interval.sameRateInterference);\n'
                    '  CsrErrorAllocation allocated = m_phy.AllocateErrors (')
    s = replace_one(s, '  RxSignal &incoming = it->second;\n\n  std::vector<RxSignal *> previousSignals;',
                    '  RxSignal &incoming = it->second;\n'
                    '  Sc::Record (m_id, "phy", "rx_signal_arrival",\n'
                    '              {Sc::V ("tx_id", incoming.id), Sc::V ("peer", incoming.txId),\n'
                    '               Sc::V ("sequence", incoming.sequence),\n'
                    '               Sc::V ("state_before", CsrMacCore::StateName (m_mac.GetState ())),\n'
                    '               Sc::V ("prior_signals", m_rxSignals.size () - 1),\n'
                    '               Sc::V ("tracked_id", m_trackedSignalId),\n'
                    '               Sc::V ("prior_sync", hadSync),\n'
                    '               Sc::V ("preamble", int (incoming.preamble)),\n'
                    '               Sc::V ("start_sec", incoming.startSec),\n'
                    '               Sc::V ("end_sec", incoming.endSec),\n'
                    '               Sc::V ("rx_power_dbm", incoming.rxPowerDbm),\n'
                    '               Sc::V ("snr_db", incoming.snrDb)});\n\n'
                    '  std::vector<RxSignal *> previousSignals;')
    s = replace_one(s, '      double syncThresholdDb = DrawSyncSnrThresholdDb ();',
                    '      Sc::RxContext drawContext (m_id, incoming.id);\n'
                    '      double syncThresholdDb = DrawSyncSnrThresholdDb ();\n'
                    '      Sc::Record (m_id, "phy", "rx_sync_gate",\n'
                    '                  {Sc::V ("tx_id", incoming.id),\n'
                    '                   Sc::V ("peer", incoming.txId),\n'
                    '                   Sc::V ("sync_threshold_db", syncThresholdDb),\n'
                    '                   Sc::V ("snr_db", incoming.snrDb),\n'
                    '                   Sc::V ("channel_matched", incoming.frontEnd.channelMatched)});')
    s = replace_one(s, '  return m_syncThresholdRng->GetValue (\n    profile.syncSnrThresholdDb,\n    profile.syncSnrThresholdVarianceDb2);',
                    '  return Sc::Normal (m_syncThresholdRng,\n'
                    '    profile.syncSnrThresholdDb,\n'
                    '    profile.syncSnrThresholdVarianceDb2);')
    s = replace_one(s, '  it->second.preambleActive = false;',
                    '  Sc::Record (m_id, "phy", "rx_preamble_end",\n'
                    '              {Sc::V ("tx_id", signalId),\n'
                    '               Sc::V ("peer", it->second.txId),\n'
                    '               Sc::V ("state_before", CsrMacCore::StateName (m_mac.GetState ())),\n'
                    '               Sc::V ("tracked_id", m_trackedSignalId)});\n'
                    '  it->second.preambleActive = false;')
    s = replace_one(s, '  RxSignal *selected = candidates.front ();',
                    '  for (const RxSignal *candidate : candidates)\n'
                    '    { Sc::Record (m_id, "phy", "rx_acquisition_candidate",\n'
                    '        {Sc::V ("tx_id", candidate->id),\n'
                    '         Sc::V ("peer", candidate->txId),\n'
                    '         Sc::V ("rx_power_dbm", candidate->rxPowerDbm),\n'
                    '         Sc::V ("start_sec", candidate->startSec)}); }\n'
                    '  RxSignal *selected = candidates.front ();')
    s = replace_one(s, '  // Snapshot the receiver-global br_inoise state through the exact',
                    '  Sc::Record (m_id, "phy", "rx_acquire",\n'
                    '              {Sc::V ("tx_id", selected->id),\n'
                    '               Sc::V ("peer", selected->txId),\n'
                    '               Sc::V ("candidates", candidates.size ()),\n'
                    '               Sc::V ("state_before", CsrMacCore::StateName (m_mac.GetState ())),\n'
                    '               Sc::V ("tracked_id_before", m_trackedSignalId)});\n\n'
                    '  // Snapshot the receiver-global br_inoise state through the exact')
    s = replace_one(s, '      m_lastRxDecision = decision;',
                    '      Sc::Record (m_id, "phy", "rx_phy_decision",\n'
                    '                  {Sc::V ("tx_id", signal.id),\n'
                    '                   Sc::V ("peer", signal.txId),\n'
                    '                   Sc::V ("sequence", signal.sequence),\n'
                    '                   Sc::V ("outcome", decision.success),\n'
                    '                   Sc::V ("state_before", CsrMacCore::StateName (m_mac.GetState ())),\n'
                    '                   Sc::V ("collision_count", signal.collisionCount),\n'
                    '                   Sc::V ("rejected", signal.rejected),\n'
                    '                   Sc::V ("header_errors", decision.headerErrors),\n'
                    '                   Sc::V ("payload_errors", decision.payloadErrors),\n'
                    '                   Sc::V ("snr_db", decision.snrDb)});\n'
                    '      if (m_id == 4 && !decision.success)\n'
                    '        { for (const auto &childPacket : signal.frames)\n'
                    '            { CsrHeader child; childPacket->PeekHeader (child);\n'
                    '              if (child.GetType () == CSR_PKT_ACK)\n'
                    '                { Sc::Record (m_id, "phy", "node4_ack_drop",\n'
                    '                    {Sc::V ("peer", signal.txId), Sc::V ("tx_id", signal.id),\n'
                    '                     Sc::V ("sequence", child.GetSeq ()),\n'
                    '                     Sc::V ("reason", decision.eccDropped ? "ecc" :\n'
                    '                      (signal.collided ? "collision" : "phy_or_state"))}); }\n'
                    '            }\n'
                    '        }\n'
                    '      m_lastRxDecision = decision;')
    s = replace_one(s, '      if (signal.missedByState)\n        {\n          m_rxMissCount++;',
                    '      Sc::Record (m_id, "phy", "rx_prior_stage",\n'
                    '                  {Sc::V ("tx_id", signal.id),\n'
                    '                   Sc::V ("peer", signal.txId),\n'
                    '                   Sc::V ("sequence", signal.sequence),\n'
                    '                   Sc::V ("state_before", CsrMacCore::StateName (m_mac.GetState ())),\n'
                    '                   Sc::V ("tracked_id", m_trackedSignalId),\n'
                    '                   Sc::V ("rejected", signal.rejected),\n'
                    '                   Sc::V ("missed_by_state", signal.missedByState)});\n'
                    '      if (m_id == 4)\n'
                    '        { for (const auto &childPacket : signal.frames)\n'
                    '            { CsrHeader child; childPacket->PeekHeader (child);\n'
                    '              if (child.GetType () == CSR_PKT_ACK)\n'
                    '                { Sc::Record (m_id, "phy", "node4_ack_drop",\n'
                    '                    {Sc::V ("peer", signal.txId), Sc::V ("tx_id", signal.id),\n'
                    '                     Sc::V ("sequence", child.GetSeq ()),\n'
                    '                     Sc::V ("reason", m_mac.GetState () == CsrMacCore::State::TX\n'
                    '                        ? "half_duplex" : "prior_stage")}); }\n'
                    '            }\n'
                    '        }\n'
                    '      if (signal.missedByState)\n        {\n          m_rxMissCount++;')
    s = replace_one(s, '  for (const auto &segment : signal.frames)\n    {\n      m_mac.DeliverRxFrameToUp (segment->Copy (),',
                    '  for (const auto &segment : signal.frames)\n    {\n'
                    '      CsrHeader child; segment->PeekHeader (child);\n'
                    '      Mr::FrameTag childTag; segment->PeekPacketTag (childTag);\n'
                    '      Sc::Record (m_id, "phy", "rx_child",\n'
                    '                  {Sc::V ("tx_id", signal.id),\n'
                    '                   Sc::V ("peer", signal.txId),\n'
                    '                   Sc::V ("frame_id", childTag.id),\n'
                    '                   Sc::V ("sequence", child.GetSeq ()),\n'
                    '                   Sc::V ("source", child.GetSrc ()),\n'
                    '                   Sc::V ("destination", child.GetDst ()),\n'
                    '                   Sc::V ("kind", unsigned (child.GetType ())),\n'
                    '                   Sc::V ("wirebytes", CsrGetOpnetWireSize (segment))});\n'
                    '      if (m_id == 4 && child.GetType () == CSR_PKT_ACK)\n'
                    '        { Sc::Record (m_id, "phy", "node4_ack_rx",\n'
                    '            {Sc::V ("peer", signal.txId), Sc::V ("tx_id", signal.id),\n'
                    '             Sc::V ("frame_id", childTag.id),\n'
                    '             Sc::V ("sequence", child.GetSeq ()),\n'
                    '             Sc::V ("outcome", true)}); }\n'
                    '      m_mac.DeliverRxFrameToUp (segment->Copy (),')
    p.write_text(s)

    p = output/'csr-phy-model.h'
    s = p.read_text()
    s = replace_one(s, '#include "csr-common.h"', '#include "csr-common.h"\n#include "source5-observer.h"')
    s = replace_one(s, 'double uniform = rng == nullptr ? 1.0 : rng->GetValue (0.0, 1.0);',
                    'double uniform = Sc::Uniform (rng, 0.0, 1.0, bits, probability);')
    s = replace_one(s,
                    '        uint32_t headerErrors = SampleSourceBinomial (\n'
                    '          headerBits,\n'
                    '          ber.headerBer,\n'
                    '          rng);\n'
                    '        uint32_t payloadErrors = SampleSourceBinomial (\n'
                    '          payloadBits,\n'
                    '          ber.payloadBer,\n'
                    '          rng);',
                    '        uint32_t headerErrors;\n'
                    '        { Sc::DrawSite drawSite ("header", headerBeginSec, headerEndSec);\n'
                    '          headerErrors = SampleSourceBinomial (\n'
                    '            headerBits, ber.headerBer, rng); }\n'
                    '        uint32_t payloadErrors;\n'
                    '        { Sc::DrawSite drawSite ("payload", payloadBeginSec, intervalEndSec);\n'
                    '          payloadErrors = SampleSourceBinomial (\n'
                    '            payloadBits, ber.payloadBer, rng); }')
    p.write_text(s)

    p = output/'csr-hop-layer.h'
    s = p.read_text()
    s = replace_one(s, '#include "csr-common.h"', '#include "csr-common.h"\n#include "source5-observer.h"')
    s = replace_one(s, '    return canSend;\n  }\n\nprivate:',
                    '    Sc::Record (m_nodeId, "hop", m_nodeId == 5 ? "node5_hop_gate" : "hop_gate",\n'
                    '                {Sc::V ("peer", dest),\n'
                    '                 Sc::V ("outcome", canSend),\n'
                    '                 Sc::V ("pending_data", m_pendingDataCount),\n'
                    '                 Sc::V ("peer_outstanding", e.outstanding),\n'
                    '                 Sc::V ("peer_threshold", e.threshold),\n'
                    '                 Sc::V ("global_allowed", nodeCanSend),\n'
                    '                 Sc::V ("neighbor_allowed", neighborCanSend)});\n'
                    '    return canSend;\n  }\n\nprivate:')
    s = replace_one(s, '      m_pendingDataCount++;\n\n      std::cout << "[HOP " << m_nodeId',
                    '      m_pendingDataCount++;\n'
                    '      CsrDifferentialAppTag source5AppTag;\n'
                    '      const bool source5HasTag = payload->PeekPacketTag (source5AppTag);\n'
                    '      CsrNetHeader source5NwkHeader;\n'
                    '      const bool source5HasHeader = payload->PeekHeader (source5NwkHeader);\n'
                    '      Sc::Record (m_nodeId, "hop", m_nodeId == 5 ? "node5_hop_admit" : "hop_admit",\n'
                    '                  {Sc::V ("peer", dst), Sc::V ("sequence", seq),\n'
                    '                   Sc::V ("app_source", source5HasHeader ? source5NwkHeader.GetSrc () : 0),\n'
                    '                   Sc::V ("app_sequence", source5HasTag ? source5AppTag.GetSequence () : 0),\n'
                    '                   Sc::V ("pending_data", m_pendingDataCount),\n'
                    '                   Sc::V ("peer_outstanding", fc.outstanding),\n'
                    '                   Sc::V ("peer_threshold", fc.threshold),\n'
                    '                   Sc::V ("resend_depth_before", m_resendQueue.size ())});\n\n'
                    '      std::cout << "[HOP " << m_nodeId')
    s = replace_one(s, '      WriteDifferentialAdmissionTrace (completionEvent);\n    }\n\n  for (auto it = m_resendQueue.begin ();',
                    '      WriteDifferentialAdmissionTrace (completionEvent);\n    }\n'
                    '  Sc::Record (m_nodeId, "hop", m_nodeId == 5 ? "node5_hop_feedback" : "hop_feedback",\n'
                    '              {Sc::V ("peer", entry->dest),\n'
                    '               Sc::V ("app_source", completionNetworkSource),\n'
                    '               Sc::V ("app_sequence", completionAppSequenceValid ? completionAppTag.GetSequence () : 0),\n'
                    '               Sc::V ("sequence", seq), Sc::V ("reason", "ack"),\n'
                    '               Sc::V ("pending_data", m_pendingDataCount),\n'
                    '               Sc::V ("peer_outstanding", GetOutstandingDataCount (entry->dest)),\n'
                    '               Sc::V ("resend_depth_before", m_resendQueue.size ())});\n\n'
                    '  for (auto it = m_resendQueue.begin ();')
    s = replace_one(s, '              WriteDifferentialAdmissionTrace (releaseEvent);\n            }\n\n          // Legacy check_dack() schedules',
                    '              WriteDifferentialAdmissionTrace (releaseEvent);\n            }\n'
                    '          Sc::Record (m_nodeId, "hop", m_nodeId == 5 ? "node5_hop_feedback" : "hop_feedback",\n'
                    '                      {Sc::V ("peer", it->dest),\n'
                    '                       Sc::V ("app_source", it->networkSource),\n'
                    '                       Sc::V ("app_sequence", capacityAppSequenceValid ? capacityAppTag.GetSequence () : 0),\n'
                    '                       Sc::V ("sequence", it->seq),\n'
                    '                       Sc::V ("reason", "dack_expiry"),\n'
                    '                       Sc::V ("pending_data", m_pendingDataCount),\n'
                    '                       Sc::V ("peer_outstanding", fc.outstanding)});\n\n'
                    '          // Legacy check_dack() schedules')
    s = replace_one(s, '      WriteDifferentialAdmissionTrace (completionEvent);\n    }\n}\n\nvoid\nCsrHopLayer::EnqueueResend',
                    '      WriteDifferentialAdmissionTrace (completionEvent);\n    }\n'
                    '  Sc::Record (m_nodeId, "hop", m_nodeId == 5 ? "node5_hop_feedback" : "hop_feedback",\n'
                    '              {Sc::V ("peer", de.dest),\n'
                    '               Sc::V ("app_source", completionNetworkSource),\n'
                    '               Sc::V ("app_sequence", completionAppSequenceValid ? completionAppTag.GetSequence () : 0),\n'
                    '               Sc::V ("sequence", de.seq), Sc::V ("reason", "dack"),\n'
                    '               Sc::V ("pending_data", m_pendingDataCount),\n'
                    '               Sc::V ("peer_outstanding", fc.outstanding),\n'
                    '               Sc::V ("dack_hold_sec", holdTime.GetSeconds ())});\n'
                    '}\n\nvoid\nCsrHopLayer::EnqueueResend')
    s = replace_one(s, '              WriteDifferentialAdmissionTrace (completionEvent);\n            }\n\n          it = m_resendQueue.erase (it);',
                    '              WriteDifferentialAdmissionTrace (completionEvent);\n            }\n'
                    '          Sc::Record (m_nodeId, "hop", m_nodeId == 5 ? "node5_hop_feedback" : "hop_feedback",\n'
                    '                      {Sc::V ("peer", e.dest),\n'
                    '                       Sc::V ("app_source", e.networkSource),\n'
                    '                       Sc::V ("app_sequence", timeoutAppSequenceValid ? timeoutAppTag.GetSequence () : 0),\n'
                    '                       Sc::V ("sequence", e.seq), Sc::V ("reason", "no_ack"),\n'
                    '                       Sc::V ("pending_data", m_pendingDataCount),\n'
                    '                       Sc::V ("peer_outstanding", GetOutstandingDataCount (e.dest)),\n'
                    '                       Sc::V ("resend_depth_before", m_resendQueue.size ())});\n\n'
                    '          it = m_resendQueue.erase (it);')
    p.write_text(s)

    p = output/'csr-nwk-layer.h'
    s = p.read_text()
    s = replace_one(s, '#include "csr-common.h"', '#include "csr-common.h"\n#include "source5-observer.h"')
    s = replace_one(s, '    // br_nwk.proc_app_pk() writes the post-insertion queue size',
                    '    CsrDifferentialAppTag source5Tag;\n'
                    '    const bool source5HasTag = e.payload->PeekPacketTag (source5Tag);\n'
                    '    Sc::Record (m_nodeId, "nwk", m_nodeId == 5 ? "node5_nwk_submit" : "nwk_submit",\n'
                    '                {Sc::V ("app_source", e.nwkSrc),\n'
                    '                 Sc::V ("app_sequence", source5HasTag ? source5Tag.GetSequence () : 0),\n'
                    '                 Sc::V ("destination", e.nwkDst),\n'
                    '                 Sc::V ("nwk_waiting", m_nwkQueue.size ()),\n'
                    '                 Sc::V ("nsdp_count", nsdp.count)});\n\n'
                    '    // br_nwk.proc_app_pk() writes the post-insertion queue size')
    s = replace_one(s, '        // br_nwk.proc_hop_pk() writes the post-insertion queue size',
                    '        CsrDifferentialAppTag source5RelayTag;\n'
                    '        const bool source5RelayHasTag = e.payload->PeekPacketTag (source5RelayTag);\n'
                    '        Sc::Record (m_nodeId, "nwk", m_nodeId == 5 ? "node5_relay_rx" : "relay_rx",\n'
                    '                    {Sc::V ("peer", hopSrc),\n'
                    '                     Sc::V ("app_source", e.nwkSrc),\n'
                    '                     Sc::V ("app_sequence", source5RelayHasTag ? source5RelayTag.GetSequence () : 0),\n'
                    '                     Sc::V ("destination", e.nwkDst),\n'
                    '                     Sc::V ("nwk_waiting", m_nwkQueue.size ()),\n'
                    '                     Sc::V ("nsdp_count", nsdp.count)});\n\n'
                    '        // br_nwk.proc_hop_pk() writes the post-insertion queue size')
    s = replace_one(s, '    // Legacy check_nwk_queue() scans the complete priority queue.',
                    '    Sc::Record (m_nodeId, "nwk", m_nodeId == 5 ? "node5_nwk_scan" : "nwk_scan",\n'
                    '                {Sc::V ("nwk_waiting", m_nwkQueue.size ()),\n'
                    '                 Sc::V ("pending_data", m_hop->GetPendingDataCount ()),\n'
                    '                 Sc::V ("resend_depth", m_hop->GetResendQueueSize ())});\n\n'
                    '    // Legacy check_nwk_queue() scans the complete priority queue.')
    s = replace_one(s, '        const bool canSendToHop = m_hop->CanSendToHop (hopDest);',
                    '        const bool canSendToHop = m_hop->CanSendToHop (hopDest);\n'
                    '        const auto source5Gate = m_hop->GetDataAdmissionSnapshot (hopDest);\n'
                    '        CsrDifferentialAppTag source5GateTag;\n'
                    '        const bool source5HasGateTag = it->payload->PeekPacketTag (source5GateTag);\n'
                    '        Sc::Record (m_nodeId, "nwk", m_nodeId == 5 ? "node5_nwk_gate" : "nwk_gate",\n'
                    '                    {Sc::V ("peer", hopDest),\n'
                    '                     Sc::V ("app_source", it->nwkSrc),\n'
                    '                     Sc::V ("app_sequence", source5HasGateTag ? source5GateTag.GetSequence () : 0),\n'
                    '                     Sc::V ("destination", it->nwkDst),\n'
                    '                     Sc::V ("outcome", canSendToHop),\n'
                    '                     Sc::V ("pending_data", source5Gate.pendingData),\n'
                    '                     Sc::V ("peer_outstanding", source5Gate.neighborOutstanding),\n'
                    '                     Sc::V ("peer_threshold", source5Gate.neighborThreshold),\n'
                    '                     Sc::V ("nwk_waiting", m_nwkQueue.size ()),\n'
                    '                     Sc::V ("nsdp_count", GetNsdpCount (it->nwkSrc, it->nwkDst)),\n'
                    '                     Sc::V ("route_cost", selectedRoute ? selectedRoute->cost : 0),\n'
                    '                     Sc::V ("used_reverse_route", usedReverseRoute)});')
    p.write_text(s)
    print('Original source hashes verified; observer overlay ready:', output)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock', type=Path, required=True, help='native CSR model source directory')
    ap.add_argument('--output', type=Path, required=True, help='isolated overlay/ns3 directory')
    a = ap.parse_args()
    prepare(a.stock, a.output)
