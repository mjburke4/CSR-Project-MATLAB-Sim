// Deterministic contracts against unchanged pinned CSR ns-3 source.
// Direct HOP/NWK ingress isolates liveness semantics; this is not a PHY test.
#include "ns3/core-module.h"
#include "ns3/csr-arl-routing-message.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-nwk-layer.h"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace ns3;

namespace
{
constexpr CsrNodeId LOCAL = 1;
constexpr CsrNodeId PEER = 2;
std::ofstream g_csv;
unsigned g_checks = 0;
unsigned g_failed = 0;

void Check(const std::string& name, const std::string& field,
           double actual, double expected)
{
  const bool pass = std::abs(actual - expected) <= 1e-9;
  g_checks++;
  g_failed += !pass;
  g_csv << name << ',' << std::setprecision(12)
        << Simulator::Now().GetSeconds() << ',' << field << ','
        << actual << ',' << expected << ',' << (pass ? 1 : 0) << '\n';
  if (!pass)
    std::cerr << "CONTRACT_FAIL " << name << ' ' << field << " actual="
              << actual << " expected=" << expected << '\n';
}

Ptr<Packet> Hello(bool discovery = false)
{
  CsrHelloHeader hello;
  hello.SetNodeId(PEER);
  hello.SetNodeType(CsrNodeType::Ordinary);
  hello.SetSpeedKey(8);
  hello.SetRxPowerDbmX10(-1050);
  hello.SetActiveNodes(1);
  hello.SetArlRouteMsgType(discovery ? CsrArlRouteMsgType::Discover
                                   : CsrArlRouteMsgType::None);
  if (discovery)
    {
      hello.SetDiscoverType(CsrDiscoverType::Broadcast);
      hello.SetDiscoverySequence(1);
    }
  auto packet = Create<Packet>();
  packet->AddHeader(hello);
  return packet;
}

struct Stack
{
  Ptr<CsrNetDevice> device = CreateObject<CsrNetDevice>(LOCAL);
  Ptr<CsrHopLayer> hop = CreateObject<CsrHopLayer>();
  Ptr<CsrNetLayer> nwk = CreateObject<CsrNetLayer>();

  Stack()
  {
    hop->SetNodeId(LOCAL);
    hop->SetMac(&device->GetMac());
    hop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
    nwk->SetNodeId(LOCAL);
    nwk->SetHop(hop);
    nwk->SetArlNeighborAdmissionEnabled(false);
    nwk->SetDiscoveryResponseEnabled(false);
    nwk->SetAutomaticRoutePropagationEnabled(false);
    nwk->SetRoutingSnapshotResponseEnabled(false);
    // Public NWK ingress seeds an admitted peer with network liveness t=0.
    nwk->ProcessHello(Hello(), PEER, 70.0, 20.0);
    nwk->StartNeighborFreshnessMonitor(Seconds(20), Seconds(2));
  }
};

Ptr<Packet> PassiveFrame(bool acknowledgment, bool overheard)
{
  const CsrNodeId destination = overheard ? 3 : LOCAL;
  auto packet = Create<Packet>(acknowledgment ? 0 : 16);
  if (!acknowledgment)
    packet->AddHeader(CsrNetHeader(PEER, destination, 0));
  CsrHeader outer(PEER, destination, 77, acknowledgment ? 7 : 0,
                  false, acknowledgment);
  outer.SetType(acknowledgment ? CSR_PKT_ACK : CSR_PKT_DATA);
  outer.SetDestType(CSR_DEST_UNICAST);
  outer.SetSpeedKey(8);
  packet->AddHeader(outer);
  return packet;
}

Ptr<Packet> DiscoverFrame()
{
  auto packet = Hello(true);
  CsrHeader outer(PEER, CSR_BROADCAST_ID, 78, 7, false, false);
  outer.SetType(CSR_PKT_DISCOVER);
  outer.SetDestType(CSR_DEST_BROADCAST);
  outer.SetSpeedKey(8);
  packet->AddHeader(outer);
  return packet;
}

Ptr<Packet> RoutingFrame()
{
  CsrArlRoutingMessage::Builder builder;
  std::string error;
  if (!builder.AddUpdate(PEER, 1, 0, 0, {}, &error))
    throw std::runtime_error(error);
  builder.AddFlush();
  std::vector<std::vector<uint8_t>> sections;
  if (!builder.BuildSections(1, sections, &error) || sections.size() != 1)
    throw std::runtime_error("Routing contract must fit one section: " + error);
  auto packet = Create<Packet>(sections[0].data(), sections[0].size());
  CsrHelloHeader hello;
  hello.SetNodeId(PEER);
  hello.SetNodeType(CsrNodeType::Routable);
  hello.SetSpeedKey(8);
  hello.SetRxPowerDbmX10(-1050);
  hello.SetActiveNodes(1);
  hello.SetArlRouteMsgType(CsrArlRouteMsgType::RoutingUpdate);
  hello.SetRoutingSequence(1);
  hello.SetRoutingSection(0);
  hello.SetRoutingTotalSections(1);
  hello.SetRoutingOperation(CsrRoutingOperation::Update);
  packet->AddHeader(hello);
  CsrHeader outer(PEER, LOCAL, 79, 7, false, false);
  outer.SetType(CSR_PKT_ROUTING_CONTROL);
  outer.SetDestType(CSR_DEST_UNICAST);
  outer.SetSpeedKey(8);
  packet->AddHeader(outer);
  return packet;
}

void PassiveCase(const std::string& name, bool ack, bool overheard)
{
  Stack stack;
  Simulator::Schedule(Seconds(19), [&] {
    stack.hop->ReceiveFromMac(PassiveFrame(ack, overheard), 70, 20);
    Check(name, "hop_last_heard", stack.hop->GetNeighborLastHeardSeconds(PEER), 19);
  });
  Simulator::Schedule(Seconds(20.001), [&] {
    Check(name, "active_at_equal_timeout", stack.nwk->IsArlNeighborActive(PEER), 1);
  });
  Simulator::Schedule(Seconds(22.001), [&] {
    Check(name, "active_after_network_expiry", stack.nwk->IsArlNeighborActive(PEER), 0);
    Check(name, "failures_after_expiry",
          stack.nwk->GetSecurityResetStateForTest(PEER).numFailures, 0);
  });
  Simulator::Stop(Seconds(22.01));
  Simulator::Run();
  Simulator::Destroy();
}

void ControlCase(const std::string& name, const std::string& kind, bool duplicate)
{
  Stack stack;
  auto routing = RoutingFrame();
  if (duplicate)
    Simulator::Schedule(Seconds(5), [&] {
      stack.hop->ReceiveFromMac(routing->Copy(), 70, 20);
    });
  Simulator::Schedule(Seconds(19), [&] {
    if (kind == "discover")
      stack.hop->ReceiveFromMac(DiscoverFrame(), 70, 20);
    else if (kind == "routing")
      stack.hop->ReceiveFromMac(routing->Copy(), 70, 20);
    else
      stack.nwk->NoteNeighborCheckSuccess(PEER,
        kind == "obsolete_verify" ? CsrNeighborCheckType::Verify
                                   : CsrNeighborCheckType::Message,
        kind == "obsolete_verify" ? 99 : 0);
  });
  const bool refresh = !duplicate && kind != "obsolete_verify";
  Simulator::Schedule(Seconds(22.001), [&] {
    Check(name, "active_at_22", stack.nwk->IsArlNeighborActive(PEER),
          duplicate || refresh ? 1 : 0);
  });
  const double before = duplicate ? 24.001 : 38.001;
  const double after = duplicate ? 26.001 : 40.001;
  if (refresh || duplicate)
    {
      Simulator::Schedule(Seconds(before), [&] {
        Check(name, "active_before_next_qualifying_expiry", stack.nwk->IsArlNeighborActive(PEER), 1);
      });
      Simulator::Schedule(Seconds(after), [&] {
        Check(name, "active_after_qualifying_expiry", stack.nwk->IsArlNeighborActive(PEER), 0);
      });
    }
  Simulator::Stop(Seconds(after + .01));
  Simulator::Run();
  Simulator::Destroy();
}

void ExpiryRetentionCase()
{
  // No attached HOP is intentional: install source public sentinel ownership
  // without a running radio completing/retrying it before the expiry boundary.
  auto nwk = CreateObject<CsrNetLayer>();
  nwk->SetNodeId(LOCAL);
  nwk->SetAutomaticRoutePropagationEnabled(false);
  nwk->ProcessHello(Hello(), PEER, 70, 20);
  CsrNetLayer::SecurityResetStateForTest before;
  before.discoverySequenceValid = true;
  before.keyUpdateComplete = true;
  before.keyRequestSentValid = true;
  before.keySendComplete = true;
  before.keySendActive = true;
  before.keySendValid = true;
  before.overheardValid = true;
  before.keyRequestDelay = Seconds(11);
  before.keySendDelay = Seconds(13);
  before.overheardDelay = Seconds(17);
  before.numFailures = 9;
  before.admissionRetryPending = true;
  nwk->SetSecurityResetStateForTest(PEER, before);
  nwk->StartNeighborFreshnessMonitor(Seconds(20), Seconds(2));
  Simulator::Schedule(Seconds(22.001), [&] {
    const auto after = nwk->GetSecurityResetStateForTest(PEER);
    const std::string name = "freshness_preserves_key_and_retry_state";
    Check(name, "discovery_sequence_valid", after.discoverySequenceValid, 1);
    Check(name, "received_key", after.keyUpdateComplete, 1);
    Check(name, "key_request_valid", after.keyRequestSentValid, 1);
    Check(name, "sent_key", after.keySendComplete, 1);
    Check(name, "key_send_active", after.keySendActive, 1);
    Check(name, "key_send_valid", after.keySendValid, 1);
    Check(name, "overheard_valid", after.overheardValid, 1);
    Check(name, "key_request_delay", after.keyRequestDelay.GetSeconds(), 11);
    Check(name, "key_send_delay", after.keySendDelay.GetSeconds(), 13);
    Check(name, "overheard_delay", after.overheardDelay.GetSeconds(), 17);
    Check(name, "failures", after.numFailures, 9);
    Check(name, "admission_retry_pending", after.admissionRetryPending, 1);
    Check(name, "expiry_chirp_count", nwk->GetDiscoveryChirpCountForTest(), 1);
  });
  Simulator::Schedule(Seconds(23), [&] {
    // The completion still belongs to the preserved transaction; freshness
    // expiry does not introduce an unrelated generation rejection.
    nwk->NoteNeighborCheckSuccess(PEER, CsrNeighborCheckType::Message, 0);
    const auto after = nwk->GetSecurityResetStateForTest(PEER);
    const std::string name = "qualified_completion_after_expiry";
    Check(name, "active", nwk->IsArlNeighborActive(PEER), 1);
    Check(name, "failures_decremented_once", after.numFailures, 8);
    Check(name, "admission_retry_canceled_on_activation", after.admissionRetryPending, 0);
  });
  Simulator::Stop(Seconds(23.01));
  Simulator::Run();
  Simulator::Destroy();
}
} // namespace

int main(int argc, char** argv)
{
  if (argc != 2)
    {
      std::cerr << "usage: tranche6_freshness_contract output.csv\n";
      return 2;
    }
  Time::SetResolution(Time::NS);
  g_csv.open(argv[1]);
  if (!g_csv) return 2;
  g_csv << "case,time_seconds,field,actual,expected,pass\n";
  PassiveCase("addressed_data", false, false);
  PassiveCase("overheard_data", false, true);
  PassiveCase("addressed_ack", true, false);
  PassiveCase("overheard_ack", true, true);
  ControlCase("discover_refreshes", "discover", false);
  ControlCase("first_routing_refreshes", "routing", false);
  ControlCase("duplicate_routing_does_not_refresh", "routing", true);
  ControlCase("qualified_check_ack_refreshes", "check_ack", false);
  ControlCase("obsolete_verify_ack_does_not_refresh", "obsolete_verify", false);
  ExpiryRetentionCase();
  g_csv.flush();
  std::cout << "CONTRACT_SUMMARY checks=" << g_checks << " failed=" << g_failed << '\n';
  return g_failed ? 1 : 0;
}
