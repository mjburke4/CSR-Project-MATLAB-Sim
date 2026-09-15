// T14 actual MAC ACK-service boundary. Reconstructed queued packet inputs,
// unchanged T12 raw-draw/transport seams, actual gateway HOP/NWK. No RF claim.
#include "ns3/core-module.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-nwk-layer.h"
#include "ns3/tranche12-relay-hooks.h"
#include <array>
#include <bit>
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
constexpr int64_t SOURCE_EPOCH = 2808000000LL, GATEWAY_EPOCH = 2832961000LL, TX = 3120000000LL,
                  BOUNDARY = 3144961000LL, STOP = 4000000000LL;
std::string Decimal(double d) {
  std::ostringstream s;
  s << std::setprecision(17) << d;
  return s.str();
}
std::string Hex(double d) {
  std::ostringstream s;
  s << std::hex << std::setfill('0') << std::setw(16) << std::bit_cast<uint64_t>(d);
  return s.str();
}
std::vector<std::string> Split(std::string line) {
  if (!line.empty() && line.back() == '\r')
    line.pop_back();
  std::vector<std::string> out;
  std::istringstream in(line);
  std::string x;
  while (std::getline(in, x, ','))
    out.push_back(x);
  return out;
}
int64_t Integer(const std::string &s) {
  size_t n;
  auto v = std::stoll(s, &n);
  if (n != s.size())
    throw std::runtime_error("Invalid integer");
  return v;
}
std::vector<Row> Read(const std::string &path) {
  std::ifstream f(path);
  std::string line;
  if (!std::getline(f, line))
    throw std::runtime_error("Missing CSV");
  auto header = Split(line);
  if (std::set<std::string>(header.begin(), header.end()).size() != header.size())
    throw std::runtime_error("Duplicate CSV header");
  std::vector<Row> out;
  while (std::getline(f, line)) {
    auto v = Split(line);
    if (v.size() != header.size())
      throw std::runtime_error("CSV width mismatch");
    Row r;
    for (size_t i = 0; i < v.size(); ++i)
      r[header[i]] = v[i];
    out.push_back(r);
  }
  return out;
}
struct Node {
  Ptr<CsrNetDevice> dev;
  Ptr<CsrHopLayer> hop;
  Ptr<CsrNetLayer> nwk;
};
struct Info {
  std::string kind = "NONE";
  unsigned peer = 0, source = 0, seq = 0;
  uint64_t app = 0, ack = 0, dack = 0;
};
Info Get(Ptr<Packet> p) {
  Info i;
  auto copy = p->Copy();
  CsrHeader h;
  if (!copy->RemoveHeader(h))
    throw std::runtime_error("Missing frame header");
  i.kind = h.GetType() == CSR_PKT_DATA ? "DATA" : "ACK";
  i.peer = h.GetDst();
  i.seq = h.GetSeq();
  i.ack = h.GetAckBitmap();
  i.dack = h.GetDackBitmap();
  if (i.kind == "DATA") {
    CsrNetHeader n;
    CsrDifferentialAppTag tag;
    if (!copy->PeekHeader(n) || !p->PeekPacketTag(tag))
      throw std::runtime_error("Missing DATA identity");
    i.source = n.GetSrc();
    i.app = tag.GetSequence();
  }
  return i;
}
struct Context {
  std::string name, mode;
  bool late = false;
  int64_t offset = 0;
  std::array<Node, 6> nodes;
  std::map<unsigned, std::vector<Row>> tapes;
  std::map<unsigned, unsigned> used;
  std::map<unsigned, size_t> pending;
  std::vector<Row> draws;
  std::ofstream events, boundary, checks;
  unsigned order = 0, checkCount = 0, failed = 0, mixed = 0;
  std::set<uint64_t> delivered;
  std::vector<Info> gatewayTx;
  std::vector<int64_t> gatewayTimes;
  std::vector<Ptr<Packet>> cached;
  int cachedSlot = 0;
  Time cachedDuration, cachedTx;
  unsigned ingressCount = 0;
};
Context *c = nullptr;
void Event(const std::string &phase, unsigned node, unsigned peer, Info i = {}) {
  auto &m = c->nodes.at(node).dev->GetMac();
  double now = Simulator::Now().GetSeconds();
  c->events << c->name << ',' << ++c->order << ',' << phase << ','
            << Simulator::Now().GetNanoSeconds() << ',' << Decimal(now) << ',' << Hex(now) << ",0,"
            << node << ',' << peer << ',' << i.kind << ',' << i.source << ',' << i.app << ','
            << i.seq << ',' << i.ack << ',' << i.dack << ',' << m.GetAckQueuedFrameCount() << ','
            << m.GetDataQueuedFrameCount() << ',' << m.GetTransmittedFrameCount() << '\n';
}
void Check(const std::string &checkpoint, unsigned node, int64_t actual, int64_t expected) {
  bool pass = actual == expected;
  ++c->checkCount;
  c->failed += !pass;
  c->checks << c->name << ',' << checkpoint << ',' << node << ',' << actual << ',' << expected
            << ',' << pass << '\n';
  if (!pass)
    std::cerr << "CHECK_FAILED " << c->name << ' ' << checkpoint << ' ' << actual
              << " != " << expected << '\n';
}
Ptr<Packet> Data(unsigned seq) {
  auto p = Create<Packet>(16);
  p->AddPacketTag(CsrDifferentialAppTag(seq));
  p->AddHeader(CsrNetHeader(5, 1, 0));
  CsrHeader h(5, 1, seq, 0, true, false);
  h.SetType(CSR_PKT_DATA);
  h.SetLinkControl(128, 33, -100);
  p->AddHeader(h);
  CsrSetOpnetEnvelope(p, CsrOpnetPacketFormat::Mac, 48);
  return p;
}
Ptr<Packet> Ack() {
  auto p = Create<Packet>();
  CsrHeader h(5, 4, 4, 0, false, true);
  h.SetType(CSR_PKT_ACK);
  h.SetLinkControl(128, 33, -100);
  h.SetHasAckWindow(true);
  h.SetAckBitmap(15);
  h.SetDackBitmap(0);
  p->AddHeader(h);
  CsrSetOpnetEnvelope(p, CsrOpnetPacketFormat::Mac, 41);
  return p;
}
void Delivery(Ptr<Packet> p, CsrNodeId source) {
  CsrDifferentialAppTag tag;
  if (source != 5 || p->GetSize() != 16 || !p->PeekPacketTag(tag) ||
      !c->delivered.insert(tag.GetSequence()).second)
    throw std::runtime_error("Invalid or duplicate gateway delivery");
  Info i;
  i.kind = "DATA";
  i.source = source;
  i.app = tag.GetSequence();
  i.seq = 0;
  Event("deliver", 1, 5, i);
}
int Draw(uint32_t node, int low, int high) {
  auto &used = c->used[node];
  auto &tape = c->tapes.at(node);
  if (used >= tape.size())
    throw std::runtime_error("Raw tape exhausted");
  auto row = tape.at(used);
  if (Integer(row.at("ordinal")) != used + 1 || Integer(row.at("min")) != low ||
      Integer(row.at("max")) != high)
    throw std::runtime_error("Raw draw ordinal/support mismatch");
  int raw = Integer(row.at("draw"));
  if (raw < low || raw > high)
    throw std::runtime_error("Raw draw outside support");
  row["time_ns"] = std::to_string(Simulator::Now().GetNanoSeconds());
  row["resolved"] = "-1";
  row["probes"] = "0";
  c->pending[node] = c->draws.size();
  c->draws.push_back(row);
  ++used;
  return raw;
}
void Resolve(uint32_t node, int resolved, uint32_t probes) {
  auto &r = c->draws.at(c->pending.at(node));
  r["resolved"] = std::to_string(resolved);
  r["probes"] = std::to_string(probes);
}
void Ingress(uint32_t sender, const std::vector<Ptr<Packet>> &frames, int slot, bool mixed) {
  if (mixed)
    ++c->ingressCount;
  std::set<unsigned> observed;
  for (auto p : frames) {
    auto i = Get(p);
    unsigned receiver = i.peer;
    auto &m = c->nodes.at(receiver).dev->GetMac();
    if (i.kind == "DATA")
      Event("ingress_before", receiver, sender, i);
    else
      Event("feedback_ingress", receiver, sender, i);
    if (observed.insert(receiver).second) {
      m.NoteHeardFrom(sender, Simulator::Now().GetSeconds());
      m.SetNeighborPathloss(sender, 70);
      m.NoteNeighborReservedSlot(sender, slot);
    }
    m.DeliverRxFrameToUp(p->Copy(), 70, 20);
    if (i.kind == "DATA")
      Event("ingress_after", receiver, sender, i);
  }
}
void Arm() {
  Time target = NanoSeconds(BOUNDARY + c->offset);
  if (c->mode == "continuous" || c->mode == "local_ns")
    target = c->cachedTx + c->cachedDuration + MicroSeconds(1);
  if (target < Simulator::Now())
    throw std::runtime_error("Arrival precedes arm");
  Time arm = Simulator::Now();
  auto frames = c->cached;
  int slot = c->cachedSlot;
  EventId id =
      Simulator::Schedule(target - arm, [frames, slot] { Ingress(5, frames, slot, true); });
  double tx = c->cachedTx.GetSeconds(), d = c->cachedDuration.GetSeconds(),
         tick = NanoSeconds(BOUNDARY).GetSeconds(), a = arm.GetSeconds(), rx = target.GetSeconds(),
         delta = rx - tick;
  c->boundary << c->name << ',' << c->mode << ',' << c->late << ",89,2,"
              << c->cachedTx.GetNanoSeconds() << ',' << Decimal(tx) << ',' << Hex(tx) << ','
              << c->cachedDuration.GetNanoSeconds() << ',' << Decimal(d) << ',' << Hex(d) << ','
              << BOUNDARY << ',' << Decimal(tick) << ',' << Hex(tick) << ',' << arm.GetNanoSeconds()
              << ',' << Decimal(a) << ',' << Hex(a) << ',' << target.GetNanoSeconds() << ','
              << Decimal(rx) << ',' << Hex(rx) << ',' << Decimal(delta) << ',' << Hex(delta) << ','
              << id.GetUid() << '\n';
}
void Transport(uint32_t sender, const std::vector<Ptr<Packet>> &frames, Time duration, int rate,
               double power, int preamble, int slot) {
  bool hasData = false;
  for (auto p : frames) {
    auto i = Get(p);
    hasData |= i.kind == "DATA";
    Event(sender == 5 ? "aggregate_tx" : "ack_tx", sender, i.peer, i);
    if (sender == 1) {
      c->gatewayTx.push_back(i);
      c->gatewayTimes.push_back(Simulator::Now().GetNanoSeconds());
    }
  }
  if (sender != 1 && sender != 5)
    throw std::runtime_error("Unexpected transmitting node");
  if (hasData) {
    if (sender != 5 || ++c->mixed != 1 || frames.size() != 2 || Get(frames[0]).kind != "ACK" ||
        Get(frames[0]).peer != 4 || Get(frames[1]).kind != "DATA" || Get(frames[1]).peer != 1)
      throw std::runtime_error("Unexpected mixed aggregate");
    Check("mixed_tx_ns", 5, Simulator::Now().GetNanoSeconds(), TX);
    Check("mixed_bytes", 5, CsrGetOpnetAggregateWireSize(frames), 89);
    Check("mixed_segments", 5, frames.size(), 2);
    Check("mixed_duration_ns", 5, duration.GetNanoSeconds(), 24960000);
    Check("mixed_rate", 5, rate, 128);
    Check("mixed_power_tenths", 5, llround(power * 10), 330);
    Check("mixed_preamble_short", 5, preamble, 0);
    c->cached = frames;
    c->cachedDuration = duration;
    c->cachedTx = Simulator::Now();
    c->cachedSlot = slot;
    if (!c->late)
      Arm();
    return;
  }
  Simulator::Schedule(duration + MicroSeconds(1),
                      [sender, frames, slot] { Ingress(sender, frames, slot, false); });
}
void Run(const Row &input, const std::vector<Row> &tapes, const std::filesystem::path &out) {
  Context context;
  c = &context;
  c->name = input.at("case");
  c->mode = input.at("mode");
  c->offset = Integer(input.at("offset_ns"));
  c->late = Integer(input.at("late_insertion"));
  auto dir = out / c->name;
  std::filesystem::create_directories(dir);
  c->events.open(dir / "events.csv");
  c->boundary.open(dir / "boundary.csv");
  c->checks.open(dir / "checks.csv");
  c->events
      << "case,order,phase,time_ns,time_seconds_dec,time_seconds_hex,scheduler_id,node,peer,kind,"
         "app_source,app_id,hop_seq,ack_bits,dack_bits,ack_queue,data_queue,transmissions\n";
  c->boundary << "case,transport_mode,late_insertion,wire_payload_bytes,segment_count,tx_time_ns,"
                 "tx_seconds_dec,tx_seconds_hex,duration_ns,duration_seconds_dec,duration_seconds_"
                 "hex,tick_time_ns,tick_seconds_dec,tick_seconds_hex,arm_time_ns,arm_seconds_dec,"
                 "arm_seconds_hex,arrival_time_ns,arrival_seconds_dec,arrival_seconds_hex,arrival_"
                 "minus_tick_seconds_dec,arrival_minus_tick_seconds_hex,ingress_event_id\n";
  c->checks << "case,checkpoint,node,actual,expected,pass\n";
  for (auto &r : tapes)
    if (r.at("case") == c->name)
      c->tapes[Integer(r.at("node"))].push_back(r);
  for (unsigned node : {1, 4, 5})
    if (c->tapes[node].size() != 64)
      throw std::runtime_error("Full 64-entry tape required");
  RngSeedManager::SetSeed(129);
  RngSeedManager::SetRun(1);
  OpenDifferentialTraceCsv((dir / "native.csv").string());
  SetDifferentialAdmissionTraceEnabled(true);
  for (unsigned node : {1, 4, 5}) {
    auto &n = c->nodes[node];
    n.dev = CreateObject<CsrNetDevice>(node);
    n.hop = CreateObject<CsrHopLayer>();
    n.hop->SetNodeId(node);
    n.hop->SetMac(&n.dev->GetMac());
    n.hop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
    auto &m = n.dev->GetMac();
    m.SetRxCallback(MakeCallback(&CsrHopLayer::ReceiveFromMac, n.hop));
    m.SetSlotSelectionProfile(CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
    m.SetActiveNodesForPostTx(3);
    m.NoteReportedActiveNodes(3);
    m.SetReceiveState(CsrMacCore::State::IDLE);
  }
  auto &g = c->nodes[1];
  g.nwk = CreateObject<CsrNetLayer>();
  g.nwk->SetNodeId(1);
  g.nwk->SetAutomaticRoutePropagationEnabled(false);
  g.nwk->SetRoutingSnapshotResponseEnabled(false);
  g.nwk->SetArlNeighborAdmissionEnabled(false);
  g.nwk->SetHop(g.hop);
  g.nwk->ConfigureLinkControl(128, 128, 33, 33, 6);
  g.nwk->SetRxFromNetCallback(MakeCallback(&Delivery));
  csr_t12::rawDraw = Draw;
  csr_t12::resolvedDraw = Resolve;
  csr_t12::transport = Transport;
  Simulator::Schedule(NanoSeconds(SOURCE_EPOCH), [] {
    auto &m = c->nodes[5].dev->GetMac();
    for (unsigned peer : {1, 4}) {
      m.NoteHeardFrom(peer, Simulator::Now().GetSeconds());
      m.NoteHeardFrom(peer, Simulator::Now().GetSeconds());
      m.SetNeighborPathloss(peer, 70);
    }
    m.SetReceiveState(CsrMacCore::State::SEARCH);
    m.EnqueueTxFrame(Ack(), 4, 0, false);
    m.EnqueueTxFrame(Data(3), 1, 0, true);
    auto &m4 = c->nodes[4].dev->GetMac();
    m4.NoteHeardFrom(5, Simulator::Now().GetSeconds());
    m4.NoteHeardFrom(5, Simulator::Now().GetSeconds());
    m4.SetNeighborPathloss(5, 70);
  });
  Simulator::Schedule(NanoSeconds(GATEWAY_EPOCH), [] {
    auto &m = c->nodes[1].dev->GetMac();
    m.NoteHeardFrom(5, Simulator::Now().GetSeconds());
    m.NoteHeardFrom(5, Simulator::Now().GetSeconds());
    m.SetNeighborPathloss(5, 70);
    m.SetReceiveState(CsrMacCore::State::SEARCH);
    for (unsigned seq : {1, 2}) {
      auto p = Data(seq);
      auto i = Get(p);
      Event("prime_before", 1, 5, i);
      m.DeliverRxFrameToUp(p, 70, 20);
      Event("prime_after", 1, 5, i);
    }
    Check("primed_deliveries", 1, c->delivered.size(), 2);
    Check("primed_ack_queue", 1, m.GetAckQueuedFrameCount(), 1);
  });
  if (c->late)
    Simulator::Schedule(NanoSeconds(BOUNDARY - 2), [] {
      if (c->cached.empty())
        throw std::runtime_error("Late arm missing cached aggregate");
      Arm();
    });
  Simulator::Stop(NanoSeconds(STOP));
  Simulator::Run();
  Check("mixed_aggregate_count", 5, c->mixed, 1);
  Check("mixed_ingress_count", 5, c->ingressCount, 1);
  Check("delivered_count", 1, c->delivered.size(), 3);
  for (unsigned seq : {1, 2, 3})
    Check("delivered_id_" + std::to_string(seq), 1, c->delivered.count(seq), 1);
  Check("gateway_first_ack_ns", 1, c->gatewayTimes.empty() ? 0 : c->gatewayTimes.front(), BOUNDARY);
  bool follows = c->name == "tie_late" || c->name == "after";
  Check("gateway_first_ack_seq", 1, c->gatewayTx.empty() ? 0 : c->gatewayTx.front().seq,
        follows ? 2 : 3);
  Check("gateway_first_ack_bits", 1, c->gatewayTx.empty() ? 0 : c->gatewayTx.front().ack,
        follows ? 3 : 7);
  Check("gateway_ack_count", 1, c->gatewayTx.size(), follows ? 6 : 5);
  Check("gateway_last_ack_seq", 1, c->gatewayTx.empty() ? 0 : c->gatewayTx.back().seq, 3);
  Check("gateway_last_ack_bits", 1, c->gatewayTx.empty() ? 0 : c->gatewayTx.back().ack, 7);
  for (unsigned node : {1, 4, 5}) {
    auto &n = c->nodes[node];
    auto &m = n.dev->GetMac();
    Event("settled", node, 0);
    Check("final_ack_queue", node, m.GetAckQueuedFrameCount(), 0);
    Check("final_data_queue", node, m.GetDataQueuedFrameCount(), 0);
    Check("final_hop_pending", node, n.hop->GetPendingDataCount(), 0);
    Check("final_resend_queue", node, n.hop->GetResendQueueSize(), 0);
    Check("final_dack_holds", node, n.hop->GetDackHoldCountForTranche12(), 0);
  }
  Check("final_nwk_queue", 1, g.nwk->GetNwkQueueSize(), 0);
  std::ofstream raw(dir / "raw.csv");
  raw << "case,node,ordinal,time_ns,min,max,draw,resolved,probes\n";
  for (auto &r : c->draws) {
    for (auto key : {"case", "node", "ordinal", "time_ns", "min", "max", "draw", "resolved"})
      raw << r.at(key) << ',';
    raw << r.at("probes") << '\n';
  }
  std::ofstream usage(dir / "usage.csv");
  usage << "case,node,supplied,consumed,unused\n";
  for (unsigned n : {1, 4, 5})
    usage << c->name << ',' << n << ",64," << c->used[n] << ',' << 64 - c->used[n] << '\n';
  std::cout << "EDGE_CASE " << c->name << " events=" << c->order << " checks=" << c->checkCount
            << " failed=" << c->failed << "\n";
  unsigned failures = c->failed;
  CloseDifferentialTraceCsv();
  Simulator::Destroy();
  SetDifferentialAdmissionTraceEnabled(false);
  csr_t12::rawDraw = {};
  csr_t12::resolvedDraw = {};
  csr_t12::transport = {};
  c = nullptr;
  if (failures)
    throw std::runtime_error("Edge structural checks failed");
}
void SelfTest() {
  Context context;
  c = &context;
  unsigned checks = 0;
  auto yes = [&](bool p) {
    if (!p)
      throw std::runtime_error("Self-test failed");
    ++checks;
  };
  auto reject = [&](auto fn) {
    bool rejected = false;
    try {
      fn();
    } catch (const std::exception &) {
      rejected = true;
    }
    yes(rejected);
  };
  yes(Hex(1.0) == "3ff0000000000000");
  yes(Hex(0.0) == "0000000000000000");
  yes(Integer("3144961000") == BOUNDARY);
  reject([] { Integer("1.5"); });
  Row r{{"case", "test"}, {"node", "1"}, {"ordinal", "1"},
        {"min", "0"},     {"max", "31"}, {"draw", "0"}};
  c->tapes[1] = {r};
  yes(Draw(1, 0, 31) == 0);
  Resolve(1, 0, 1);
  yes(c->draws.back().at("resolved") == "0");
  reject([] { Draw(1, 0, 31); });
  c->used[1] = 0;
  reject([] { Draw(1, 0, 30); });
  c->tapes[1][0]["draw"] = "32";
  reject([] { Draw(1, 0, 31); });
  c->tapes[1][0]["draw"] = "1.5";
  reject([] { Draw(1, 0, 31); });
  c->tapes[1][0] = r;
  c->tapes[1][0]["ordinal"] = "2";
  reject([] { Draw(1, 0, 31); });
  yes(CsrGetOpnetAggregateWireSize({Ack(), Data(3)}) == 89);
  yes(Get(Ack()).ack == 15);
  yes(Get(Data(3)).app == 3);
  c = nullptr;
  std::cout << "EDGE_SELF_TEST checks=" << checks << " failed=0\n";
}
} // namespace
int main(int argc, char **argv) {
  try {
    Time::SetResolution(Time::NS);
    if (argc == 2 && std::string(argv[1]) == "--self-test") {
      SelfTest();
      return 0;
    }
    if (argc != 4)
      throw std::runtime_error("usage: edge cases.csv draws.csv output");
    auto cases = Read(argv[1]), draws = Read(argv[2]);
    for (auto &r : cases)
      Run(r, draws, argv[3]);
    std::cout << "EDGE_SUMMARY cases=" << cases.size() << " completed=1\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "EDGE_FAILURE " << e.what() << '\n';
    return 1;
  }
}
