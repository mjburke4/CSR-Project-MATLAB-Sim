#!/usr/bin/env python3
"""Passive all-node 0--330 s observer built on accepted source5 observer.

Baseline source is hash checked and never modified. Added observers perform no
simulation scheduling, no cancellation, and no RNG calls. All extra events are
diagnostic rows. A complete canonical 30-field prefix gate is mandatory.
"""
from pathlib import Path
import re
from base_prepare_overlay import prepare as base_prepare, replace_one


def prepare(stock, output):
    base_prepare(stock, output)
    p = output / 'source5-observer.h'
    s = p.read_text().replace('#include <fstream>', '#include <fstream>\n#include <functional>')
    s = s.replace('return now >= 300000000000LL && now < 330000000000LL;',
                  'return now >= 0 && now < 330000000000LL;')
    s = s.replace('inline uint64_t ordinal = 0;', '''inline uint64_t ordinal = 0;
inline const char *cause = "unscoped";
struct CauseScope {
  const char *previous;
  CauseScope(const char *name):previous(cause){cause=name;}
  ~CauseScope(){cause=previous;}
};
struct Finally {
  std::function<void()> action;
  explicit Finally(std::function<void()> f):action(std::move(f)){}
  ~Finally(){action();}
};''')
    s = s.replace('std::map<std::string, std::string> values (data.begin (), data.end ());',
                  'std::map<std::string, std::string> values (data.begin (), data.end ());\n  values["cause"] = cause;')
    s = s.replace('\\tautonomous132\\t', '\\tautonomous132\\t')
    s = s.replace('\\tsource5_132\\t', '\\tautonomous132\\t')
    # Shared event ordinal: Mr capture and this observer use the same counter.
    p.write_text(s)

    p = output / 'csr-hop-layer.h'
    s = p.read_text()
    start=s.index('CsrHopLayer::SendProtectedDiscovery (Ptr<Packet> discoveryPayload)')
    stop=s.index('CsrHopLayer::SendAuthenticatedRoutingHello',start)
    section=s[start:stop]
    before='  m_mac->EnqueueTxFrame (frame, CSR_BROADCAST_ID, 7, false);'
    section=replace_one(section,before,before+'''
  CsrHelloHeader observedDiscovery;
  const bool observedHasHeader = discoveryPayload->PeekHeader(observedDiscovery);
  NS_ABORT_MSG_IF(!observedHasHeader,"Observer missing DISCOVER metadata");
  Mr::FrameTag observedTag; frame->PeekPacketTag(observedTag);
  std::ostringstream observedPeers;
  for (unsigned i=0;i<observedDiscovery.GetChirpNeighborCount();++i)
    {if(observedPeers.tellp()>0)observedPeers<<";";observedPeers<<observedDiscovery.GetChirpNeighbor(i);}
  Sc::Record(m_nodeId,"hop","discovery_plaintext",
    {Sc::V("frame_id",observedTag.id),
     Sc::V("subtype",static_cast<unsigned>(observedDiscovery.GetDiscoverType())),
     Sc::V("discovery_sequence",observedDiscovery.GetDiscoverySequence()),
     Sc::V("active_peers",observedPeers.str()),
     Sc::V("native_active_nodes",unsigned(observedDiscovery.GetActiveNodes())),
     Sc::V("node_type",static_cast<unsigned>(observedDiscovery.GetNodeType())),
     Sc::V("speed_key",observedDiscovery.GetSpeedKey()),
     Sc::V("s0_dbm",observedDiscovery.GetRxPowerDbmX10()/10.0)});
''')
    s=s[:start]+section+s[stop:]
    p.write_text(s)
    p = output / 'mac-replay-hooks.h'
    s = p.read_text().replace('#pragma once', '#pragma once\n#include "source5-observer.h"')
    s = s.replace('inline uint64_t order=0, frameId=0;',
                  'inline uint64_t &order=Sc::ordinal; inline uint64_t frameId=0;')
    s = replace_one(s,
        'if(Simulator::Now().GetNanoSeconds()>=300000000000LL&&Simulator::Now().GetNanoSeconds()<330000000000LL)',
        'if(Simulator::Now().GetNanoSeconds()>=0&&Simulator::Now().GetNanoSeconds()<330000000000LL)')
    p.write_text(s)

    p = output / 'csr-mac-core.h'
    s = p.read_text()
    anchor = 'int chosenSlot = Mr::Draw(rng,m_nodeId,0,slotRange);'
    assert s.count(anchor) == 2
    s = s.replace(anchor, anchor + '''
        Sc::Record(m_nodeId,"mac","mac_draw",
          {Sc::V("draw",chosenSlot),Sc::V("low",0),Sc::V("high",slotRange),
           Sc::V("draw_ordinal",Mr::ordinals[m_nodeId]),
           Sc::V("active_nodes",activeForSlotting),
           Sc::V("reported_nodes",m_maxReportedActiveNodes),
           Sc::V("reservation_counter",m_txCountdownCounter),
           Sc::V("reservation_slot",m_scheduledTxSlot),
           Sc::V("profile",static_cast<int>(m_slotSelectionProfile)),
           Sc::V("state_before",StateName(m_state)),
           Sc::V("rng_consumed",1)});''')
    s = s.replace('  PickTxSlot (CsrNodeId dest)\n  {',
                  '  PickTxSlot (CsrNodeId dest)\n  {\n    Sc::CauseScope observerCause("CsrMacCore::PickTxSlot");')
    p.write_text(s)

    p = output / 'csr-net-device.h'
    s = p.read_text()
    # The prior bounded observer scheduled one snapshot. Remove it: this
    # capture derives all snapshots from existing native callback boundaries.
    s = replace_one(s, '''    if (m_id == 4)
      { Simulator::Schedule (Seconds (300.0),
                             &CsrNetDevice::RecordSource5Boundary, this); }
''', '')
    state_method = '''  void RecordAutonomousState (const char *phase)
  {
    Sc::Record(m_id,"device","receiver_boundary",
      {Sc::V("phase",phase),
       Sc::V("state_before",CsrMacCore::StateName(m_mac.GetState())),
       Sc::V("sync_present",m_mac.IsSyncPresent()),
       Sc::V("tracked_id",m_trackedSignalId),
       Sc::V("rx_signal_count",m_rxSignals.size()),
       Sc::V("preparation_active",m_mac.IsTxPreparationActive()),
       Sc::V("post_tx_wait_active",m_postTxWaitActive),
       Sc::V("force_awake_until_sec",m_forceAwakeUntilSec),
       Sc::V("reservation_counter",m_mac.GetLocalReservationCounter()),
       Sc::V("mac_ack_depth",m_mac.GetAckQueuedFrameCount()),
       Sc::V("mac_data_depth",m_mac.GetDataQueuedFrameCount())});
  }

  void RecordAutonomousTimer(const char *action,const char *name,const EventId &ev)
  {
    Sc::Record(m_id,"device","timer_lifecycle",
      {Sc::V("action",action),Sc::V("timer",name),
       Sc::V("event_uid",ev.GetUid()),Sc::V("deadline_ns",ev.GetTs()),
       Sc::V("pending",ev.IsPending()),
       Sc::V("state_before",CsrMacCore::StateName(m_mac.GetState()))});
  }

'''
    s = replace_one(s, '  CsrMacCore& GetMac ()', state_method + '  CsrMacCore& GetMac ()')
    # Existing callback entry/exit boundaries, including early returns. Scope
    # destructor only reads state; no simulator event is created.
    names = ['RefreshDutyState','SleepReceiver','WakeForSignal','WakeForPendingTx',
             'OpnetPeriodicWake','ScheduleOpnetPeriodicWake','StartPostTxWait',
             'CancelPostTxWait','PostTxWaitExpired','ScheduleSignalWake',
             'SchedulePendingTxWake','UpdateSyncPresence','ScheduleAcquisition',
             'ReturnToSearchAfterReceive','ReturnRejectedReceiveToSearch',
             'AcquireSignal','EndReceivePreamble','EndReceiveSignal','OnMacTxFinished']
    for name in names:
        pattern = r'(CsrNetDevice::'+name+r'\s*\([^)]*\)\n\{)'
        inject = ('\n  Sc::CauseScope observerCause("CsrNetDevice::'+name+'");'
                  '\n  RecordAutonomousState("enter");'
                  '\n  Sc::Finally observerExit([this]{RecordAutonomousState("exit");});')
        s, count = re.subn(pattern, lambda m: m[0]+inject, s)
        assert count == 1, (name, count)
    # Schedule and cancellation records use returned EventId, without touching
    # its state. All observed fields are native nanosecond/integer values.
    timers = '(?:acquisition|signalWake|pendingTxWake|opnetPeriodicWake|sleep|doneRx|postTxWait|forceAwakeEnd)'
    pattern = r'(m_'+timers+r'Event\s*=\s*Simulator::Schedule\s*\([^;]*;)' 
    def schedule(m):
        name = re.match(r'(m_\w+Event)',m[0])[1]
        return m[0]+'\n  RecordAutonomousTimer("schedule","'+name+'",'+name+');'
    s = re.sub(pattern,schedule,s)
    pattern = r'(Simulator::Cancel \((m_'+timers+r'Event)\);)'
    s = re.sub(pattern,lambda m:'RecordAutonomousTimer("cancel","'+m[2]+'",'+m[2]+');\n      '+m[1],s)
    p.write_text(s)


if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--stock',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    prepare(args.stock,args.output)
