// Matched MAC timing through public APIs on unmodified pinned CSR headers.
// Receiver states and occupancy are prescribed; no RF/RNG equivalence claim.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
using namespace ns3;

namespace {
std::ofstream csv;
unsigned checks = 0, failures = 0;

void Check(const std::string& name, const std::string& point,
           const std::string& field, double actual, double expected)
{
  const bool pass = std::isfinite(actual) && std::abs(actual - expected) <= 1e-9;
  ++checks; failures += !pass;
  csv << name << ',' << point << ',' << std::setprecision(15)
      << Simulator::Now().GetSeconds() << ',' << field << ',' << actual << ','
      << expected << ',' << (pass ? 1 : 0) << '\n';
  if (!pass)
    std::cerr << "FAIL " << name << ' ' << point << ' ' << field
              << " actual=" << actual << " expected=" << expected << '\n';
}

double State(const CsrMacCore& mac)
{
  switch (mac.GetState())
    {
    case CsrMacCore::State::IDLE: return 0;
    case CsrMacCore::State::SEARCH: return 1;
    case CsrMacCore::State::TRACK: return 2;
    case CsrMacCore::State::TX: return 3;
    }
  return -1;
}

Ptr<Packet> Frame()
{
  CsrHeader header(1, 2, 1, 0, true, false);
  header.SetType(CSR_PKT_DATA); header.SetDestType(CSR_DEST_UNICAST);
  header.SetLinkControl(128, 33, -100);
  auto packet = Create<Packet>(16); packet->AddHeader(header); return packet;
}

Ptr<CsrNetDevice> Fixture()
{
  RngSeedManager::SetSeed(129); RngSeedManager::SetRun(1);
  auto device = CreateObject<CsrNetDevice>(1);
  auto& mac = device->GetMac();
  mac.SetSlotSelectionProfile(
    CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
  mac.SetActiveNodesForPostTx(3);
  mac.SetSupervisorSlotReduction(29); // Fixed input, no supervisor process.
  return device;
}

void Occupy(CsrMacCore& mac, int first)
{
  // Range2 has inclusive draw0..2. Occupy0/2 at selection to force1.
  for (CsrNodeId peer : {2, 3})
    {
      mac.NoteHeardFrom(peer, Simulator::Now().GetSeconds());
      mac.NoteHeardFrom(peer, Simulator::Now().GetSeconds());
      mac.NoteNeighborReservedSlot(peer, first + 2 * (peer - 2));
    }
}

void AfterTx(CsrMacCore& mac, const std::string& name)
{
  Check(name, "after_tx", "transmissions", mac.GetTransmittedFrameCount(), 1);
  Check(name, "after_tx", "opportunity_slot", mac.GetLastTxOpportunitySlot(), 1);
  Check(name, "after_tx", "data_queue", mac.GetDataQueuedFrameCount(), 0);
  Check(name, "after_tx", "state", State(mac), 3);
}

void IdleCase(const std::string& name, double arrival, double wake)
{
  auto device = Fixture(); auto& mac = device->GetMac();
  mac.SetReceiveState(CsrMacCore::State::IDLE); Occupy(mac, 0);
  Simulator::Schedule(Seconds(arrival), [&] {
    mac.EnqueueTxFrame(Frame(), 2, 0, true);
    Check(name, "queued", "state", State(mac), 0);
    Check(name, "queued", "preparation", mac.IsTxPreparationActive(), 0);
    Check(name, "queued", "data_queue", mac.GetDataQueuedFrameCount(), 1);
  });
  Simulator::Schedule(Seconds(wake - 1e-6), [&] {
    Check(name, "before_wake", "state", State(mac), 0);
    Check(name, "before_wake", "preparation", mac.IsTxPreparationActive(), 0);
    Check(name, "before_wake", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  Simulator::Schedule(Seconds(wake + 1e-6), [&] {
    Check(name, "prepared", "state", State(mac), 1);
    Check(name, "prepared", "preparation", mac.IsTxPreparationActive(), 1);
    Check(name, "prepared", "counter", mac.GetLocalReservationCounter(), 1);
    Check(name, "prepared", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  const double tx = wake + .325;
  Simulator::Schedule(Seconds(tx - 1e-6), [&] {
    Check(name, "before_tx", "counter", mac.GetLocalReservationCounter(), 0);
    Check(name, "before_tx", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  Simulator::Schedule(Seconds(tx + 1e-6), [&] { AfterTx(mac, name); });
  Simulator::Stop(Seconds(tx + 1e-5)); Simulator::Run(); Simulator::Destroy();
}

void AccessCase(const std::string& name, int mode)
{
  auto device = Fixture(); auto& mac = device->GetMac();
  Occupy(mac, mode == 1 || mode == 2 ? 0 : 1);
  if (mode == 1) mac.SetSyncPresent(true);
  if (mode == 2) mac.SetReceiveState(CsrMacCore::State::TRACK);
  mac.EnqueueTxFrame(Frame(), 2, 0, true);
  Check(name, "queued", "state", State(mac), 1 + (mode == 2));
  Check(name, "queued", "preparation", mac.IsTxPreparationActive(), 0);
  Check(name, "queued", "transmissions", mac.GetTransmittedFrameCount(), 0);
  Check(name, "queued", "data_queue", mac.GetDataQueuedFrameCount(), 1);
  Simulator::Schedule(Seconds(.014), [&] {
    Check(name, "prepared", "preparation", mac.IsTxPreparationActive(), mode != 2);
    Check(name, "prepared", "counter", mac.GetLocalReservationCounter(), 1 - 2 * (mode == 2));
    Check(name, "prepared", "transmissions", mac.GetTransmittedFrameCount(), 0);
    Check(name, "prepared", "state", State(mac), 1 + (mode == 2));
  });
  Simulator::Schedule(Seconds(.299), [&] {
    Check(name, "before_holdoff", "transmissions", mac.GetTransmittedFrameCount(), 0);
    Check(name, "before_holdoff", "counter", mac.GetLocalReservationCounter(), 1 - 2 * (mode == 2));
  });
  auto freeze = [&] {
    if (mode == 3) mac.SetSyncPresent(true);
    else mac.SetReceiveState(CsrMacCore::State::TRACK);
  };
  if (mode >= 3)
    {
      if (mode == 6)
        Simulator::Schedule(Seconds(.311), [&] {
          // Tick0.312 is already queued. The new equal-time Track event
          // receives a later UID, so TSLOT must execute first.
          Simulator::Schedule(Seconds(.001), freeze);
        });
      else
        Simulator::Schedule(Seconds(mode == 5 ? .312 : .310), freeze);
      Simulator::Schedule(Seconds(.399), [&] {
        Check(name, "frozen", "counter", mac.GetLocalReservationCounter(), 1 - (mode == 6));
        Check(name, "frozen", "transmissions", mac.GetTransmittedFrameCount(), 0);
        Check(name, "frozen", "preparation", mac.IsTxPreparationActive(), 1);
        Check(name, "frozen", "state", State(mac), 1 + (mode != 3));
      });
    }
  Simulator::Schedule(Seconds(mode >= 3 ? .400 : .310), [&] {
    if (mode == 1 || mode == 3) mac.SetSyncPresent(false);
    if (mode == 2 || mode == 4 || mode == 5 || mode == 6)
      mac.SetReceiveState(CsrMacCore::State::SEARCH);
    Check(name, "resume", "counter", mac.GetLocalReservationCounter(), 1 - (mode == 6));
    Check(name, "resume", "preparation", mac.IsTxPreparationActive(), 1);
    Check(name, "resume", "state", State(mac), 1);
  });
  const double tx = mode == 6 ? .403 : (mode >= 3 ? .416 : .325);
  Simulator::Schedule(Seconds(tx - 1e-6), [&] {
    Check(name, "before_tx", "counter", mac.GetLocalReservationCounter(), 0);
    Check(name, "before_tx", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  Simulator::Schedule(Seconds(tx + 1e-6), [&] { AfterTx(mac, name); });
  Simulator::Stop(Seconds(tx + 1e-5)); Simulator::Run(); Simulator::Destroy();
}

void RestartCase()
{
  const std::string name = "idle_restart";
  auto device = Fixture(); auto& mac = device->GetMac();
  Occupy(mac, 1); mac.EnqueueTxFrame(Frame(), 2, 0, true);
  Simulator::Schedule(Seconds(.014), [&] {
    Check(name, "initial", "preparation", mac.IsTxPreparationActive(), 1);
    Check(name, "initial", "counter", mac.GetLocalReservationCounter(), 1);
  });
  Simulator::Schedule(Seconds(.020), [&] {
    const auto removed = mac.CancelAcknowledgedFrames(2, 1, 1, 0);
    mac.SetReceiveState(CsrMacCore::State::IDLE);
    Check(name, "idle", "removed", removed, 1);
    Check(name, "idle", "preparation", mac.IsTxPreparationActive(), 0);
    Check(name, "idle", "state", State(mac), 0);
  });
  Simulator::Schedule(Seconds(.025), [&] {
    Occupy(mac, 1); mac.SetReceiveState(CsrMacCore::State::SEARCH);
    mac.EnqueueTxFrame(Frame(), 2, 0, true);
    Check(name, "restart", "preparation", mac.IsTxPreparationActive(), 0);
    Check(name, "restart", "state", State(mac), 1);
  });
  Simulator::Schedule(Seconds(.038 - 1e-6), [&] {
    Check(name, "before_new_tick", "preparation", mac.IsTxPreparationActive(), 0);
    Check(name, "before_new_tick", "neighbor_counter", mac.GetNeighborReservationCounter(2), 1);
  });
  Simulator::Schedule(Seconds(.038 + 1e-6), [&] {
    Check(name, "new_tick", "preparation", mac.IsTxPreparationActive(), 1);
    Check(name, "new_tick", "counter", mac.GetLocalReservationCounter(), 1);
    Check(name, "new_tick", "neighbor_counter", mac.GetNeighborReservationCounter(2), 0);
  });
  Simulator::Schedule(Seconds(.350 - 1e-6), [&] {
    Check(name, "before_tx", "counter", mac.GetLocalReservationCounter(), 0);
    Check(name, "before_tx", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  Simulator::Schedule(Seconds(.350 + 1e-6), [&] { AfterTx(mac, name); });
  Simulator::Stop(Seconds(.35001)); Simulator::Run(); Simulator::Destroy();
}
}

int main(int argc, char** argv)
{
  if (argc != 2) { std::cerr << "usage: tranche10_contention_contract checkpoints.csv\n"; return 2; }
  Time::SetResolution(Time::NS); csv.open(argv[1]); if (!csv) return 2;
  csv << "case,checkpoint,time_seconds,field,actual,expected,pass\n";
  IdleCase("idle_p15", 15 * .013, .208);
  IdleCase("idle_literal", .195, .208);
  IdleCase("idle_p30", 30 * .013, .403);
  IdleCase("idle_p51", 51 * .013, .676);
  IdleCase("idle_p60", 60 * .013, .793);
  IdleCase("idle_before", .195 - 1e-9, .195);
  IdleCase("idle_after", .195 + 1e-9, .208);
  AccessCase("search_initial", 0); AccessCase("sync_initial", 1);
  AccessCase("track_initial", 2); AccessCase("sync_busy", 3);
  AccessCase("track_busy", 4); AccessCase("track_tie_early", 5);
  AccessCase("track_tie_late", 6); RestartCase();
  csv.flush();
  std::cout << "CONTRACT_SUMMARY checks=" << checks << " failed=" << failures << '\n';
  return failures ? 1 : 0;
}
