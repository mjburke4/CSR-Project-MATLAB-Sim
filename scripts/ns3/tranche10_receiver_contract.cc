// Fixed-TX receiver timing through the unmodified pinned CSR public APIs.
// Source BER/ECC remain enabled. Only stochastic SYNC sampling is disabled.
// No forced slot, custom error/closure hook, HOP feedback, or RNG equivalence.
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

struct CaseContext
{
  std::string name;
  Ptr<CsrNetDevice> receiver;
  unsigned received = 0;
  double receiveEnd = 0;
};
CaseContext* context = nullptr;

void Check(const std::string& name, const std::string& checkpoint,
           const std::string& field, double actual, double expected)
{
  const double tolerance = field.ends_with("_seconds") ? 1e-12 : 0;
  const bool pass = std::isfinite(actual) && std::abs(actual - expected) <= tolerance;
  ++checks;
  failures += !pass;
  csv << name << ',' << checkpoint << ',' << std::setprecision(17)
      << Simulator::Now().GetSeconds() << ',' << field << ',' << actual << ','
      << expected << ',' << (pass ? 1 : 0) << '\n';
  if (!pass)
    std::cerr << "FAIL " << name << ' ' << checkpoint << ' ' << field
              << " actual=" << actual << " expected=" << expected << '\n';
}

bool IsState(CsrMacCore::State state)
{
  return context->receiver->GetMacState() == state;
}

bool HasSync()
{
  return context->receiver->GetMac().IsSyncPresent();
}

void Receive(Ptr<Packet> packet, double, double)
{
  ++context->received;
  CsrHeader header;
  packet->PeekHeader(header);
  const auto& decision = context->receiver->GetLastRxDecision();
  const auto& name = context->name;
  Check(name, "delivery", "received", context->received, 1);
  Check(name, "delivery", "sequence", header.GetSeq(), 1);
  Check(name, "delivery", "track", IsState(CsrMacCore::State::TRACK), 1);
  Check(name, "delivery", "time_seconds", Simulator::Now().GetSeconds(), context->receiveEnd);
  Check(name, "delivery", "success", decision.success, 1);
  Check(name, "delivery", "header_ber", decision.headerBer, 0);
  Check(name, "delivery", "payload_ber", decision.payloadBer, 0);
  Check(name, "delivery", "header_errors", decision.headerErrors, 0);
  Check(name, "delivery", "payload_errors", decision.payloadErrors, 0);
  Check(name, "delivery", "sync_present", HasSync(), 0);
}

Ptr<Packet> Frame()
{
  CsrHeader header(2, 1, 1, 0, false, false);
  header.SetType(CSR_PKT_DATA);
  header.SetDestType(CSR_DEST_UNICAST);
  header.SetSpeedKey(128);
  auto packet = Create<Packet>(585);
  packet->AddHeader(header);
  CsrSetOpnetEnvelope(packet, CsrOpnetPacketFormat::Mac, 617);
  return packet;
}

void ReceiverCase(const std::string& name, double txAt, double trackAt,
                  bool missFirstWindow)
{
  RngSeedManager::SetSeed(129);
  RngSeedManager::SetRun(1);
  auto receiver = CreateObject<CsrNetDevice>(1);
  auto transmitter = CreateObject<CsrNetDevice>(2);
  for (auto device : {receiver, transmitter})
    {
      CsrPhyProfile profile;
      profile.stochasticSyncThreshold = false;
      profile.txPowerDbm = 33;
      device->GetPhy().SetProfile(profile);
      device->GetPhy().SetLinkDistanceMeters(1, 2, 1200);
    }
  transmitter->SetPeer(receiver);
  receiver->GetMac().SetRxCallback(MakeCallback(&Receive));
  receiver->EnableOpnetAlignedDutyCycling(true);
  auto packet = Frame();
  const double arrivalAt = txAt + 4e-6;
  const double preambleEnd = arrivalAt + 1.005720;
  const double receiveEnd = arrivalAt + 1.049100;
  const double probe = 1e-9;
  CaseContext local{name, receiver, 0, receiveEnd};
  context = &local;
  Check(name, "initial", "idle", IsState(CsrMacCore::State::IDLE), 1);
  Check(name, "initial", "sync_present", HasSync(), 0);
  Check(name, "initial", "received", local.received, 0);
  Check(name, "initial", "wire_bytes", CsrGetOpnetWireSize(packet), 617);
  Simulator::Schedule(Seconds(txAt), [=] {
    Time duration = transmitter->SendToPeer(packet, 1, 128, 33, PREAMBLE_LONG, -1, false);
    Check(name, "transmit", "duration_seconds", duration.GetSeconds(), 1.049100);
  });
  Simulator::Schedule(Seconds(arrivalAt-probe), [=] {
    Check(name, "before_arrival", "sync_present", HasSync(), 0);
  });
  Simulator::Schedule(Seconds(arrivalAt+probe), [=] {
    Check(name, "after_arrival", "sync_present", HasSync(), 1);
    Check(name, "after_arrival", "idle", IsState(CsrMacCore::State::IDLE), txAt < .988);
  });
  Simulator::Schedule(Seconds(.988-probe), [=] {
    Check(name, "before_wake", "idle", IsState(CsrMacCore::State::IDLE), 1);
  });
  Simulator::Schedule(Seconds(.988+probe), [=] {
    Check(name, "after_wake", "search", IsState(CsrMacCore::State::SEARCH), 1);
  });
  Simulator::Schedule(Seconds(trackAt-probe), [=] {
    Check(name, "before_track", "search", IsState(CsrMacCore::State::SEARCH), 1);
    Check(name, "before_track", "received", context->received, 0);
  });
  Simulator::Schedule(Seconds(trackAt+probe), [=] {
    Check(name, "after_track", "track", IsState(CsrMacCore::State::TRACK), 1);
  });
  Simulator::Schedule(Seconds(.996900+probe), [=] {
    Check(name, "after_first_sleep", "idle", IsState(CsrMacCore::State::IDLE), missFirstWindow);
    Check(name, "after_first_sleep", "sync_present", HasSync(), 1);
    Check(name, "after_first_sleep", "received", context->received, 0);
  });
  if (missFirstWindow)
    {
      Simulator::Schedule(Seconds(1.976-probe), [=] {
        Check(name, "before_second_wake", "idle", IsState(CsrMacCore::State::IDLE), 1);
      });
      Simulator::Schedule(Seconds(1.976+probe), [=] {
        Check(name, "after_second_wake", "search", IsState(CsrMacCore::State::SEARCH), 1);
      });
    }
  Simulator::Schedule(Seconds(preambleEnd-probe), [=] {
    Check(name, "before_preamble_end", "sync_present", HasSync(), 1);
    Check(name, "before_preamble_end", "track", IsState(CsrMacCore::State::TRACK), 1);
  });
  Simulator::Schedule(Seconds(preambleEnd+probe), [=] {
    Check(name, "after_preamble_end", "sync_present", HasSync(), 0);
    Check(name, "after_preamble_end", "track", IsState(CsrMacCore::State::TRACK), 1);
  });
  Simulator::Schedule(Seconds(receiveEnd-probe), [=] {
    Check(name, "before_end", "track", IsState(CsrMacCore::State::TRACK), 1);
    Check(name, "before_end", "received", context->received, 0);
  });
  Simulator::Schedule(Seconds(receiveEnd+probe), [=] {
    Check(name, "after_end", "search", IsState(CsrMacCore::State::SEARCH), 1);
    Check(name, "after_end", "received", context->received, 1);
    Check(name, "after_end", "sync_present", HasSync(), 0);
  });
  Simulator::Schedule(Seconds(receiveEnd+.0078-probe), [=] {
    Check(name, "before_sleep", "search", IsState(CsrMacCore::State::SEARCH), 1);
  });
  Simulator::Schedule(Seconds(receiveEnd+.0078+probe), [=] {
    Check(name, "after_sleep", "idle", IsState(CsrMacCore::State::IDLE), 1);
    Check(name, "after_sleep", "received", context->received, 1);
  });
  Simulator::Stop(Seconds(receiveEnd+.008));
  Simulator::Run();
  Simulator::Destroy();
  context = nullptr;
}
} // namespace

int main(int argc, char** argv)
{
  if (argc != 2)
    {
      std::cerr << "Usage: tranche10-receiver-contract checkpoints.csv\n";
      return 2;
    }
  csv.open(argv[1]);
  if (!csv)
    {
      std::cerr << "Cannot open checkpoint output\n";
      return 2;
    }
  csv << "case,checkpoint,time_seconds,field,actual,expected,pass\n";
  ReceiverCase("preamble_before_wake", .962, .994630, false);
  ReceiverCase("preamble_at_wake", .988, .994634, false);
  ReceiverCase("preamble_after_wake", .990, .996634, false);
  ReceiverCase("acquisition_canceled_by_sleep", .991, 1.982630, true);
  csv.close();
  if (!csv)
    {
      std::cerr << "Cannot close checkpoint output\n";
      return 2;
    }
  std::cout << "RECEIVER_CONTRACT_CHECKS=" << checks
            << " FAILURES=" << failures << '\n';
  return failures ? 1 : 0;
}
