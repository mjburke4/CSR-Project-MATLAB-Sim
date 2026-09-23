// Public API only: prescribed decoded HOP ingress, real single-node MAC/HOP.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include <array>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace ns3;
struct Probe {
  std::string name; std::ofstream* out;
  Ptr<CsrNetDevice> device; Ptr<CsrHopLayer> hop;
  unsigned delivered=0,released=0; bool haveLast=false;
  std::array<uint64_t,8> last{};
  void Delivery(Ptr<Packet>,CsrNodeId) { ++delivered; }
  void Release(CsrNodeId,CsrNodeId) { ++released; }
  void Observe(std::string event) {
    auto& mac=device->GetMac(); auto a=hop->GetDataAdmissionSnapshot(1);
    std::array<uint64_t,8> values={mac.GetTransmittedFrameCount(),
      mac.GetAckQueuedFrameCount(),mac.GetDataQueuedFrameCount(),
      hop->GetPendingDataCount(),a.neighborOutstanding,a.neighborThreshold,released,delivered};
    if(event=="state" && haveLast && values==last)return;
    haveLast=true;last=values;
    *out<<name<<','<<std::setprecision(17)<<Simulator::Now().GetSeconds()<<','<<event;
    for(auto value:values)*out<<','<<value;
    *out<<'\n';
  }
  void Upstream(unsigned sequence) {
    auto p=Create<Packet>(185);p->AddHeader(CsrNetHeader(8,2,0));
    CsrHeader h(8,2,sequence,0,true,false);
    h.SetType(CSR_PKT_DATA);h.SetDestType(CSR_DEST_UNICAST);h.SetLinkControl(8,33,-100);
    p->AddHeader(h);CsrSetOpnetEnvelope(p,CsrOpnetPacketFormat::Hop,217);
    Observe("upstream_before");hop->ReceiveFromMac(p,70,30);Observe("upstream_after");
  }
  void Feedback() {
    auto p=Create<Packet>();CsrHeader h(1,2,1,0,false,true);
    h.SetType(CSR_PKT_ACK);h.SetDestType(CSR_DEST_UNICAST);h.SetLinkControl(8,33,-100);
    h.SetHasAckWindow(true);h.SetAckBitmap(1);h.SetDackBitmap(0);
    p->AddHeader(h);CsrSetOpnetEnvelope(p,CsrOpnetPacketFormat::Ack,41);
    Observe("feedback_before");hop->ReceiveFromMac(p,70,30);Observe("feedback_after");
  }
};
int main(int argc,char** argv) {
  if(argc!=3)throw std::runtime_error("Usage: hop_replay INPUT.csv OUTPUT.csv");
  std::ifstream input(argv[1]);std::ofstream output(argv[2]);
  if(!input||!output)throw std::runtime_error("Cannot open input/output");
  output<<"case_id,observed_time_s,event,mac_tx,ack_queue,data_queue,hop_pending,neighbor_outstanding,neighbor_threshold,released,delivered\n";
  std::string line;std::getline(input,line);
  if(line!="case_id,upstream_first_s,upstream_second_s,feedback_s,stop_s,feedback_effect" &&
     line!="case_id,upstream_first_s,upstream_second_s,feedback_s,stop_s,feedback_effect\r")
    throw std::runtime_error("Unexpected replay schema");
  while(std::getline(input,line)) {
    if(line.empty())continue;std::stringstream parser(line);std::vector<std::string> fields;
    std::string part;while(std::getline(parser,part,','))fields.push_back(part);
    if(fields.size()!=6)throw std::runtime_error("Malformed replay input");
    if(fields[5]!="ack" && fields[5]!="expired" && fields[5]!="ack\r" && fields[5]!="expired\r")throw std::runtime_error("Unknown feedback effect");
    double first=std::stod(fields[1]),second=std::stod(fields[2]);
    double feedback=std::stod(fields[3]),stop=std::stod(fields[4]);
    RngSeedManager::SetSeed(132);RngSeedManager::SetRun(1);
    Probe probe;probe.name=fields[0];probe.out=&output;
    probe.device=CreateObject<CsrNetDevice>(2);probe.hop=CreateObject<CsrHopLayer>();
    auto& mac=probe.device->GetMac();probe.hop->SetNodeId(2);probe.hop->SetMac(&mac);
    probe.hop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
    probe.hop->ConfigureLinkControl(8,8,33,33,6);
    probe.hop->SetRxFromHopCallback(MakeCallback(&Probe::Delivery,&probe));
    probe.hop->SetNsdpDecrementCallback(MakeCallback(&Probe::Release,&probe));
    csr_t11::rawDraw=[](uint32_t node,int lo,int hi){ if(node!=2 || lo!=1 || hi<1)throw std::runtime_error("Unexpected draw domain"); return 1; };mac.SetActiveNodesForPostTx(3);
    auto p=Create<Packet>(185);p->AddHeader(CsrNetHeader(2,1,0));
    probe.hop->SendData(1,0,p,true);
    if(probe.hop->GetPendingDataCount()!=1)throw std::runtime_error("HOP admission failed");
    probe.Observe("admit");
    if(first>=0)Simulator::Schedule(Seconds(first),&Probe::Upstream,&probe,13);
    if(second>=0)Simulator::Schedule(Seconds(second),&Probe::Upstream,&probe,14);
    Simulator::Schedule(Seconds(feedback),&Probe::Feedback,&probe);
    for(int tick=1;tick<=static_cast<int>(stop*1000+.5);++tick)
      Simulator::Schedule(MilliSeconds(tick),&Probe::Observe,&probe,std::string("state"));
    Simulator::Stop(Seconds(stop+.000001));Simulator::Run();probe.Observe("final");
    Simulator::Destroy();
  }
}
