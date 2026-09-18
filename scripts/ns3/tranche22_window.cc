// Controlled HOP callback contract. Actual pinned production methods; no RF claim.
#include "ns3/core-module.h"
#include "ns3/map-scheduler.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
using namespace ns3;

// The copied CSR header adds only friendship for this bounded fixture.
struct CsrTranche22Access {
  static unsigned Acks(const CsrHopLayer& h, CsrNodeId p) {
    auto i=h.m_flowCtrlByDest.find(p);return i==h.m_flowCtrlByDest.end()?0:i->second.consecutiveCleanAcks;
  }
  static unsigned Dacks(const CsrHopLayer& h) {return h.m_dackList.size();}
  static unsigned LiveRetrySum(const CsrHopLayer& h) {unsigned n=0;for(auto&e:h.m_resendQueue)n+=e.resendCount;return n;}
  static int Retry(const CsrHopLayer& h,CsrNodeId peer,uint16_t seq) {for(auto&e:h.m_resendQueue)if(e.dest==peer&&e.seq==seq)return e.resendCount;return -1;}
  static Ptr<Packet> Protect(CsrHopLayer& h,CsrHeader x) {return h.ProtectAckFrame(x);}
};

// Uses the engine's unchanged MapScheduler implementation. Exposes only the
// next timestamp so Advance drains ALL callbacks at the requested row time.
class T22Scheduler:public MapScheduler {
public:
 static T22Scheduler* active;
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::T22Scheduler").SetParent<MapScheduler>().AddConstructor<T22Scheduler>();return t;}
 T22Scheduler(){active=this;}
};
T22Scheduler* T22Scheduler::active=nullptr;
namespace {
using Row=std::map<std::string,std::string>;
std::vector<std::string> Split(const std::string&s,char delim=',') {std::vector<std::string>v;std::string t;std::istringstream in(s);while(std::getline(in,t,delim))v.push_back(t);if(!s.empty()&&s.back()==delim)v.push_back("");return v;}
std::vector<Row> Read(const std::string&p){std::ifstream f(p);std::string l;std::getline(f,l);if(!l.empty()&&l.back()=='\r')l.pop_back();auto h=Split(l);if(std::set<std::string>(h.begin(),h.end()).size()!=h.size())throw std::runtime_error("duplicate CSV header");std::vector<Row>r;while(std::getline(f,l)){if(!l.empty()&&l.back()=='\r')l.pop_back();auto v=Split(l);if(v.size()!=h.size())throw std::runtime_error("CSV width");Row x;for(size_t i=0;i<h.size();i++)x[h[i]]=v[i];r.push_back(x);}return r;}
void StopDrained(){auto*s=T22Scheduler::active;if(!s->IsEmpty()&&s->PeekNext().key.m_ts==uint64_t(Simulator::Now().GetTimeStep()))Simulator::ScheduleNow(&StopDrained);else Simulator::Stop();}
void Advance(double when){auto t=Seconds(when);if(t<Simulator::Now())throw std::runtime_error("time reversed");Simulator::Schedule(t-Simulator::Now(),&StopDrained);Simulator::Run();if(Simulator::Now()!=t)throw std::runtime_error("advance mismatch");}
unsigned releases=0,wakes=0;
void Release(CsrNodeId src,CsrNodeId dst){if(src!=7||dst!=1)throw std::runtime_error("NSDP identity mismatch");releases++;}
void Wake(){wakes++;}
struct PacketInfo{CsrNodeId peer;uint16_t seq;unsigned tx=0;};
void Case(const std::string&name,const std::vector<Row>&rows,const std::filesystem::path&out){
 ObjectFactory sf;sf.SetTypeId(T22Scheduler::GetTypeId());Simulator::SetScheduler(sf);
 RngSeedManager::SetSeed(130);RngSeedManager::SetRun(1);releases=wakes=0;
 auto dev=CreateObject<CsrNetDevice>(7);auto h=CreateObject<CsrHopLayer>();h->SetNodeId(7);h->SetMac(&dev->GetMac());h->SetNsdpDecrementCallback(MakeCallback(&Release));h->SetNwkQueueWakeCallback(MakeCallback(&Wake));
 dev->GetMac().SetReceiveState(CsrMacCore::State::TRACK);
 std::map<unsigned,Ptr<CsrHopLayer>> peers;std::map<unsigned,uint16_t>last;std::map<std::string,PacketInfo>pk;
 std::filesystem::create_directories(out/name);OpenDifferentialTraceCsv((out/name/"trace.csv").string());SetDifferentialAdmissionTraceEnabled(true);
 std::ofstream f(out/name/"states.csv");f<<"case_id,step,time_s,action,packet,peer,accepted,threshold,ack_count,outstanding,global_pending,dack_holds,resend,can_send,nsdp_release_total,live_retry_sum,tx_total\n";
 unsigned tx=0;uint64_t identity=0;
 for(auto&r:rows){unsigned peer=std::stoul(r.at("peer"));double when=std::stod(r.at("time_s"));Advance(when);auto a=r.at("action");int accepted=-1;
  if(a=="SEND"){
   accepted=h->CanSendToHop(peer)?1:0;
   if(accepted){if(pk.count(r.at("packet")))throw std::runtime_error("duplicate packet alias");auto p=Create<Packet>(16);p->AddPacketTag(CsrDifferentialAppTag(++identity));p->AddHeader(CsrNetHeader(7,1,0));h->SendData(peer,0,p,true);pk[r.at("packet")]={peer,++last[peer],0};}
  }else if(a=="TX"){
   auto&i=pk.at(r.at("packet"));if(i.peer!=peer)throw std::runtime_error("TX peer mismatch");int count=CsrTranche22Access::Retry(*h,peer,i.seq);if(count<0||unsigned(count)!=i.tx)throw std::runtime_error("TX without one current queued attempt");auto removed=dev->GetMac().CancelAcknowledgedFrames(peer,i.seq,1,0);if(removed!=1)throw std::runtime_error("TX queued copy missing or duplicated");h->NotifyMacFrameSent(peer,i.seq,Simulator::Now());i.tx++;tx++;
  }else if(a=="FEEDBACK"){
   auto aa=Split(r.at("ack_packets"),';'),dd=Split(r.at("dack_packets"),';');uint16_t top=0;for(auto&v:aa)if(!v.empty()){auto&i=pk.at(v);if(i.peer!=peer)throw std::runtime_error("ACK peer mismatch");top=std::max(top,i.seq);}for(auto&v:dd)if(!v.empty()){auto&i=pk.at(v);if(i.peer!=peer)throw std::runtime_error("DACK peer mismatch");top=std::max(top,i.seq);}if(!top)throw std::runtime_error("empty feedback");uint64_t ab=0,db=0;for(auto&v:aa)if(!v.empty()){auto n=top-pk.at(v).seq;if(n>=64)throw std::runtime_error("ACK window overflow");ab|=uint64_t(1)<<n;}for(auto&v:dd)if(!v.empty()){auto n=top-pk.at(v).seq;if(n>=64)throw std::runtime_error("DACK window overflow");db|=uint64_t(1)<<n;}
   if(!peers.count(peer)){peers[peer]=CreateObject<CsrHopLayer>();peers[peer]->SetNodeId(peer);}
   CsrHeader hdr(peer,7,top,7,false,true);hdr.SetType(CSR_PKT_ACK);hdr.SetDestType(CSR_DEST_UNICAST);hdr.SetHasAckWindow(true);hdr.SetAckBitmap(ab);hdr.SetDackBitmap(db);h->ReceiveFromMac(CsrTranche22Access::Protect(*peers[peer],hdr),70,20);
  }else if(a!="PROBE")throw std::runtime_error("unsupported action");
  auto s=h->GetDataAdmissionSnapshot(peer);f<<name<<','<<r.at("step")<<','<<std::setprecision(17)<<Simulator::Now().GetSeconds()<<','<<a<<','<<r.at("packet")<<','<<peer<<','<<accepted<<','<<s.neighborThreshold<<','<<CsrTranche22Access::Acks(*h,peer)<<','<<s.neighborOutstanding<<','<<s.pendingData<<','<<CsrTranche22Access::Dacks(*h)<<','<<h->GetResendQueueSize()<<','<<(s.globalAllowed&&s.neighborAllowed)<<','<<releases<<','<<CsrTranche22Access::LiveRetrySum(*h)<<','<<tx<<'\n';
  CsrDifferentialTraceEvent mark;mark.event="t22_checkpoint";mark.node="7";mark.sequence=r.at("step");WriteDifferentialTrace(mark);
 }
 if(dev->GetMac().GetTransmittedFrameCount()!=0)throw std::runtime_error("uncontrolled MAC transmission");CloseDifferentialTraceCsv();Simulator::Destroy();
}
}
int main(int argc,char**argv){try{if(argc!=3)throw std::runtime_error("Usage: tranche22 actions.csv raw-output");auto rows=Read(argv[1]);std::vector<std::string>order;std::map<std::string,std::vector<Row>>cases;for(auto&r:rows){auto n=r.at("case_id");if(!cases.count(n))order.push_back(n);cases[n].push_back(r);}for(auto&n:order)Case(n,cases[n],argv[2]);std::cout<<"T22_NATIVE cases="<<order.size()<<" rows="<<rows.size()<<"\n";return 0;}catch(const std::exception&e){std::cerr<<"T22_NATIVE_ERROR "<<e.what()<<'\n';return 2;}}
