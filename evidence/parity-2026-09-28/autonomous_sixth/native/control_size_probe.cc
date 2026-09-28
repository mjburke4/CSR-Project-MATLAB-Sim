#include "ns3/core-module.h"
#include "ns3/csr-hop-security.h"
#include "ns3/csr-opnet-envelope.h"
#include "ns3/csr-phy-model.h"
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
using namespace ns3;

// Pure packet/model API probe. No simulator scheduling, device, channel,
// private-state access, source edit, or network execution.
void require(bool value,const char* why){if(!value){std::cerr<<"FAIL "<<why<<'\n';std::exit(1);}}
std::vector<uint8_t> bytes(Ptr<Packet> p){std::vector<uint8_t> b(p->GetSize());p->CopyData(b.data(),b.size());return b;}
std::vector<uint8_t> fromHex(const std::string& hex){
  require(hex.size()%2==0,"hex length");std::vector<uint8_t> b;
  for(size_t i=0;i<hex.size();i+=2)b.push_back(static_cast<uint8_t>(std::stoul(hex.substr(i,2),nullptr,16)));
  return b;
}
uint32_t check(const std::string& name,Ptr<Packet> packet,uint32_t expected){
  uint32_t compatibility=packet->GetSize();
  require(CsrAnnotateOpnetEnvelope(packet),"envelope annotation");
  const uint32_t modeled=CsrGetOpnetWireSize(packet);
  require(modeled==expected,name.c_str());
  auto copy=packet->Copy();require(CsrGetOpnetWireSize(copy)==expected,"tag survives retry-copy");
  std::cout<<name<<','<<compatibility<<','<<modeled<<','<<CsrGetOpnetWireSize(copy)<<"\n";
  return modeled;
}
Ptr<Packet> control(CsrHopSecurityState& state,bool pairwise,CsrHelloHeader h,const std::vector<uint8_t>& raw={}){
  auto p=raw.empty()?Create<Packet>():Create<Packet>(raw.data(),raw.size());p->AddHeader(h);
  std::vector<uint8_t> record;
  if(pairwise)record=state.ProtectPairwiseMessage(3,CsrPairwiseSecurityMode::Pairwise16,9,bytes(p)).record;
  else record=state.ProtectGroupMessage(CsrGroupSecurityMode::Group16,8,bytes(p)).record;
  auto result=Create<Packet>(record.data(),record.size());
  CsrHeader outer(1,3,7,7,true,false);outer.SetType(pairwise?CSR_PKT_NEIGHBOR_CHECK:CSR_PKT_ROUTING_CONTROL);
  outer.SetDestType(pairwise?CSR_DEST_UNICAST:CSR_DEST_MULTICAST);
  if(!pairwise)outer.SetDestinationSequences({{3,7}});
  outer.SetSecurityCount(state.GetOwnSecurityCount());outer.SetHasGroupSecurity(!pairwise);
  result->AddHeader(outer);return result;
}
int main(int argc,char**argv){
  require(argc==2,"captured_frames.tsv argument");
  std::cout<<"case,compatibility_packet_bytes,modeled_wire_bytes,retry_copy_wire_bytes\n";
  std::ifstream in(argv[1]);require(bool(in),"captured frame input");
  std::string line;std::vector<Ptr<Packet>> captured;
  while(std::getline(in,line)){
    std::istringstream parts(line);std::string name,hex;uint32_t expected;parts>>name>>expected>>hex;
    auto b=fromHex(hex);auto p=Create<Packet>(b.data(),b.size());check(name,p,expected);captured.push_back(p);
  }
  require(captured.size()==3,"three original captured children");
  require(CsrGetOpnetAggregateWireSize(captured)==63,"original captured aggregate63");

  CsrHopSecurityState state;state.SetNodeId(1);
  CsrHelloHeader h;h.SetNodeId(1);h.SetRoutingSequence(6);
  h.SetArlRouteMsgType(CsrArlRouteMsgType::RoutingUpdate);h.SetRoutingOperation(CsrRoutingOperation::Request);
  check("generated_compact_request",control(state,false,h),16);
  // Same logical request expressed as an actual ARL section is seven real
  // payload bytes and must remain23; it is NOT BuildRoutingRequestPayload.
  const std::vector<uint8_t> request={0,0,0,6,0,1,3};
  h.SetRoutingOperation(CsrRoutingOperation::Update);
  check("actual_request_section",control(state,false,h,request),23);
  auto compound=request;compound.push_back(0);
  check("actual_compound_section",control(state,false,h,compound),24);
  h.SetRoutingOperation(CsrRoutingOperation::Delete);h.SetRoutingTarget(99);
  check("compatibility_delete_marker",control(state,false,h),16);
  h.SetRoutingOperation(CsrRoutingOperation::Update);
  const std::vector<uint8_t> deletion={0,0,0,6,0,1,1,0,0,99};
  check("actual_delete_section",control(state,false,h,deletion),26);

  h.SetArlRouteMsgType(CsrArlRouteMsgType::NeighborCheck);
  h.SetNeighborCheckType(CsrNeighborCheckType::NoPath);h.SetNeighborCheckTarget(99);
  check("neighbor_no_path_target_metadata",control(state,true,h),16);
  check("neighbor_no_path_actual_three_raw_bytes",control(state,true,h,{0,0,99}),19);
  h.SetNeighborCheckType(CsrNeighborCheckType::Discovery);check("neighbor_discovery_metadata",control(state,true,h),16);
  h.SetNeighborCheckType(CsrNeighborCheckType::Overheard);check("neighbor_overheard_metadata",control(state,true,h),16);
  const double rate=CsrRateKeyToBps(8);
  auto duration=[&](uint32_t wire){return (104+48)/4.0*0.00051+(wire*8+32)/rate;};
  require(std::abs(duration(63)-0.08772)<1e-14,"native capture airtime87.72ms");
  require(std::abs(duration(77)-0.102)<1e-14,"MATLAB counterfactual airtime102ms");
  std::cout<<std::setprecision(17)<<"AIRTIME,native63,"<<duration(63)<<"\nAIRTIME,matlab77,"<<duration(77)
           <<"\nAIRTIME,delta,"<<duration(77)-duration(63)<<"\nALL_PACKET_CASES_PASS\n";
}
