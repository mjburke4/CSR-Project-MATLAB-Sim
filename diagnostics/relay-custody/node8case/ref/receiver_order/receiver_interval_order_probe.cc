#include "ns3/core-module.h"
#include "ns3/csr-common.h"
#include "ns3/csr-net-device.h"
#include <iostream>
using namespace ns3;
int main(int argc, char** argv) {
  const bool ascending = argc > 1 && std::string(argv[1]) == "ascending";
  RngSeedManager::SetSeed(132); RngSeedManager::SetRun(1);
  auto lower=CreateObject<CsrNetDevice>(1);
  auto higher=CreateObject<CsrNetDevice>(2);
  auto receiver=CreateObject<CsrNetDevice>(3);
  int64_t stream=0;
  for (auto dev : {lower,higher,receiver}) {
    stream += dev->AssignStreams(stream);
    CsrPhyProfile profile; profile.stochasticSyncThreshold=false; profile.noiseFloorDbm=0.0;
    dev->GetPhy().SetProfile(profile); dev->EnableDutyCycling(false);
    dev->GetPhy().SetLinkDistanceMeters(1,3,1.0);
    dev->GetPhy().SetLinkDistanceMeters(2,3,1.0);
    dev->GetPhy().SetLinkDistanceMeters(1,2,0.0);
  }
  lower->AddPeer(receiver); higher->AddPeer(receiver);
  const auto send=[](Ptr<CsrNetDevice> source) {
    CsrHeader hdr; hdr.SetSrc(source->GetId()); hdr.SetDst(3); hdr.SetSeq(1);
    hdr.SetDscp(0); hdr.SetAckable(false); hdr.SetType(CSR_PKT_DATA);
    hdr.SetDestType(CSR_DEST_UNICAST);
    auto packet=Create<Packet>(185); packet->AddHeader(hdr);
    std::cout << "PROBE source=" << source->GetId() << " wire_bytes=" << CsrGetOpnetWireSize(packet) << std::endl;
    source->SendToPeer(packet,3,8,0.0,PREAMBLE_SHORT,0,false);
  };
  Simulator::Schedule(Seconds(0),[=]{send(ascending ? lower : higher);});
  Simulator::Schedule(Seconds(0.026009895),[=]{send(ascending ? higher : lower);});
  Simulator::Stop(Seconds(0.4)); Simulator::Run(); Simulator::Destroy();
  if (Sc::stream.is_open()) Sc::stream.close();
  std::cout << "PROBE completed" << std::endl;
}
