#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
int csrRuleDraw = -1;
int CsrRuleDraw(int low, int high) {
  NS_ABORT_MSG_IF(csrRuleDraw < low || csrRuleDraw > high, "Rule vector draw outside requested production support");
  return csrRuleDraw;
}
struct CsrMacSlotParitySmokeAccess {
 static void Setup(CsrMacCore& mac, uint32_t local, uint32_t reported, const std::string& text) {
  mac.m_activeNodesForPostTx=local;
  mac.m_maxReportedActiveNodes=reported;
  std::stringstream in(text);std::string part;uint32_t node=100;
  while(std::getline(in,part,';')){
   if(part.empty())continue;
   CsrMacCore::NeighborInfo n;n.rtCounter=std::stoi(part);
   mac.m_neighbors[++node]=n;
  }
 }
 static int Pick(CsrMacCore& mac){return mac.PickTxSlot(2);}
};
int main(int argc,char**argv){
 NS_ABORT_MSG_IF(argc!=7,"Usage: native-vectors KIND LOCAL REPORTED REDUCTION DRAW COUNTERS");
 CsrMacCore mac;mac.SetNodeId(8);
 mac.SetSlotSelectionProfile(CsrMacCore::SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE);
 CsrMacSlotParitySmokeAccess::Setup(mac,std::stoul(argv[2]),std::stoul(argv[3]),argv[6]);
 mac.SetSupervisorSlotReduction(std::stoi(argv[4]));
 auto active=mac.GetActiveNodesForSlotting();auto range=mac.GetOpnetSlotRange(active);
 if(std::string(argv[1])=="range"){
  std::cout<<"RULE_RESULT,"<<active<<","<<range<<",\n";
 }else{
  csrRuleDraw=std::stoi(argv[5]);
  int slot=CsrMacSlotParitySmokeAccess::Pick(mac);
  std::cout<<"RULE_RESULT,"<<active<<","<<range<<","<<slot<<"\n";
 }
 Simulator::Destroy();
}
