// Public MAC API only. Exact TX membership is verified from native tx_start traces.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <sstream>
#include <stdexcept>
using namespace ns3;
namespace fs=std::filesystem;
Ptr<Packet> Frame(bool ack,unsigned bytes,int rate){
 CsrHeader h(2,ack?8:1,ack?13:1,0,!ack,ack);
 h.SetType(ack?CSR_PKT_ACK:CSR_PKT_DATA);h.SetDestType(CSR_DEST_UNICAST);
 h.SetLinkControl(rate,33,-100);
 if(ack){h.SetHasAckWindow(true);h.SetAckBitmap(1);h.SetDackBitmap(0);}
 auto p=Create<Packet>(ack?0:bytes);
 if(!ack)p->AddHeader(CsrNetHeader(2,1,0));p->AddHeader(h);
 CsrSetOpnetEnvelope(p,ack?CsrOpnetPacketFormat::Ack:CsrOpnetPacketFormat::Hop,ack?41:bytes+32);
 return p;
}
int main(int argc,char**argv){
 if(argc!=3)return 2;
 try{
 std::ifstream cases(argv[1]);if(!cases)throw std::runtime_error("No cases.csv");
 fs::path outdir(argv[2]);fs::create_directories(outdir);
 std::ofstream out(outdir/"sampled.csv"),inputs(outdir/"inputs.csv");
 out<<"case_id,ordinal,sample_time_s,ack_segments,data_segments,data_queue_after,ack_queue_after,wire_bytes,rate_kbps,reservation_after\n";
 inputs<<"case_id,input,time_s,after_ordinal\n";
 out<<std::setprecision(17);inputs<<std::setprecision(17);
 std::string line;std::getline(cases,line);
 while(std::getline(cases,line)){
  if(line.empty())continue;std::stringstream s(line);std::vector<std::string> v;std::string x;
  while(std::getline(s,x,','))v.push_back(x);
  if(v.size()!=9)throw std::runtime_error("Malformed case row");
  std::string name=v[0];unsigned bytes=std::stoul(v[1]);int rate=std::stoi(v[2]);
  double arrival=std::stod(v[3]),freezeStart=std::stod(v[5]),freezeEnd=std::stod(v[6]);
  unsigned refreshAt=std::stoul(v[4]);
  RngSeedManager::SetSeed(132);RngSeedManager::SetRun(1);
  OpenDifferentialTraceCsv((outdir/(name+"-trace.csv")).string());
  auto device=CreateObject<CsrNetDevice>(2);auto& mac=device->GetMac();
  mac.SetReservationSlotOverrideForDifferentialRun(1);mac.SetActiveNodesForPostTx(3);
  bool ackAdmitted=false,refreshed=false;unsigned copies=0,totalAck=0,previousData=1;uint64_t previousTx=0;
  std::function<void()> observe,admit;
  auto input=[&](const char* kind){inputs<<name<<','<<kind<<','<<Simulator::Now().GetSeconds()<<','<<previousTx<<'\n';};
  admit=[&](){observe();mac.EnqueueTxFrame(Frame(true,0,rate),8,0,false);ackAdmitted=true;copies=0;input("ack");};
  observe=[&](){
   auto tx=mac.GetTransmittedFrameCount();if(tx==previousTx)return;
   if(tx!=previousTx+1)throw std::runtime_error("Sampling missed TX");
   unsigned dq=mac.GetDataQueuedFrameCount(),aq=mac.GetAckQueuedFrameCount();
   if(dq>previousData)throw std::runtime_error("Unexpected DATA candidate");
   unsigned data=previousData-dq,ack=ackAdmitted&&copies<5;
   copies+=ack;totalAck+=ack;
   if(aq!=(ackAdmitted&&copies<5?1u:0u))throw std::runtime_error("ACK lifetime inference invalid");
   out<<name<<','<<tx<<','<<Simulator::Now().GetSeconds()<<','<<ack<<','<<data<<','<<dq<<','<<aq<<','<<(ack*41+data*(bytes+32))<<','<<mac.GetLastTxRateKbps()<<','<<mac.GetLocalReservationCounter()<<'\n';
   previousData=dq;previousTx=tx;
   if(refreshAt&&!refreshed&&totalAck==refreshAt){refreshed=true;Simulator::Schedule(MilliSeconds(1),admit);}
  };
  mac.EnqueueTxFrame(Frame(false,bytes,rate),1,0,true);input("data");
  if(arrival>=0)Simulator::Schedule(Seconds(arrival),admit);
  if(freezeStart>=0){
   Simulator::Schedule(Seconds(freezeStart),[&](){observe();mac.SetReceiveState(CsrMacCore::State::TRACK);input("track");});
   Simulator::Schedule(Seconds(freezeEnd),[&](){observe();mac.SetReceiveState(CsrMacCore::State::SEARCH);input("search");});
  }
  // 0.1 ms observer, far below the minimum frame airtime. No behavior mutation.
  for(unsigned i=1;i<=200000;i++)Simulator::Schedule(MicroSeconds(100*i),observe);
  Simulator::Stop(Seconds(20.00001));Simulator::Run();observe();
  if(mac.GetQueuedFrameCount()!=0)throw std::runtime_error("Queues did not drain");
  CloseDifferentialTraceCsv();Simulator::Destroy();
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
 return 0;
}
