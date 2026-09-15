// Short controlled-loss experiment. Real pinned NWK/MAC/HOP; explicitly
// prescribed raw draws and whole recipient-group loss. No route discovery/RF claim.
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
  unsigned id = 0, generated = 0, offered = 0, admitted = 0, delivered = 0, releases = 0, blocked = 0, target = 0;
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
  std::ofstream events, transport;
  std::set<std::pair<unsigned,unsigned>> droppedEdges;
  uint64_t order = 0, transmission = 0, group = 0;
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
void Generate(unsigned node, unsigned count)
{
  auto& n = ctx->nodes.at(node);
  if (n.generated + count > n.target) throw std::runtime_error("Generated demand exceeds target");
  for (unsigned i=0; i<count; ++i) {
    FrameInfo info; info.source=node; info.app=++n.generated;
    Event("generate", node, NextHop(node), info);
  }
}
void Offer(unsigned node)
{
  auto& n = ctx->nodes.at(node); if (n.admitted >= n.generated) return;
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
std::string Kind(const CsrHeader& header)
{
  if (header.GetType() == CSR_PKT_DATA) return "DATA";
  if (header.GetType() == CSR_PKT_ACK) return "ACK";
  if (header.GetType() == CSR_PKT_DACK) return "DACK";
  throw std::runtime_error("Unexpected bootstrap control entered measured transport");
}
struct Group { uint64_t id=0; unsigned count=0; bool data=false, feedback=false, drop=false; std::string reason="none"; };
Group Decide(unsigned sender, unsigned receiver, int64_t time, Group group)
{
  auto edge = std::make_pair(sender,receiver);
  if (ctx->name == "data" && group.data && (edge==std::make_pair(4u,5u) || edge==std::make_pair(5u,1u)) && !ctx->droppedEdges.count(edge)) {
    group.drop=true; group.reason="first_data"; ctx->droppedEdges.insert(edge);
  }
  if (ctx->name == "ack" && group.feedback && (edge==std::make_pair(5u,4u) || edge==std::make_pair(1u,5u)) && !ctx->droppedEdges.count(edge)) {
    group.drop=true; group.reason="first_feedback"; ctx->droppedEdges.insert(edge);
  }
  if (ctx->name == "out") {
    if (std::min(std::llabs(time-8000000000LL),std::llabs(time-9500000000LL)) <= 1000)
      throw std::runtime_error("Loss decision ambiguous within 1us of outage boundary");
    if (time >= 8000000000LL && time < 9500000000LL) { group.drop=true; group.reason="outage"; }
  }
  return group;
}
std::map<unsigned,Group> GroupFrames(uint32_t sender, const std::vector<Ptr<Packet>>& frames)
{
  std::map<unsigned,Group> groups;
  for (const auto& frame : frames) {
    CsrHeader header; frame->PeekHeader(header); unsigned receiver=header.GetDst();
    if (!((sender==4 && receiver==5) || (sender==5 && (receiver==1 || receiver==4)) || (sender==1 && receiver==5)))
      throw std::runtime_error("Transport requires declared chain addressed recipient");
    auto kind=Kind(header); auto& group=groups[receiver];
    if (!group.count) group.id=++ctx->group;
    ++group.count; group.data |= kind=="DATA"; group.feedback |= kind=="ACK" || kind=="DACK";
  }
  return groups;
}
void Transport(uint32_t sender, const std::vector<Ptr<Packet>>& frames,
               Time duration, int rate, double power, int preamble, int slot)
{
  uint64_t tx = ++ctx->transmission;
  int64_t now=Simulator::Now().GetNanoSeconds(), arrival=(Simulator::Now()+duration+MicroSeconds(1)).GetNanoSeconds();
  auto groups=GroupFrames(sender,frames);
  for (auto& item : groups) item.second=Decide(sender,item.first,now,item.second);
  unsigned index=0;
  for (const auto& frame : frames) {
    ++index; CsrHeader header; frame->PeekHeader(header); unsigned receiver=header.GetDst();
    auto info=Info(frame); info.rate=rate; info.power=power; auto& group=groups.at(receiver);
    Event("tx_start",sender,receiver,info);
    int64_t distance=ctx->name=="out" ? std::min(std::llabs(now-8000000000LL),std::llabs(now-9500000000LL)) : -1;
    ctx->transport << ctx->name << ',' << tx << ',' << group.id << ',' << index << ',' << group.count
      << ',' << now << ',' << arrival << ',' << sender << ',' << receiver << ',' << Kind(header)
      << ',' << info.source << ',' << info.app << ',' << info.seq << ',' << info.ack << ',' << info.dack
      << ',' << (group.drop?"drop":"pass") << ',' << group.reason << ',' << distance << '\n';
  }
  // Loss is cached per addressed receiver group at actual TX start. Actual
  // airtime, selected segment order and HOP Sent notifications remain native.
  Simulator::Schedule(duration+MicroSeconds(1), [sender,frames,slot,groups] {
    std::set<unsigned> observed;
    for (const auto& frame : frames) {
      CsrHeader header; frame->PeekHeader(header); unsigned receiver=header.GetDst();
      auto info=Info(frame);
      if (groups.at(receiver).drop) { Event("loss",receiver,sender,info); continue; }
      Event("ingress_before",receiver,sender,info);
      auto& mac=ctx->nodes.at(receiver).device->GetMac();
      if (observed.insert(receiver).second) {
        mac.NoteHeardFrom(sender,Simulator::Now().GetSeconds());
        mac.SetNeighborPathloss(sender,70); mac.NoteNeighborReservedSlot(sender,slot);
      }
      mac.DeliverRxFrameToUp(frame->Copy(),70,20);
      Event("ingress_after",receiver,sender,info);
    }
  });
}
void RunCase(const Row& input, const std::vector<Row>& tapes, const std::vector<Row>& offers, const std::filesystem::path& output)
{
  Context context; ctx = &context; ctx->name = input.at("case");
  auto folder = output / ctx->name; std::filesystem::create_directories(folder);
  ctx->events.open(folder / "events.csv");
  ctx->transport.open(folder / "transport.csv");
  ctx->transport << "case,tx_id,group_id,segment_index,group_segments,tx_time_ns,arrival_ns,sender,receiver,kind,app_source,app_id,hop_seq,ack_bits,dack_bits,decision,reason,boundary_distance_ns\n";
  ctx->events << "case,order,time_ns,event,node,peer,app_source,app_id,hop_seq,ack_bits,dack_bits,mac_state,ack_queue,data_queue,prep,counter,opportunity,advertised,hop_pending,neighbor_outstanding,neighbor_threshold,resend_queue,admitted,rate_kbps,power_dbm,nwk_waiting,nwk_custody,nsdp4,nsdp5,dack_holds\n";
  for (const auto& row : tapes) if (row.at("case") == ctx->name) ctx->tapes[std::stoul(row.at("node"))].push_back(row);
  for (unsigned node : {1, 4, 5})
    if (ctx->tapes[node].size() != 1024) throw std::runtime_error("Expected complete 1024-entry node tape");
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
  for (const auto& offer : offers) if (offer.at("case") == ctx->name) {
    unsigned node = Integer(offer.at("source")), id = Integer(offer.at("app_id"));
    Simulator::Schedule(NanoSeconds(std::stoll(offer.at("due_ns"))), [node,id] {
      if (ctx->nodes.at(node).generated + 1 != id) throw std::runtime_error("Noncontiguous generation identity");
      Generate(node,1);
    });
  }
  for (unsigned poll = 0; poll < 2000; ++poll)
    Simulator::Schedule(MilliSeconds(poll * 20), [] { Offer(4); Offer(5); });
  for (double checkpoint : {8.0, 9.5, 20.0, 24.0, 40.0})
    Simulator::Schedule(Seconds(checkpoint), [] { for (unsigned node : {1, 4, 5}) Event("checkpoint", node, NextHop(node)); });
  Simulator::Stop(Seconds(duration)); Simulator::Run();
  for (unsigned node : {1, 4, 5}) Event("final", node, NextHop(node));
  std::ofstream draws(folder / "raw.csv");
  draws << "case,node,ordinal,time_ns,min,max,draw,resolved,probes\n";
  for (const auto& d : ctx->draws) draws << ctx->name << ',' << d.node << ',' << d.ordinal << ',' << d.time << ',' << d.low << ',' << d.high << ',' << d.raw << ',' << d.resolved << ',' << d.probes << '\n';
  std::ofstream summary(folder / "summary.csv");
  summary << "case,node,generated,offered,admitted,delivered,releases,blocked,pending,resend_queue,ack_queue,data_queue,nwk_waiting,nsdp4,nsdp5,draws_consumed,draws_unused\n";
  for (unsigned node : {1, 4, 5}) {
    auto& n = ctx->nodes[node]; auto& mac = n.device->GetMac(); unsigned used = ctx->consumed[node];
    summary << ctx->name << ',' << node << ',' << n.generated << ',' << n.offered << ',' << n.admitted << ',' << n.delivered << ',' << n.releases << ',' << n.blocked << ',' << n.hop->GetPendingDataCount() << ',' << n.hop->GetResendQueueSize() << ',' << mac.GetAckQueuedFrameCount() << ',' << mac.GetDataQueuedFrameCount() << ',' << n.nwk->GetNwkQueueSize() << ',' << n.nwk->GetNsdpCount(4, 1) << ',' << n.nwk->GetNsdpCount(5, 1) << ',' << used << ',' << 1024 - used << '\n';
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
  auto require = [&checks](bool yes) { if (!yes) throw std::runtime_error("Loss oracle self-test failed"); ++checks; };
  Group data; data.data=true; data.count=3; Group feedback; feedback.feedback=true; feedback.count=2;
  ctx->name="data";
  require(Decide(4,5,0,data).drop); require(!Decide(4,5,1,data).drop);
  require(!Decide(5,4,1,data).drop); require(Decide(5,1,1,data).drop);
  ctx->name="ack"; ctx->droppedEdges.clear();
  require(!Decide(5,4,0,data).drop); require(Decide(5,4,0,feedback).drop);
  require(!Decide(5,4,1,feedback).drop); require(Decide(1,5,0,feedback).drop);
  ctx->name="out";
  rejects([&] { Decide(4,5,8000000000LL,data); });
  rejects([&] { Decide(4,5,9500001000LL,data); });
  require(!Decide(4,5,7999998999LL,data).drop);
  require(Decide(4,5,8000001001LL,data).drop);
  require(Decide(1,5,9499998999LL,feedback).drop);
  require(!Decide(5,4,9500001001LL,feedback).drop);
  ctx->name="ok"; require(!Decide(4,5,8000000000LL,data).drop);
  // Exercise the same grouping function as actual Transport with mixed
  // segment kinds and independently addressed recipient groups.
  auto makeFrame=[](unsigned receiver, CsrPktType kind) {
    auto frame=Create<Packet>(0); CsrHeader header(5,receiver,1,0,false,false);
    header.SetType(kind); frame->AddHeader(header); return frame;
  };
  std::vector<Ptr<Packet>> mixed={makeFrame(4,CSR_PKT_ACK),makeFrame(1,CSR_PKT_DATA),makeFrame(1,CSR_PKT_ACK)};
  ctx->name="data"; ctx->droppedEdges.clear(); ctx->group=0;
  auto groups=GroupFrames(5,mixed);
  require(groups.at(4).count==1 && groups.at(4).id==1);
  require(groups.at(1).count==2 && groups.at(1).id==2 && groups.at(1).data && groups.at(1).feedback);
  require(!Decide(5,4,0,groups.at(4)).drop);
  require(Decide(5,1,0,groups.at(1)).drop);
  ctx = nullptr; std::cout << "LOSS_SELF_TEST checks=" << checks << " failed=0\n";
}
}
int main(int argc, char** argv)
{
  try {
    if (argc == 2 && std::string(argv[1]) == "--self-test") { SelfTest(); return 0; }
    if (argc != 5) { std::cerr << "usage: tranche13_loss cases.csv draws.csv offers.csv output\n"; return 2; }
    Time::SetResolution(Time::NS); auto cases = ReadCsv(argv[1]); auto draws = ReadCsv(argv[2]);
    auto offers = ReadCsv(argv[3]);
    for (const auto& row : cases) RunCase(row, draws, offers, argv[4]);
    std::cout << "REPLAY_SUMMARY cases=" << cases.size() << " completed=1\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "REPLAY_FAILURE " << error.what() << '\n'; return 1;
  }
}
