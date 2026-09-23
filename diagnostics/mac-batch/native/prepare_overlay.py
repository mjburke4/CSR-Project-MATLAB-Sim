#!/usr/bin/env python3
from pathlib import Path
import shutil
R=Path(__file__).resolve().parents[2];N=R/'mac_replay/native';O=N/'overlay/ns3';O.mkdir(parents=True,exist_ok=True)
for p in (R/'startup131/environment/csr/model').glob('*.h'):shutil.copy2(p,O/p.name)
shutil.copy2(N/'mac-replay-hooks.h',O/'mac-replay-hooks.h')
p=O/'csr-mac-core.h';s=p.read_text().replace('#include <algorithm>','#include <algorithm>\n#include "csr-opnet-packet-model.h"\n#include "mac-replay-hooks.h"')
def patch(a,b,count=1):
 global s
 assert s.count(a)==count,(a,s.count(a));s=s.replace(a,b)
patch('void SetReceiveState (State state)\n  {','void SetReceiveState (State state)\n  {\n    if (!Mr::internalState) Mr::Input(m_nodeId,"receiver_state",StateName(state));')
patch('void SetSyncPresent (bool present)\n  {','void SetSyncPresent (bool present)\n  {\n    Mr::Input(m_nodeId,"sync",present);')
patch('void NoteReportedActiveNodes (uint32_t n)\n  {','void NoteReportedActiveNodes (uint32_t n)\n  {\n    Mr::Input(m_nodeId,"reported",n);')
s=s.replace('rng->GetInteger (0, slotRange)','Mr::Draw(rng,m_nodeId,0,slotRange)')
p.write_text(s)
p=O/'csr-net-device.h';s=p.read_text()
patch('  CsrAnnotateOpnetEnvelope (frame);','  CsrAnnotateOpnetEnvelope (frame);\n  Mr::Enqueue(m_nodeId,frame,dest,dscp,ackable);')
patch('  uint64_t completedBitmap = ackBitmap | dackBitmap;','  Mr::Input(m_nodeId,"cancel_ack",neighbor,baseSeq,ackBitmap,dackBitmap);\n  uint64_t completedBitmap = ackBitmap | dackBitmap;')
patch('CsrMacCore::CancelQueuedFramesByType (CsrNodeId neighbor, uint8_t type)\n{','CsrMacCore::CancelQueuedFramesByType (CsrNodeId neighbor, uint8_t type)\n{\n  Mr::Input(m_nodeId,"cancel_type",neighbor,unsigned(type));')
patch('  m_activeNodesForPostTx = active;','  Mr::Input(m_nodeId,"active",active);\n  m_activeNodesForPostTx = active;')
patch('  m_mac.NoteHeardFrom (signal.txId, now);','  Mr::Input(m_id,"received",signal.txId,now,decision.pathlossDb,signal.reservedSlot);\n  m_mac.NoteHeardFrom (signal.txId, now);')
patch('  SetReceiveState (State::SEARCH);\n  ActivateTxPreparation (true);','  Mr::internalState=true;\n  SetReceiveState (State::SEARCH);\n  Mr::internalState=false;\n  ActivateTxPreparation (true);')
patch('  NS_ASSERT_MSG (!frames.empty (), "cannot transmit an empty CSR aggregate");','  Mr::Tx(m_id,frames,rateKbps,txPowerDbm,int(preamble),slot,m_mac.GetLastTxOpportunitySlot());\n  NS_ASSERT_MSG (!frames.empty (), "cannot transmit an empty CSR aggregate");')
for signature in ['CsrNetDevice::OnMacTxFinished (bool queuesEmpty)','CsrNetDevice::RefreshDutyState ()','CsrNetDevice::SchedulePendingTxWake ()']:
 patch(signature+'\n{',signature+'\n{\n  if(Mr::replay) return;')
# Explicit replay setup keeps native duty inputs used by IdleRts, but starts no device timers.
patch('  CsrMacCore& GetMac ()','  void ConfigureMacReplay() {m_dutyCycleEnabled=true;m_opnetAlignedDutyCycle=true;m_wakePhaseSec=0.0;}\n\n  CsrMacCore& GetMac ()')
p.write_text(s)
shutil.copy2(R/'receiver_replay/native/capture.cc',N/'capture.cc')
print('Prepared observer and receiver-boundary overlay; original sources unchanged')
