// Short matched-contention experiment. Real pinned NWK/MAC/HOP; explicitly
// prescribed raw draws and successful addressed delivery. No route discovery/RF claim.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-nwk-layer.h"
#include "ns3/tranche12-relay-hooks.h"
#include <array>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ns3;
namespace {
using Row = std::map<std::string, std::string>;
int Integer(const std::string& value)
{
  size_t used = 0; int number = std::stoi(value, &used);
  if (used != value.size()) throw std::runtime_error("Non-integer replay value");
  return number;
}
std::vector<std::string> Split(const std::string& line)
{
  std::vector<std::string> out; std::stringstream input(line); std::string part;
  while (std::getline(input, part, ',')) { if (!part.empty() && part.back() == '\r') part.pop_back(); out.push_back(part); }
  return out;
}
std::vector<Row> ReadCsv(const std::string& path)
{
  std::ifstream input(path); if (!input) throw std::runtime_error("Cannot open " + path);
  std::string line; if (!std::getline(input, line)) throw std::runtime_error("Empty CSV");
  auto header = Split(line); std::vector<Row> rows;
  while (std::getline(input, line)) {
    if (line.empty()) continue; auto fields = Split(line);
    if (fields.size() != header.size()) throw std::runtime_error("CSV row width mismatch");
    Row row; for (unsigned i = 0; i < header.size(); ++i) row[header[i]] = fields[i]; rows.push_back(row);
  }
  return rows;
}
struct Draw { unsigned node, ordinal; int64_t time; int low, high, raw, resolved = -1; unsigned probes = 0; };
struct FrameInfo { unsigned source = 0, app = 0, seq = 0; uint64_t ack = 0, dack = 0; int rate = 0; double power = 0; };
struct Context;
struct Node {
  unsigned id = 0, offered = 0, admitted = 0, delivered = 0, releases = 0, blocked = 0, target = 0;
  Ptr<CsrNetDevice> device; Ptr<CsrHopLayer> hop; Ptr<CsrNetLayer> nwk;
  std::set<std::pair<unsigned, unsigned>> received;
  void Release(CsrNodeId source, CsrNodeId destination);
  void Delivery(Ptr<Packet> packet, CsrNodeId peer);
};
struct Context {
  std::string name; std::array<Node, 6> nodes;
  std::map<unsigned, std::vector<Row>> tapes;
  std::map<unsigned, unsigned> consumed;
  std::map<unsigned, size_t> pendingDraw;
  std::vector<Draw> draws;
  std::ofstream events;
  uint64_t order = 0;
} *ctx = nullptr;

int State(CsrMacCore::State state)
{
  if (state == CsrMacCore::State::IDLE) return 0;
  if (state == CsrMacCore::State::SEARCH) return 1;
  if (state == CsrMacCore::State::TRACK) return 2;
  return 3;
}
FrameInfo Info(Ptr<Packet> frame)
{
  FrameInfo info; CsrHeader header; auto payload = frame->Copy();
  if (!payload->RemoveHeader(header)) throw std::runtime_error("Missing MAC/HOP header");
  info.seq = header.GetSeq(); info.rate = header.GetSpeedKey(); info.power = header.GetTxPowerDbm();
  if (header.HasAckWindow()) { info.ack = header.GetAckBitmap(); info.dack = header.GetDackBitmap(); }
  if (header.GetType() == CSR_PKT_DATA) {
    CsrNetHeader net; if (!payload->PeekHeader(net)) throw std::runtime_error("Missing DATA network metadata");
    info.source = net.GetSrc(); CsrDifferentialAppTag tag;
    if (!frame->PeekPacketTag(tag)) throw std::runtime_error("Missing application identity tag");
    info.app = tag.GetSequence();
  }
  return info;
}
void Event(const std::string& event, unsigned node, unsigned peer, FrameInfo info = {})
{
  auto& n = ctx->nodes.at(node); auto& mac = n.device->GetMac();
  auto snap = n.hop->GetDataAdmissionSnapshot(peer);
  ctx->events << ctx->name << ',' << ++ctx->order << ',' << Simulator::Now().GetNanoSeconds()
    << ',' << event << ',' << node << ',' << peer << ',' << info.source << ',' << info.app
    << ',' << info.seq << ',' << info.ack << ',' << info.dack << ',' << State(mac.GetState())
    << ',' << mac.GetAckQueuedFrameCount() << ',' << mac.GetDataQueuedFrameCount()
    << ',' << mac.IsTxPreparationActive() << ',' << mac.GetLocalReservationCounter()
    << ',' << mac.GetLastTxOpportunitySlot() << ',' << mac.GetLastAdvertisedReservationSlot()
    << ',' << snap.pendingData << ',' << snap.neighborOutstanding << ',' << snap.neighborThreshold
    << ',' << n.hop->GetResendQueueSize() << ',' << n.admitted << ',' << info.rate
    << ',' << std::setprecision(17) << info.power
    << ',' << n.nwk->GetNwkQueueSize()
    << ',' << n.nwk->GetNsdpCount(4, 1) + n.nwk->GetNsdpCount(5, 1)
    << ',' << n.nwk->GetNsdpCount(4, 1) << ',' << n.nwk->GetNsdpCount(5, 1)
    << ',' << n.hop->GetDackHoldCountForTranche12() << '\n';
}
unsigned NextHop(unsigned node) { return node == 4 ? 5 : (node == 5 ? 1 : 0); }
void Offer(unsigned node)
{
  auto& n = ctx->nodes.at(node); if (n.admitted >= n.target) return;
  FrameInfo info; info.source = node; info.app = n.admitted + 1;
  ++n.offered; Event("offer", node, NextHop(node), info);
  if (!n.nwk->CanAdmitApplicationPacket(1)) { ++n.blocked; Event("blocked", node, NextHop(node), info); return; }
  auto payload = Create<Packet>(16); payload->AddPacketTag(CsrDifferentialAppTag(info.app));
  auto before = n.nwk->GetNsdpCount(node, 1);
  n.nwk->Send(1, 0, payload, true);
  if (n.nwk->GetNsdpCount(node, 1) != before + 1)
    throw std::runtime_error("Actual NWK Send did not retain the admitted application");
  ++n.admitted; Event("admit", node, NextHop(node), info);
}
void Node::Release(CsrNodeId source, CsrNodeId destination)
{
  if ((source != 4 && source != 5) || destination != 1)
    throw std::runtime_error("Wrong released network flow");
  auto before = nwk->GetNsdpCount(source, destination);
  nwk->DecrementNsdp(source, destination);
  if (!before || nwk->GetNsdpCount(source, destination) != before - 1)
    throw std::runtime_error("Release callback did not decrement real NWK custody");
  ++releases; FrameInfo info; info.source = source; Event("release", id, NextHop(id), info);
}
void Node::Delivery(Ptr<Packet> packet, CsrNodeId source)
{
  CsrDifferentialAppTag tag;
  if (id != 1 || !packet->PeekPacketTag(tag) || (source != 4 && source != 5) || packet->GetSize() != 16)
    throw std::runtime_error("Invalid actual NWK application delivery");
  if (!received.insert({source, tag.GetSequence()}).second)
    throw std::runtime_error("Duplicate application delivery escaped the stack");
  if (tag.GetSequence() < 1 || tag.GetSequence() > ctx->nodes[source].target)
    throw std::runtime_error("Actual delivered application was never offered");
  ++delivered; FrameInfo info; info.source = source; info.app = tag.GetSequence(); Event("deliver", id, 5, info);
}
int RawDraw(uint32_t node, int low, int high)
{
  auto& ordinal = ctx->consumed[node]; auto& tape = ctx->tapes.at(node);
  if (ordinal >= tape.size()) throw std::runtime_error("Replay tape exhausted");
  auto& row = tape.at(ordinal);
  if (Integer(row.at("ordinal")) != static_cast<int>(ordinal + 1) ||
      Integer(row.at("min")) != low || Integer(row.at("max")) != high)
    throw std::runtime_error("Replay ordinal/support mismatch");
  int raw = Integer(row.at("draw"));
  if (raw < low || raw > high) throw std::runtime_error("Replay draw outside native support");
  ctx->pendingDraw[node] = ctx->draws.size();
  ctx->draws.push_back({node, ++ordinal, Simulator::Now().GetNanoSeconds(), low, high, raw});
  return raw;
}
void ResolvedDraw(uint32_t node, int resolved, uint32_t probes)
{
  auto& draw = ctx->draws.at(ctx->pendingDraw.at(node));
  draw.resolved = resolved; draw.probes = probes;
}
void Transport(uint32_t sender, const std::vector<Ptr<Packet>>& frames,
               Time duration, int rate, double power, int preamble, int slot)
{
  for (const auto& frame : frames) {
    CsrHeader header; frame->PeekHeader(header); unsigned receiver = header.GetDst();
    if (!((sender == 4 && receiver == 5) || (sender == 5 && (receiver == 1 || receiver == 4)) || (sender == 1 && receiver == 5)))
      throw std::runtime_error("Transport requires declared addressed recipient");
    auto info = Info(frame); info.rate = rate; info.power = power;
    Event("tx_start", sender, receiver, info);
  }
  // Each aggregate arrives in one event, in actual segment order. Receiver
  // state is intentionally not an acceptance gate: this is a prescribed link.
  Simulator::Schedule(duration + MicroSeconds(1), [sender, frames, slot] {
    std::set<unsigned> observed;
    for (const auto& frame : frames) {
      CsrHeader header; frame->PeekHeader(header); unsigned receiver = header.GetDst();
      auto info = Info(frame); Event("ingress_before", receiver, sender, info);
      auto& mac = ctx->nodes.at(receiver).device->GetMac();
      if (observed.insert(receiver).second) {
        mac.NoteHeardFrom(sender, Simulator::Now().GetSeconds());
        mac.SetNeighborPathloss(sender, 70); mac.NoteNeighborReservedSlot(sender, slot);
      }
      mac.DeliverRxFrameToUp(frame->Copy(), 70, 20);
      Event("ingress_after", receiver, sender, info);
    }
  });
}
void RunCase(const Row& input, const std::vector<Row>& tapes, const std::filesystem::path& output)
{
  Context context; ctx = &context; ctx->name = input.at("case");
  auto folder = output / ctx->name; std::filesystem::create_directories(folder);
  ctx->events.open(folder / "events.csv");
  ctx->events << "case,order,time_ns,event,node,peer,app_source,app_id,hop_seq,ack_bits,dack_bits,mac_state,ack_queue,data_queue,prep,counter,opportunity,advertised,hop_pending,neighbor_outstanding,neighbor_threshold,resend_queue,admitted,rate_kbps,power_dbm,nwk_waiting,nwk_custody,nsdp4,nsdp5,dack_holds\n";
  for (const auto& row : tapes) if (row.at("case") == ctx->name) ctx->tapes[std::stoul(row.at("node"))].push_back(row);
  for (unsigned node : {1, 4, 5})
    if (ctx->tapes[node].size() != 256) throw std::runtime_error("Expected complete 256-entry node tape");
  RngSeedManager::SetSeed(129); RngSeedManager::SetRun(1);
  OpenDifferentialTraceCsv((folder / "native.csv").string()); SetDifferentialAdmissionTraceEnabled(true);
  for (unsigned node : {1, 4, 5}) {
    auto& n = ctx->nodes[node]; n.id = node; n.device = CreateObject<CsrNetDevice>(node);
    n.hop = CreateObject<CsrHopLayer>(); n.hop->SetNodeId(node); n.hop->SetMac(&n.device->GetMac());
    n.hop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
    n.nwk = CreateObject<CsrNetLayer>(); n.nwk->SetNodeId(node);
    n.nwk->SetAutomaticRoutePropagationEnabled(false); n.nwk->SetRoutingSnapshotResponseEnabled(false);
    n.nwk->SetArlNeighborAdmissionEnabled(false); n.nwk->SetHop(n.hop);
    n.nwk->ConfigureLinkControl(128, 128, 33, 33, 6);
    n.nwk->SetRxFromNetCallback(MakeCallback(&Node::Delivery, &n));
    n.hop->SetNsdpDecrementCallback(MakeCallback(&Node::Release, &n));
    auto& mac = n.device->GetMac();
    mac.SetRxCallback(MakeCallback(&CsrHopLayer::ReceiveFromMac, n.hop));
    mac.SetSlotSelectionProfile(CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
    mac.SetActiveNodesForPostTx(3); mac.NoteReportedActiveNodes(3);
    mac.SetReceiveState(CsrMacCore::State::SEARCH);
    for (unsigned peer : {1, 4, 5}) if ((node == 5 && peer != 5) || (node != 5 && peer == 5)) {
      mac.NoteHeardFrom(peer, 0); mac.NoteHeardFrom(peer, 0); mac.SetNeighborPathloss(peer, 70);
    }
  }
  ctx->nodes[4].target = Integer(input.at("apps4")); ctx->nodes[5].target = Integer(input.at("apps5"));
  ctx->nodes[4].nwk->AddStaticRouteWithPathloss(1, 5, 70, false, 2);
  ctx->nodes[5].nwk->AddStaticRouteWithPathloss(1, 1, 70, true, 2);
  if (!ctx->nodes[4].nwk->HasRelayRoute(1) || !ctx->nodes[5].nwk->HasRelayRoute(1))
    throw std::runtime_error("Prescribed DATA routes not usable");
  csr_t12::rawDraw = RawDraw; csr_t12::resolvedDraw = ResolvedDraw; csr_t12::transport = Transport;
  const double duration = std::stod(input.at("duration_seconds"));
  for (unsigned poll = 0; poll < 800; ++poll)
    Simulator::Schedule(MilliSeconds(poll * 20), [] { Offer(4); Offer(5); });
  Simulator::Schedule(Seconds(16), [] { for (unsigned node : {1, 4, 5}) Event("checkpoint", node, NextHop(node)); });
  Simulator::Stop(Seconds(duration)); Simulator::Run();
  for (unsigned node : {1, 4, 5}) Event("final", node, NextHop(node));
  std::ofstream draws(folder / "raw.csv");
  draws << "case,node,ordinal,time_ns,min,max,draw,resolved,probes\n";
  for (const auto& d : ctx->draws) draws << ctx->name << ',' << d.node << ',' << d.ordinal << ',' << d.time << ',' << d.low << ',' << d.high << ',' << d.raw << ',' << d.resolved << ',' << d.probes << '\n';
  std::ofstream summary(folder / "summary.csv");
  summary << "case,node,offered,admitted,delivered,releases,blocked,pending,resend_queue,ack_queue,data_queue,nwk_waiting,nsdp4,nsdp5,draws_consumed,draws_unused\n";
  for (unsigned node : {1, 4, 5}) {
    auto& n = ctx->nodes[node]; auto& mac = n.device->GetMac(); unsigned used = ctx->consumed[node];
    summary << ctx->name << ',' << node << ',' << n.offered << ',' << n.admitted << ',' << n.delivered << ',' << n.releases << ',' << n.blocked << ',' << n.hop->GetPendingDataCount() << ',' << n.hop->GetResendQueueSize() << ',' << mac.GetAckQueuedFrameCount() << ',' << mac.GetDataQueuedFrameCount() << ',' << n.nwk->GetNwkQueueSize() << ',' << n.nwk->GetNsdpCount(4, 1) << ',' << n.nwk->GetNsdpCount(5, 1) << ',' << used << ',' << 256 - used << '\n';
  }
  std::ofstream deliveries(folder / "deliveries.csv"); deliveries << "case,app_source,app_id\n";
  for (const auto& app : ctx->nodes[1].received) deliveries << ctx->name << ',' << app.first << ',' << app.second << '\n';
  CloseDifferentialTraceCsv(); Simulator::Destroy(); SetDifferentialAdmissionTraceEnabled(false);
  csr_t12::rawDraw = {}; csr_t12::resolvedDraw = {}; csr_t12::transport = {};
  ctx = nullptr;
}
void SelfTest()
{
  unsigned checks = 0; Context context; ctx = &context;
  Row valid{{"ordinal","1"},{"min","0"},{"max","31"},{"draw","31"}};
  ctx->tapes[1] = {valid};
  if (RawDraw(1, 0, 31) != 31) throw std::runtime_error("Inclusive endpoint not accepted");
  ++checks;
  auto rejects = [&checks](auto fn) {
    bool rejected = false; try { fn(); } catch (const std::exception&) { rejected = true; }
    if (!rejected) throw std::runtime_error("Replay fail-closed test unexpectedly accepted");
    ++checks;
  };
  rejects([] { RawDraw(1, 0, 31); });
  ctx->consumed[1] = 0; rejects([] { RawDraw(1, 0, 30); });
  ctx->tapes[1][0]["draw"] = "32"; rejects([] { RawDraw(1, 0, 31); });
  ctx->tapes[1][0]["draw"] = "1.5"; rejects([] { RawDraw(1, 0, 31); });
  ctx->tapes[1][0] = valid; ctx->tapes[1][0]["ordinal"] = "2";
  rejects([] { RawDraw(1, 0, 31); });
  ctx = nullptr; std::cout << "REPLAY_SELF_TEST checks=" << checks << " failed=0\n";
}
}
int main(int argc, char** argv)
{
  try {
    if (argc == 2 && std::string(argv[1]) == "--self-test") { SelfTest(); return 0; }
    if (argc != 4) { std::cerr << "usage: tranche12_relay cases.csv draws.csv output\n"; return 2; }
    Time::SetResolution(Time::NS); auto cases = ReadCsv(argv[1]); auto draws = ReadCsv(argv[2]);
    for (const auto& row : cases) RunCase(row, draws, argv[3]);
    std::cout << "REPLAY_SUMMARY cases=" << cases.size() << " completed=1\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "REPLAY_FAILURE " << error.what() << '\n'; return 1;
  }
}
