#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-nwk-layer.h"
#include "ns3/csr-arl-routing-message.h"
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
using namespace ns3;

// Public-API component harness: unattached MAC, no device/channel/PHY, no
// private-state access. Run drains only same-time NWK work under a 1-ns stop.
// Keys and reliable completions use actual authenticated HOP receive APIs.
void require(bool yes,const char* text) {
  if(!yes){std::cerr<<"FAIL: "<<text<<'\n';std::exit(1);}
}
std::string caseName;
std::vector<CsrRoutingOperation> observedOps;
const char* operationName(CsrRoutingOperation operation){return operation==CsrRoutingOperation::Delete?"Delete":"Update";}
void record(std::vector<CsrNodeId> peers,Ptr<Packet> p) {
  CsrHelloHeader h; require(p->RemoveHeader(h)>0,"grouped payload header");
  std::vector<uint8_t> bytes(p->GetSize());p->CopyData(bytes.data(),bytes.size());
  CsrArlRoutingMessage::Section section;std::string error;
  require(CsrArlRoutingMessage::DecodeSection(bytes,section,&error),"grouped section decode");
  std::vector<CsrArlRoutingMessage::Record> records;
  require(CsrArlRoutingMessage::ParseRecordStream(section.body,records,&error),"grouped record decode");
  for(const auto& r:records){
    if(r.nodeId==1 && (r.operation==CsrRoutingOperation::Delete || r.operation==CsrRoutingOperation::Update)){
      observedOps.push_back(r.operation);
      std::cout<<"GROUP_RECORD "<<caseName<<' '<<operationName(r.operation)
               <<" destination="<<r.nodeId<<" recipients="<<peers.size()<<'\n';
    }
  }
}
void drain(){Simulator::Stop(NanoSeconds(1));Simulator::Run();}
Ptr<Packet> makeHello(CsrNodeId peer=1){
  CsrHelloHeader h;h.SetNodeId(peer);h.SetHelloSeq(1);h.SetNodeType(CsrNodeType::Routable);
  h.SetSpeedKey(8);h.SetRxPowerDbmX10(-1030);h.SetActiveNodes(2);
  h.SetArlRouteMsgType(CsrArlRouteMsgType::NeighborCheck);h.SetNeighborCheckType(CsrNeighborCheckType::Overheard);
  auto p=Create<Packet>();p->AddHeader(h);return p;
}
Ptr<Packet> selfUpdate(){
  CsrArlRoutingMessage::Builder b;std::string error;
  require(b.AddUpdate(1,1,0,0,{},&error),"self capability encode");
  std::vector<std::vector<uint8_t>> sections;
  require(b.BuildSections(1,sections,&error)&&sections.size()==1,"self update section");
  auto p=Create<Packet>(sections[0].data(),sections[0].size());
  CsrHelloHeader h;h.SetNodeId(1);h.SetHelloSeq(2);h.SetNodeType(CsrNodeType::Routable);
  h.SetSpeedKey(8);h.SetRxPowerDbmX10(-1030);h.SetActiveNodes(2);
  h.SetArlRouteMsgType(CsrArlRouteMsgType::RoutingUpdate);
  h.SetRoutingSequence(1);h.SetRoutingSection(0);h.SetRoutingTotalSections(1);
  h.SetRoutingOperation(CsrRoutingOperation::Update);p->AddHeader(h);return p;
}
void ack(Ptr<CsrHopLayer> hop,uint16_t seq){
  auto p=Create<Packet>();CsrHeader h(1,5,seq,7,false,true);p->AddHeader(h);
  hop->ReceiveFromMac(p,140.876,-0.900945);
}
uint32_t currentPopulation(Ptr<CsrNetLayer> nwk){
  auto payloads=nwk->BuildArlRoutingSnapshotPayloadsForTest(77);
  require(!payloads.empty(),"snapshot observation empty");
  CsrHelloHeader h;require(payloads[0]->PeekHeader(h)>0,"snapshot header missing");
  return h.GetActiveNodes();
}
void run(int mode){
  caseName=mode==0?"absent_candidate":mode==1?"observed_capability_zero":"observed_capability_one";
  observedOps.clear();std::cout<<"CASE_BEGIN "<<caseName<<'\n';
  CsrMacCore mac;mac.SetNodeId(5);
  mac.SetSlotSelectionProfile(CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
  auto hop=CreateObject<CsrHopLayer>();hop->SetNodeId(5);hop->SetMac(&mac);
  hop->SetHopWireProfile(CsrHopWireProfile::HIST_ADB97C54_BARE);
  auto nwk=CreateObject<CsrNetLayer>();nwk->SetNodeId(5);nwk->SetHop(hop);
  nwk->SetAutomaticRoutePropagationEnabled(true);
  nwk->SetAutomaticRoutingControlObserverForTest(MakeCallback(&record));
  // A separate directly observed peer establishes the original 2->3 count
  // scale without changing admission or sequences for the peer under test.
  nwk->ProcessHello(makeHello(9),9,140.876,-0.900945);drain();
  require(mac.GetActiveNodesForSlotting()==2,"initial publication must be two");

  CsrHopSecurityState peer;peer.SetNodeId(1);
  auto key=Create<Packet>();key->AddHeader(peer.BuildKeyUpdate(5));
  CsrHeader h(1,5,1,7,true,false);h.SetType(CSR_PKT_KEY_UPDATE);h.SetSecurityCount(peer.GetOwnSecurityCount());key->AddHeader(h);
  hop->ReceiveFromMac(key,140.876,-0.900945);ack(hop,1);
  require(hop->HasGroupKeySentTo(1)&&hop->HasGroupKeyReceivedFrom(1),"two-sided key exchange");
  if(mode>0)nwk->ProcessHello(makeHello(),1,140.876,-0.900945);
  if(mode==2)nwk->ProcessHello(selfUpdate(),1,140.876,-0.900945);
  drain();observedOps.clear();
  uint32_t cost=0;
  require(!nwk->GetSelectedRouteCost(1,cost),"inactive peer route must not be selectable");
  // ACK the actual outgoing Overheard seq2. It refreshes NWK last-heard,
  // admits the peer and queues snapshot work; there is no radio transmission.
  ack(hop,2);
  require(nwk->IsArlNeighborActive(1),"proof ACK must admit peer");
  const auto current=currentPopulation(nwk);const auto published=mac.GetActiveNodesForSlotting();
  require(current==3,"proof ACK must expose population three to routing payloads");
  require(published==(mode==0?2:3),"proof ACK must preserve prior MAC publication");
  require(nwk->GetSelectedRouteCost(1,cost)==(mode>0),"admission must not synthesize missing route");
  std::cout<<"POPULATION "<<caseName<<" current="<<current<<" published="<<published<<'\n';
  drain();
  if(mode==0){
    require(observedOps.empty(),"absent admission must not send DELETE/UPDATE");
    std::cout<<"ROUTE_ADMISSION "<<caseName<<" grouped_operations=0 selectable=0\n";
    nwk->ProcessHello(makeHello(),1,140.876,-0.900945);
    require(mac.GetActiveNodesForSlotting()==3,"later HELLO must publish three");
    require(nwk->GetSelectedRouteCost(1,cost),"later HELLO must create direct route");
    drain();require(observedOps.size()==1&&observedOps[0]==CsrRoutingOperation::Delete,"later capability-zero HELLO creates DELETE change");
    std::cout<<"LATER_HELLO "<<caseName<<" published=3 selectable=1 grouped_operation=Delete\n";
  }else{
    const auto expected=mode==1?CsrRoutingOperation::Delete:CsrRoutingOperation::Update;
    require(observedOps.size()==1&&observedOps[0]==expected,"observed candidate admission must emit matching change");
    std::cout<<"ROUTE_ADMISSION "<<caseName<<" grouped_operations=1 selectable=1 operation="<<operationName(expected)<<'\n';
  }
  std::cout<<"CASE_END "<<caseName<<" PASS\n";
  Simulator::Destroy();
}
int main(){run(0);run(1);run(2);std::cout<<"ALL_COMPONENT_CASES_PASS\n";}
