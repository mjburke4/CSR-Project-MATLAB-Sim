// Observation fixture for the pinned ns-3 CSR implementation.  This file is
// compiled as a standalone translation unit; it does not edit the source tree
// or install a custom PHY/error model.  See the Python launcher for provenance.
#include "ns3/core-module.h"
#include "ns3/csr-common.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-nwk-layer.h"

#include <array>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <string>

using namespace ns3;

namespace
{
constexpr double STOP = 900.0;
constexpr double BLACKOUT_START = 405.0;
constexpr double BLACKOUT_END = 540.0;
constexpr CsrNodeId RELAY = 2;

struct RuntimeNode
{
  CsrNodeId id;
  Ptr<CsrNetDevice> device;
  Ptr<CsrHopLayer> hop;
  Ptr<CsrNetLayer> network;
  uint64_t postPhyDrops {0};
  uint64_t delivered {0};
  uint64_t linkFailureCallbacks {0};
};

std::map<CsrNodeId, RuntimeNode> nodes;
std::ofstream snapshots;
bool relayEnabled = true;

void
AdministrativeEvent (const std::string &name, CsrNodeId node)
{
  CsrDifferentialTraceEvent event;
  event.event = name;
  event.node = CsrTraceInteger (node);
  event.reason = "explicit_fixture_stimulus";
  WriteDifferentialTrace (event);
}

void
SetRelayEnabled (bool enabled)
{
  relayEnabled = enabled;
  AdministrativeEvent (enabled ? "link_enable" : "link_disable", RELAY);
}

void
ReceiveAfterMac (CsrNodeId receiver, Ptr<Packet> frame,
                 double pathlossDb, double snrDb)
{
  CsrHeader header;
  NS_ABORT_MSG_IF (!frame->PeekHeader (header), "Decoded frame has no CSR header");
  RuntimeNode &node = nodes.at (receiver);
  // Match MATLAB NetworkSimulation.receive's source OR receiver eligibility.
  // Source ns-3 has already updated MAC last-heard/pathloss/reservation here.
  // MATLAB rejects before those MAC updates: this residual is reported, never
  // disguised as identical coupling or as a physical movement/power blackout.
  if (!relayEnabled && (receiver == RELAY || header.GetSrc () == RELAY))
    {
      node.postPhyDrops++;
      CsrDifferentialTraceEvent event;
      event.event = "post_phy_eligibility_drop";
      event.node = CsrTraceInteger (receiver);
      event.peer = CsrTraceInteger (header.GetSrc ());
      event.packetType = CsrPacketTypeName (header.GetType ());
      event.source = CsrTraceInteger (header.GetSrc ());
      event.destination = CsrTraceInteger (header.GetDst ());
      event.sequence = CsrTraceInteger (header.GetSeq ());
      event.success = "0";
      event.reason = "node_disabled_after_mac_before_hop";
      WriteDifferentialTrace (event);
      return;
    }
  node.hop->ReceiveFromMac (frame, pathlossDb, snrDb);
}

void
ObserveLinkFailure (CsrNodeId node, CsrNodeId peer)
{
  nodes.at (node).linkFailureCallbacks++;
  CsrDifferentialTraceEvent event;
  event.event = "observed_link_failure_callback";
  event.node = CsrTraceInteger (node);
  event.peer = CsrTraceInteger (peer);
  WriteDifferentialTrace (event);
  nodes.at (node).network->NoteLinkFailure (peer);
}

void
Deliver (CsrNodeId node, Ptr<Packet> packet, CsrNodeId source)
{
  nodes.at (node).delivered++;
  CsrDifferentialAppTag tag;
  NS_ABORT_MSG_IF (!packet->PeekPacketTag (tag), "Delivered application lacks observation tag");
  NS_ABORT_MSG_IF (source != 3 || node != 1 || packet->GetSize () != 64,
                   "Unexpected delivered application contract");
}

void
Discover (CsrNodeId node)
{
  AdministrativeEvent ("manual_discovery", node);
  nodes.at (node).network->StartDiscovery (Seconds (0), Seconds (30));
}

void
SendApplication (uint64_t sequence)
{
  Ptr<Packet> packet = Create<Packet> (64);
  packet->AddPacketTag (CsrDifferentialAppTag (sequence));
  CsrDifferentialTraceEvent event;
  event.event = "app_send";
  event.node = "3";
  event.peer = "1";
  event.packetType = "data";
  event.source = "3";
  event.destination = "1";
  event.sequence = CsrTraceInteger (sequence);
  event.sizeBytes = CsrTraceInteger (64 + CsrNetHeader ().GetSerializedSize ());
  event.detail = "application_payload_bytes=64;dscp=0;ack_required=1;application_gating=0";
  WriteDifferentialTrace (event);
  nodes.at (3).network->Send (1, 0, packet, true);
}

void
Snapshot ()
{
  for (const auto &[id, node] : nodes)
    {
      uint32_t cost = 0;
      const bool route = node.network->GetSelectedRouteCost (1, cost);
      // Only const observation getters are used: HasRelayRoute/LookupNextHop
      // would change the source destination-creation order while inspecting it.
      snapshots << Simulator::Now ().GetSeconds () << ',' << id << ','
                << node.network->GetNwkQueueSize () << ','
                << node.network->GetNsdpCount (3, 1) << ','
                << node.hop->GetPendingDataCount () << ','
                << node.hop->GetResendQueueSize () << ','
                << node.device->GetMac ().GetQueuedFrameCount () << ','
                << node.device->GetMac ().GetAckQueuedFrameCount () << ','
                << route << ',';
      if (route) snapshots << cost;
      snapshots << ',' << node.network->IsArlNeighborActive (1)
                << ',' << node.network->IsArlNeighborActive (2)
                << ',' << node.network->IsArlNeighborActive (3)
                << ',' << node.network->GetInactiveNeighborDropCount ()
                << ',' << node.postPhyDrops
                << ',' << node.delivered
                << ',' << node.linkFailureCallbacks << '\n';
    }
  if (Simulator::Now ().GetSeconds () + 5 < STOP)
    Simulator::Schedule (Seconds (5), &Snapshot);
}
} // namespace

int
main (int argc, char *argv[])
{
  uint32_t seed = 128;
  double freshness = 60;
  std::string tracePath;
  std::string snapshotPath;
  CommandLine command (__FILE__);
  command.AddValue ("seed", "Paired experiment seed, 128/129/130", seed);
  command.AddValue ("freshness", "Neighbor timeout, 60/180/300 s", freshness);
  command.AddValue ("trace", "Canonical packet trace CSV", tracePath);
  command.AddValue ("snapshots", "Observation-only queue/route snapshots CSV", snapshotPath);
  command.Parse (argc, argv);
  NS_ABORT_MSG_IF (seed < 128 || seed > 130, "Unsupported bounded seed");
  NS_ABORT_MSG_IF (freshness != 60 && freshness != 180 && freshness != 300,
                   "Unsupported bounded freshness timeout");
  NS_ABORT_MSG_IF (tracePath.empty () || snapshotPath.empty (), "Output paths required");
  Time::SetResolution (Time::NS);
  RngSeedManager::SetSeed (seed);
  RngSeedManager::SetRun (1);
  SetDifferentialTraceAggregateOnly (false);
  SetDifferentialAdmissionTraceEnabled (true);
  OpenDifferentialTraceCsv (tracePath);
  snapshots.open (snapshotPath);
  NS_ABORT_MSG_IF (!snapshots, "Cannot open snapshots");
  snapshots << std::setprecision (12)
            << "time_s,node,nwk_queue,nsdp_3_1,hop_pending_data,hop_resend_queue,"
               "mac_queue,mac_ack_queue,selected_route_1,selected_route_cost,"
               "active_peer_1,active_peer_2,active_peer_3,inactive_neighbor_drops,"
               "post_phy_eligibility_drops,app_deliveries,link_failure_callbacks\n";
  int64_t nextStream = 0;
  for (CsrNodeId id : {1, 2, 3})
    {
      RuntimeNode node;
      node.id = id;
      node.device = CreateObject<CsrNetDevice> (id);
      nextStream += node.device->AssignStreams (nextStream);
      node.device->GetMac ().SetSlotSelectionProfile (
        CsrMacCore::SlotSelectionProfile::NS3_CURRENT_FINE_FREE_SLOT);
      CsrPhyProfile profile;
      profile.txPowerDbm = 30;
      profile.txBaseFrequencyHz = 400e6;
      profile.rxBaseFrequencyHz = 400e6;
      profile.txBwHz = profile.rxBwHz = 1e6;
      profile.txHeightMeters = profile.rxHeightMeters = 1;
      profile.stochasticSyncThreshold = true;
      profile.propagationModel = CsrPropagationModel::OPNET_THREE_PATH;
      node.device->GetPhy ().SetProfile (profile);
      node.device->EnableOpnetAlignedDutyCycling (true);
      node.hop = CreateObject<CsrHopLayer> ();
      node.hop->SetHopWireProfile (CsrHopWireProfile::PRODUCTION_PAIRWISE16);
      node.hop->SetNodeId (id);
      node.hop->SetMac (&node.device->GetMac ());
      node.network = CreateObject<CsrNetLayer> ();
      node.network->SetNodeId (id);
      node.network->SetHop (node.hop);
      node.network->SetNodeType (id == 1 ? CsrNodeType::Gateway : CsrNodeType::Routable);
      node.network->ConfigureLinkControl (8, 128, 0, 30, 10);
      node.network->StartNeighborFreshnessMonitor (Seconds (freshness), Seconds (5));
      node.device->GetMac ().SetRxCallback (MakeBoundCallback (&ReceiveAfterMac, id));
      node.hop->SetLinkFailureCallback (MakeBoundCallback (&ObserveLinkFailure, id));
      node.network->SetRxFromNetCallback (MakeBoundCallback (&Deliver, id));
      nodes.emplace (id, std::move (node));
    }
  for (auto &[firstId, first] : nodes)
    for (auto &[secondId, second] : nodes)
      if (firstId != secondId)
        {
          first.device->AddPeer (second.device);
          for (auto &[observerId, observer] : nodes)
            observer.device->GetPhy ().SetLinkDistanceMeters (
              firstId, secondId, 3800.0 * std::abs (int (firstId) - int (secondId)));
        }
  for (CsrNodeId id : {1, 2, 3})
    for (double when : {10.0 + 35 * (id - 1), 315.0 + 5 * (id - 1),
                        576.0 + 5 * (id - 1)})
      Simulator::Schedule (Seconds (when), &Discover, id);
  Simulator::Schedule (Seconds (BLACKOUT_START), &SetRelayEnabled, false);
  Simulator::Schedule (Seconds (BLACKOUT_END), &SetRelayEnabled, true);
  for (uint64_t sequence = 1; sequence <= 5; ++sequence)
    Simulator::Schedule (Seconds (450 + 36 * (sequence - 1)), &SendApplication, sequence);
  Simulator::ScheduleNow (&Snapshot);
  Simulator::Stop (Seconds (STOP));
  Simulator::Run ();
  Snapshot ();
  std::cout << "CSR Tranche 6 outage reference complete: seed=" << seed
            << " freshness=" << freshness << " generated=5 delivered="
            << nodes.at (1).delivered << '\n';
  snapshots.close ();
  CloseDifferentialTraceCsv ();
  Simulator::Destroy ();
  return 0;
}
