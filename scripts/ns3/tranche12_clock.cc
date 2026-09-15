// Production MAC/scheduler boundary observations, no source overlay or RF.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
using namespace ns3;

namespace {
constexpr int64_t EPOCH = 1699501000, BOUNDARY = 2011501000;
std::ofstream events, checks;
unsigned failures = 0, checkpointCount = 0, eventCount = 0;

Ptr<Packet> Frame()
{
  CsrHeader header(1, 2, 1, 0, true, false);
  header.SetType(CSR_PKT_DATA); header.SetDestType(CSR_DEST_UNICAST);
  header.SetLinkControl(128, 33, -100);
  auto packet = Create<Packet>(16); packet->AddHeader(header); return packet;
}

void RunCase(const std::string& name)
{
  auto device = CreateObject<CsrNetDevice>(1); auto& mac = device->GetMac();
  mac.SetSlotSelectionProfile(CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
  mac.SetActiveNodesForPostTx(3);
  mac.SetReceiveState(CsrMacCore::State::IDLE);
  unsigned order = 0;
  const bool followsTick = name == "tie_late" || name == "after";
  auto snapshot = [&](const std::string& phase) {
    ++order; ++eventCount;
    const std::array<int64_t, 4> actual{
      mac.GetLocalReservationCounter(), mac.GetNeighborReservationCounter(2),
      static_cast<int64_t>(mac.GetDataQueuedFrameCount()),
      static_cast<int64_t>(mac.GetTransmittedFrameCount())};
    const std::array<int64_t, 4> expected{
      phase == "settled" || followsTick ? 15 : 16,
      phase == "ingress_before" ? (followsTick ? 15 : 16) :
        (phase == "ingress_after" || followsTick ? 16 : 15), 1, 0};
    events << name << ',' << order << ',' << phase << ','
           << Simulator::Now().GetNanoSeconds();
    for (auto value : actual) events << ',' << value;
    events << '\n';
    const std::array<std::string, 4> fields{
      "local_counter", "neighbor_counter", "data_queue", "transmissions"};
    for (size_t i = 0; i < fields.size(); ++i)
      {
        const bool pass = actual[i] == expected[i];
        ++checkpointCount; failures += !pass;
        checks << name << ',' << phase << ',' << fields[i] << ','
               << actual[i] << ',' << expected[i] << ',' << pass << '\n';
      }
  };
  auto ingress = [&] {
    snapshot("ingress_before");
    // Same known-neighbor reservation update as a successfully received frame.
    mac.NoteNeighborReservedSlot(2, 16);
    snapshot("ingress_after");
  };
  Simulator::Schedule(NanoSeconds(EPOCH), [&] {
    mac.SetReceiveState(CsrMacCore::State::SEARCH);
    mac.NoteHeardFrom(2, Simulator::Now().GetSeconds());
    mac.NoteHeardFrom(2, Simulator::Now().GetSeconds());
    // The first tick decrements these values before PREP_TX. All possible
    // raw draws resolve to the single unoccupied slot 16, without an override.
    for (int slot = 0; slot <= 31; ++slot)
      if (slot != 16)
        {
          const CsrNodeId peer = static_cast<CsrNodeId>(100 + slot);
          mac.NoteHeardFrom(peer, Simulator::Now().GetSeconds());
          mac.NoteHeardFrom(peer, Simulator::Now().GetSeconds());
          mac.NoteNeighborReservedSlot(peer, slot + 1);
        }
    mac.EnqueueTxFrame(Frame(), 2, 0, true);
  });
  Simulator::Schedule(NanoSeconds(BOUNDARY - 5), [&] {
    mac.NoteNeighborReservedSlot(2, 16);
  });
  const int64_t arm = name == "tie_late" ? BOUNDARY - 2 : 1989000000;
  Simulator::Schedule(NanoSeconds(arm), [&] {
    Time target = NanoSeconds(BOUNDARY);
    if (name == "before") target -= NanoSeconds(1);
    if (name == "after") target += NanoSeconds(1);
    if (name == "continuous" || name == "quantized")
      {
        // Reconstruct source PHY airtime. Native time converts each physical
        // duration to its integer time type at the transport interface.
        const double duration = (104.0 + 48.0) / 4.0 * .000510 +
          (48.0 * 8.0 + 32.0) / CsrRateKeyToBps(128);
        target = NanoSeconds(1989000000) + Seconds(duration) + MicroSeconds(1);
      }
    Simulator::Schedule(target - Simulator::Now(), ingress);
  });
  Simulator::Schedule(NanoSeconds(BOUNDARY + 2), [&] { snapshot("settled"); });
  Simulator::Stop(NanoSeconds(BOUNDARY + 3));
  Simulator::Run(); Simulator::Destroy();
}
} // namespace

int main(int argc, char** argv)
{
  if (argc != 2) { std::cerr << "usage: clock OUTPUT_DIRECTORY\n"; return 2; }
  Time::SetResolution(Time::NS);
  const std::string output = argv[1];
  events.open(output + "/events.csv"); checks.open(output + "/checks.csv");
  if (!events || !checks) return 2;
  events << "case,order,phase,time_ns,local_counter,neighbor_counter,data_queue,transmissions\n";
  checks << "case,phase,field,actual,expected,pass\n";
  for (const auto* name : {"tie_early", "tie_late", "before", "after", "continuous", "quantized"})
    RunCase(name);
  events.close(); checks.close();
  std::cout << "clock cases=6 events=" << eventCount << " checkpoints="
            << checkpointCount << " failures=" << failures << '\n';
  return failures == 0 && eventCount == 18 && checkpointCount == 72 ? 0 : 1;
}
