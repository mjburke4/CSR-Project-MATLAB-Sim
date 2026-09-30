#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-nwk-layer.h"
#include <cstdlib>
#include <iostream>
#include <string>

using namespace ns3;

// A direct public-API component probe. No device, channel, physical traffic,
// Simulator::Run, private-state access, or source modifications are used.
// The unattached MAC retains frames, exposing enqueue counts while its normal
// MaybeScheduleNextTx null-device guard prevents any radio scheduling.
void require(bool yes, const char* what) {
  if (!yes) { std::cerr << "FAIL: " << what << '\n'; std::exit(1); }
}

Ptr<Packet> hello(CsrArlRouteMsgType kind,
                  CsrNeighborCheckType subtype = CsrNeighborCheckType::None) {
  CsrHelloHeader h;
  h.SetNodeId(1); h.SetHelloSeq(1); h.SetNodeType(CsrNodeType::Routable);
  h.SetSpeedKey(8); h.SetRxPowerDbmX10(-1030); h.SetActiveNodes(1);
  h.SetArlRouteMsgType(kind); h.SetNeighborCheckType(subtype);
  if (kind == CsrArlRouteMsgType::Discover) {
    h.SetDiscoverType(CsrDiscoverType::Broadcast); h.SetDiscoverySequence(1);
  }
  auto p = Create<Packet>(); p->AddHeader(h); return p;
}

void run(bool discoveryPending) {
  const std::string name = discoveryPending ? "discovery_active" : "overheard_only";
  std::cout << "CASE_BEGIN " << name << '\n';
  CsrMacCore mac; mac.SetNodeId(5);
  auto hop = CreateObject<CsrHopLayer>(); hop->SetNodeId(5); hop->SetMac(&mac);
  hop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
  auto nwk = CreateObject<CsrNetLayer>(); nwk->SetNodeId(5); nwk->SetHop(hop);
  CsrHopSecurityState peer; peer.SetNodeId(1);
  if (discoveryPending) nwk->ProcessHello(hello(CsrArlRouteMsgType::Discover),1,140.876,-0.900945);

  // Receive an authenticated KeyUpdate through the actual HOP security API.
  auto p=Create<Packet>(); p->AddHeader(peer.BuildKeyUpdate(5));
  CsrHeader h(1,5,1,7,true,false); h.SetType(CSR_PKT_KEY_UPDATE);
  h.SetSecurityCount(peer.GetOwnSecurityCount()); p->AddHeader(h);
  hop->ReceiveFromMac(p,140.876,-0.900945);
  require(hop->HasGroupKeyReceivedFrom(1), "received key not installed");
  require(hop->IsKeyUpdateSendActive(1), "reciprocal key not in flight");

  // Discovery first emits KEY_REQUEST seq1; the reciprocal update is seq2.
  const uint16_t keySeq=discoveryPending ? 2 : 1;
  auto ack=Create<Packet>(); CsrHeader a(1,5,keySeq,7,false,true); ack->AddHeader(a);
  hop->ReceiveFromMac(ack,140.876,-0.900945);
  require(hop->HasGroupKeySentTo(1), "key ACK did not complete sent key");
  require(!nwk->IsArlNeighborActive(1), "key exchange alone admitted peer");
  const uint32_t afterKeys=mac.GetDataQueuedFrameCount();
  std::cout << "CHECKPOINT " << name << " after_key_ack " << afterKeys << '\n';

  // Public NWK HELLO callback models a successfully authenticated first
  // NeighborCheck delivery, independently of PHY and duplicate filtering.
  nwk->ProcessHello(hello(CsrArlRouteMsgType::NeighborCheck,CsrNeighborCheckType::Overheard),1,140.876,-0.900945);
  const uint32_t first=mac.GetDataQueuedFrameCount();
  require(first==afterKeys+1,"first received Overheard must enqueue one distinct check");
  std::cout << "CHECKPOINT " << name << " after_first_overheard " << first << '\n';
  nwk->ProcessHello(hello(CsrArlRouteMsgType::NeighborCheck,CsrNeighborCheckType::Overheard),1,140.876,-0.900945);
  const uint32_t repeated=mac.GetDataQueuedFrameCount();
  require(repeated==first,"active Message/Discovery must prevent another Message; Overheard deadline not due");
  std::cout << "CHECKPOINT " << name << " after_second_overheard " << repeated << '\n';
  std::cout << "CASE_END " << name << " PASS\n";
  Simulator::Destroy();
}

int main() {
  run(false);
  run(true);
  std::cout << "ALL_COMPONENT_CASES_PASS\n";
}
