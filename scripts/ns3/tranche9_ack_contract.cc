// Public-API ACK service contracts against unmodified pinned CSR headers.
// Receiver states and feedback arrivals are prescribed. No RF delivery claim.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

using namespace ns3;

namespace {
std::ofstream csv;
unsigned checks = 0, failures = 0;
Ptr<CsrHopLayer> releaseHop;
Ptr<CsrNetDevice> releaseDevice;
unsigned releases = 0, wakes = 0;

void Check(const std::string& name, const std::string& checkpoint,
           const std::string& field, double actual, double expected)
{
  const bool pass = std::isfinite(actual) && std::abs(actual - expected) <= 1e-9;
  ++checks;
  failures += !pass;
  csv << name << ',' << checkpoint << ',' << std::setprecision(15)
      << Simulator::Now().GetSeconds() << ',' << field << ',' << actual << ','
      << expected << ',' << (pass ? 1 : 0) << '\n';
  if (!pass)
    std::cerr << "FAIL " << name << ' ' << checkpoint << ' ' << field
              << " actual=" << actual << " expected=" << expected << '\n';
}

Ptr<Packet> Frame(uint16_t sequence, bool ack)
{
  CsrHeader header(1, 2, sequence, 0, !ack, ack);
  header.SetType(ack ? CSR_PKT_ACK : CSR_PKT_DATA);
  header.SetDestType(CSR_DEST_UNICAST);
  header.SetLinkControl(128, 33, -100);
  if (ack)
    {
      header.SetHasAckWindow(true);
      header.SetAckBitmap(sequence == 10 ? 1 : 3);
      header.SetDackBitmap(0);
    }
  auto packet = Create<Packet>(ack ? 0 : 16);
  packet->AddHeader(header);
  return packet;
}

Ptr<Packet> ControlFrame()
{
  auto packet = Frame(7, false);
  CsrHeader header;
  packet->RemoveHeader(header);
  header.SetType(CSR_PKT_KEY_REQUEST);
  header.SetAckable(false);
  packet->AddHeader(header);
  return packet;
}

void Occupy(CsrMacCore& mac)
{
  // With range2 the inclusive draw0..2 has one free result: slot1.
  // Next tick decrements the prescribed neighbor counters1/3 to0/2.
  mac.NoteNeighborReservedSlot(2, 1);
  mac.NoteNeighborReservedSlot(3, 3);
}

void MacCase(const std::string& name, int freeze, bool cancel, bool control = false)
{
  RngSeedManager::SetSeed(129);
  RngSeedManager::SetRun(1);
  auto device = CreateObject<CsrNetDevice>(1);
  auto& mac = device->GetMac();
  mac.SetSlotSelectionProfile(
    CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
  mac.SetActiveNodesForPostTx(3);
  mac.SetSupervisorSlotReduction(29); // A fixed fixture input, no supervisor process.
  for (CsrNodeId peer : {2, 3})
    {
      mac.NoteHeardFrom(peer, 0);
      mac.NoteHeardFrom(peer, 0);
    }
  Occupy(mac);
  mac.EnqueueTxFrame(control ? ControlFrame() : Frame(cancel ? 7 : 10, !cancel),
                     2, 0, cancel && !control);
  Simulator::Schedule(Seconds(.014), [&] {
    Check(name, "prepared", "counter", mac.GetLocalReservationCounter(), 1);
    Check(name, "prepared", "preparation", mac.IsTxPreparationActive(), 1);
    Check(name, "prepared", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  if (!cancel)
    Simulator::Schedule(Seconds(.200), [&] {
      mac.EnqueueTxFrame(Frame(11, true), 2, 0, false);
      Check(name, "replaced", "ack_queue", mac.GetAckQueuedFrameCount(), 1);
      Check(name, "replaced", "counter", mac.GetLocalReservationCounter(), 1);
    });
  Simulator::Schedule(Seconds(.299), [&] {
    Check(name, "before_holdoff", "transmissions", mac.GetTransmittedFrameCount(), 0);
  });
  if (freeze)
    {
      Simulator::Schedule(Seconds(.310), [&] {
        if (freeze == 1) mac.SetSyncPresent(true);
        else mac.SetReceiveState(CsrMacCore::State::TRACK);
      });
      Simulator::Schedule(Seconds(.399), [&] {
        Check(name, "frozen", "counter", mac.GetLocalReservationCounter(), 1);
        Check(name, "frozen", "transmissions", mac.GetTransmittedFrameCount(), 0);
      });
      Simulator::Schedule(Seconds(.400), [&] {
        if (freeze == 1) mac.SetSyncPresent(false);
        else mac.SetReceiveState(CsrMacCore::State::SEARCH);
        Check(name, "resume", "preparation", mac.IsTxPreparationActive(), 1);
      });
    }
  if (cancel)
    {
      Simulator::Schedule(Seconds(.315), [&] {
        const auto removed = control
          ? mac.CancelQueuedFramesByType(2, CSR_PKT_KEY_REQUEST)
          : mac.CancelAcknowledgedFrames(2, 7, 1, 0);
        Check(name, "canceled", "removed", removed, 1);
        Check(name, "canceled", "data_queue", mac.GetDataQueuedFrameCount(), 0);
        Check(name, "canceled", "preparation", mac.IsTxPreparationActive(), 1);
        Check(name, "canceled", "counter", mac.GetLocalReservationCounter(), 0);
      });
      Simulator::Schedule(Seconds(.320), [&] {
        mac.EnqueueTxFrame(Frame(11, true), 2, 0, false);
        Check(name, "new_ack", "ack_queue", mac.GetAckQueuedFrameCount(), 1);
        Check(name, "new_ack", "preparation", mac.IsTxPreparationActive(), 1);
      });
    }
  const double tx = freeze ? .416 : .325;
  Simulator::Schedule(Seconds(tx - .001), [&] { Occupy(mac); });
  Simulator::Schedule(Seconds(tx - .000001), [&] {
    Check(name, "before_tx", "transmissions", mac.GetTransmittedFrameCount(), 0);
    Check(name, "before_tx", "counter", mac.GetLocalReservationCounter(), 0);
  });
  Simulator::Schedule(Seconds(tx + .000001), [&] {
    Check(name, "after_tx", "transmissions", mac.GetTransmittedFrameCount(), 1);
    Check(name, "after_tx", "advertised_slot", mac.GetLastAdvertisedReservationSlot(), 1);
    Check(name, "after_tx", "ack_queue", mac.GetAckQueuedFrameCount(), 1);
    Check(name, "after_tx", "data_queue", mac.GetDataQueuedFrameCount(), 0);
    Check(name, "after_tx", "rate_key_kbps", mac.GetLastTxRateKbps(), 128);
    Check(name, "after_tx", "power_dbm", mac.GetLastTxPowerDbm(), 33);
  });
  Simulator::Stop(Seconds(tx + .00001));
  Simulator::Run();
  Simulator::Destroy();
}

void Release(CsrNodeId source, CsrNodeId destination)
{
  ++releases;
  const auto s = releaseHop->GetDataAdmissionSnapshot(2);
  Check("hop_release_order", "nsdp_callback", "source", source, 1);
  Check("hop_release_order", "nsdp_callback", "destination", destination, 3);
  Check("hop_release_order", "nsdp_callback", "pending", s.pendingData, 0);
  Check("hop_release_order", "nsdp_callback", "outstanding", s.neighborOutstanding, 0);
  Check("hop_release_order", "nsdp_callback", "resend_queue", releaseHop->GetResendQueueSize(), 1);
  Check("hop_release_order", "nsdp_callback", "mac_queue", releaseDevice->GetMac().GetDataQueuedFrameCount(), 1);
}

void Wake() { ++wakes; }

void HopCase()
{
  releases = wakes = 0;
  releaseDevice = CreateObject<CsrNetDevice>(1);
  releaseHop = CreateObject<CsrHopLayer>();
  releaseHop->SetNodeId(1);
  releaseHop->SetMac(&releaseDevice->GetMac());
  releaseHop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
  releaseHop->SetNsdpDecrementCallback(MakeCallback(&Release));
  releaseHop->SetNwkQueueWakeCallback(MakeCallback(&Wake));
  releaseDevice->GetMac().SetReceiveState(CsrMacCore::State::TRACK);
  auto payload = Create<Packet>(16);
  payload->AddHeader(CsrNetHeader(1, 3, 0));
  releaseHop->SendData(2, 0, payload, true);
  Check("hop_release_order", "admitted", "pending", releaseHop->GetPendingDataCount(), 1);
  Check("hop_release_order", "admitted", "can_send", releaseHop->CanSendToHop(2), 0);
  Simulator::Schedule(Seconds(.100), [] {
    CsrHeader header(2, 1, 1, 0, false, true);
    header.SetType(CSR_PKT_ACK);
    header.SetDestType(CSR_DEST_UNICAST);
    header.SetHasAckWindow(true);
    header.SetAckBitmap(1);
    header.SetDackBitmap(0);
    header.SetSpeedKey(128);
    auto ack = Create<Packet>();
    ack->AddHeader(header);
    releaseHop->ReceiveFromMac(ack->Copy(), 70, 20);
    // Duplicate feedback must not release the same capacity twice or add a wake.
    releaseHop->ReceiveFromMac(ack->Copy(), 70, 20);
    Check("hop_release_order", "completed", "pending", releaseHop->GetPendingDataCount(), 0);
    Check("hop_release_order", "completed", "resend_queue", releaseHop->GetResendQueueSize(), 0);
    Check("hop_release_order", "completed", "mac_queue", releaseDevice->GetMac().GetDataQueuedFrameCount(), 0);
    Check("hop_release_order", "completed", "can_send", releaseHop->CanSendToHop(2), 1);
    Check("hop_release_order", "completed", "releases", releases, 1);
    Check("hop_release_order", "completed", "wakes", wakes, 0);
  });
  Simulator::Schedule(Seconds(.100000001), [] {
    Check("hop_release_order", "before_tic", "wakes", wakes, 0);
  });
  Simulator::Schedule(Seconds(.100000100), [] {
    Check("hop_release_order", "after_tic", "wakes", wakes, 1);
    Check("hop_release_order", "after_tic", "can_send", releaseHop->CanSendToHop(2), 1);
  });
  Simulator::Stop(Seconds(.101));
  Simulator::Run();
  Simulator::Destroy();
  releaseHop = nullptr;
  releaseDevice = nullptr;
}
}

int main(int argc, char** argv)
{
  if (argc != 2) { std::cerr << "usage: tranche9_ack_contract checkpoints.csv\n"; return 2; }
  Time::SetResolution(Time::NS);
  csv.open(argv[1]);
  if (!csv) return 2;
  csv << "case,checkpoint,time_seconds,field,actual,expected,pass\n";
  MacCase("mac_ack_wait", 0, false);
  MacCase("mac_ack_sync", 1, false);
  MacCase("mac_ack_track", 2, false);
  MacCase("mac_cancel_then_ack", 0, true);
  MacCase("mac_control_cancel_then_ack", 0, true, true);
  HopCase();
  csv.flush();
  std::cout << "CONTRACT_SUMMARY checks=" << checks << " failed=" << failures << '\n';
  return failures ? 1 : 0;
}
