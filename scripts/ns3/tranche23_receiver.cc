// Controlled post-security receiver DATA / actual NWK ownership contract.
// Copied headers add friendship only. No production source or RF changes.
#include "ns3/core-module.h"
#include "ns3/map-scheduler.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-hop-layer.h"
#include "ns3/csr-nwk-layer.h"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
using namespace ns3;

struct CsrTranche23Access {
  static bool Ingress(CsrHopLayer& h, const CsrHeader& header, Ptr<Packet> payload) {
    bool first=h.CheckReceivedSeq(header.GetSrc(),header.GetSeq(),true);
    h.HandleDataFrame(header,payload,first);return first;
  }
  static Ptr<Packet> Protect(CsrHopLayer& h,CsrHeader header) {return h.ProtectAckFrame(header);}
  static unsigned Holds(const CsrHopLayer& h){return h.m_dackList.size();}
  static int Highest(const CsrHopLayer& h){auto p=h.m_rxDataStateBySrc.find(7);return p==h.m_rxDataStateBySrc.end()?-1:p->second.highest;}
  static uint64_t Ack(const CsrHopLayer& h){auto p=h.m_rxDataStateBySrc.find(7);return p==h.m_rxDataStateBySrc.end()?0:p->second.ackBitmap;}
  static uint64_t Dack(const CsrHopLayer& h){auto p=h.m_rxDataStateBySrc.find(7);return p==h.m_rxDataStateBySrc.end()?0:p->second.dackBitmap;}
  static bool TxConfirmed(const CsrHopLayer& h,uint16_t seq){for(auto&e:h.m_resendQueue)if(e.dest==2&&e.seq==seq)return e.initialTxConfirmed;throw std::runtime_error("missing TX owner");}
  static CsrHeader Feedback(const CsrMacCore& m){unsigned n=0;CsrHeader h;for(auto&e:m.m_ackQueue)if(e.dest==7){e.frame->PeekHeader(h);n++;}if(n!=1)throw std::runtime_error("receiver feedback queue is not singular");return h;}
};
class T23Scheduler:public MapScheduler {
public:static T23Scheduler* active;static TypeId GetTypeId(){static TypeId t=TypeId("ns3::T23Scheduler").SetParent<MapScheduler>().AddConstructor<T23Scheduler>();return t;}T23Scheduler(){active=this;}
};
T23Scheduler* T23Scheduler::active=nullptr;
namespace {
using Row=std::map<std::string,std::string>;
std::vector<std::string> Split(const std::string&s,char delim=','){std::vector<std::string>v;std::string t;std::istringstream in(s);while(std::getline(in,t,delim))v.push_back(t);if(!s.empty()&&s.back()==delim)v.push_back("");return v;}
std::vector<Row> Read(const std::string&p){std::ifstream f(p);if(!f)throw std::runtime_error("cannot open actions");std::string l;std::getline(f,l);if(!l.empty()&&l.back()=='\r')l.pop_back();auto h=Split(l);if(std::set<std::string>(h.begin(),h.end()).size()!=h.size())throw std::runtime_error("duplicate CSV header");std::vector<Row>r;while(std::getline(f,l)){if(!l.empty()&&l.back()=='\r')l.pop_back();auto v=Split(l);if(v.size()!=h.size())throw std::runtime_error("CSV width");Row x;for(size_t i=0;i<h.size();i++)x[h[i]]=v[i];r.push_back(x);}return r;}
std::string Hex(uint64_t n){std::ostringstream s;s<<std::uppercase<<std::hex<<std::setw(16)<<std::setfill('0')<<n;return s.str();}
void StopDrained(){auto*s=T23Scheduler::active;if(!s->IsEmpty()&&s->PeekNext().key.m_ts==uint64_t(Simulator::Now().GetTimeStep()))Simulator::ScheduleNow(&StopDrained);else Simulator::Stop();}
void Advance(double when){auto t=Seconds(when);if(t<Simulator::Now())throw std::runtime_error("time reversed");Simulator::Schedule(t-Simulator::Now(),&StopDrained);Simulator::Run();if(Simulator::Now()!=t)throw std::runtime_error("advance mismatch");}
struct Counters {
  Ptr<CsrNetLayer> nwk;unsigned rxDelivered=0,nsdpReleases=0,nwkEnqueues=0;
  void Deliver(Ptr<Packet> p,CsrNodeId peer){CsrNetHeader h;p->PeekHeader(h);auto before=nwk->GetNsdpCount(h.GetSrc(),h.GetDst());rxDelivered++;nwk->ReceiveFromHop(p,peer);auto after=nwk->GetNsdpCount(h.GetSrc(),h.GetDst());if(after<before)throw std::runtime_error("ingress unexpectedly released custody");nwkEnqueues+=after-before;}
  void Release(CsrNodeId src,CsrNodeId dst){auto before=nwk->GetNsdpCount(src,dst);nwk->DecrementNsdp(src,dst);auto after=nwk->GetNsdpCount(src,dst);if(after>before)throw std::runtime_error("completion unexpectedly created custody");nsdpReleases+=before-after;}
};
void Case(const std::string&name,const std::vector<Row>&rows,const std::filesystem::path&out,bool observe){
 ObjectFactory sf;sf.SetTypeId(T23Scheduler::GetTypeId());Simulator::SetScheduler(sf);RngSeedManager::SetSeed(130);RngSeedManager::SetRun(1);
 auto dev=CreateObject<CsrNetDevice>(8);auto h=CreateObject<CsrHopLayer>();auto nwk=CreateObject<CsrNetLayer>();auto peer=CreateObject<CsrHopLayer>();peer->SetNodeId(2);
 h->SetNodeId(8);h->SetMac(&dev->GetMac());nwk->SetNodeId(8);nwk->SetArlNeighborAdmissionEnabled(false);nwk->SetAutomaticRoutePropagationEnabled(false);nwk->SetHop(h);nwk->AddStaticRoute(1,2);dev->GetMac().SetReceiveState(CsrMacCore::State::TRACK);
 Counters c;c.nwk=nwk;h->SetRxFromHopCallback(MakeCallback(&Counters::Deliver,&c));h->SetNsdpDecrementCallback(MakeCallback(&Counters::Release,&c));
 std::filesystem::create_directories(out/name);if(observe){OpenDifferentialTraceCsv((out/name/"trace.csv").string());SetDifferentialAdmissionTraceEnabled(true);}else SetDifferentialAdmissionTraceEnabled(false);
 std::ofstream state(out/name/"states.csv"),feedback(out/name/"feedback.csv");
 // Exact header follows the frozen root contract.
 state<<"case_id,step,time_s,action,packet,accepted,nsdp_relay,nsdp_local,nwk_waiting,nwk_owned,hop_pending,hop_outstanding,hop_resend,hop_holds,rx_highest,rx_ack_hex,rx_dack_hex,ack_generated,dack_generated,rx_received,rx_delivered,rx_duplicates,nsdp_releases,ack_completed,dack_completed,dack_expired,data_tx\n";
 feedback<<"case_id,step,time_s,kind,sequence,ack_hex,dack_hex,relay_nsdp,local_nsdp,nwk_owned\n";
 std::map<std::string,uint64_t> identities;std::set<uint16_t> sent;std::set<uint16_t>completed;
 unsigned received=0,duplicates=0,acks=0,dacks=0,ackCompleted=0,dackCompleted=0,expired=0,tx=0;uint64_t nextIdentity=0;
 for(auto&r:rows){auto holdsBefore=CsrTranche23Access::Holds(*h);Advance(std::stod(r.at("time_s")));auto holdsAfter=CsrTranche23Access::Holds(*h);if(holdsBefore<holdsAfter)throw std::runtime_error("unexpected natural DACK creation");expired+=holdsBefore-holdsAfter;
  auto a=r.at("action"),alias=r.at("packet");int accepted=-1;
  if(a=="RX"||a=="LOCAL"){
   if(!identities.count(alias))identities[alias]=++nextIdentity;
   auto p=Create<Packet>(16);p->AddPacketTag(CsrDifferentialAppTag(identities.at(alias)));auto src=std::stoul(r.at("nwk_source")),dst=std::stoul(r.at("destination"));
   if(a=="LOCAL"){
    if(src!=8||dst!=1)throw std::runtime_error("invalid local flow");accepted=nwk->CanAdmitApplicationPacket(dst)?1:0;if(accepted){nwk->Send(dst,0,p,true);c.nwkEnqueues++;}
   }else{
    p->AddHeader(CsrNetHeader(src,dst,0));CsrHeader hdr(7,8,std::stoul(r.at("sequence")),0,true,false);hdr.SetType(CSR_PKT_DATA);hdr.SetDestType(CSR_DEST_UNICAST);received++;bool first=CsrTranche23Access::Ingress(*h,hdr,p);duplicates+=!first;
    auto fb=CsrTranche23Access::Feedback(dev->GetMac());if(fb.IsDack())dacks++;else acks++;auto nr=nwk->GetNsdpCount(7,1),nl=nwk->GetNsdpCount(8,1);feedback<<name<<','<<r.at("step")<<','<<std::setprecision(17)<<Simulator::Now().GetSeconds()<<','<<(fb.IsDack()?"DACK":"ACK")<<','<<fb.GetSeq()<<','<<Hex(fb.GetAckBitmap())<<','<<Hex(fb.GetDackBitmap())<<','<<nr<<','<<nl<<','<<nr+nl<<'\n';
   }
  }else if(a=="TX"){
   auto seq=static_cast<uint16_t>(std::stoul(r.at("sequence")));if(CsrTranche23Access::TxConfirmed(*h,seq))throw std::runtime_error("repeated controlled initial TX");auto n=dev->GetMac().CancelAcknowledgedFrames(2,seq,1,0);if(n!=1)throw std::runtime_error("TX without exactly one queued copy");h->NotifyMacFrameSent(2,seq,Simulator::Now());sent.insert(seq);tx++;
  }else if(a=="FEEDBACK"){
   auto aa=Split(r.at("ack_packets"),';'),dd=Split(r.at("dack_packets"),';');uint16_t top=0;for(auto&v:aa)if(!v.empty())top=std::max(top,static_cast<uint16_t>(std::stoul(v)));for(auto&v:dd)if(!v.empty())top=std::max(top,static_cast<uint16_t>(std::stoul(v)));if(!top)throw std::runtime_error("empty feedback");for(auto&v:aa)if(!v.empty()&&!sent.count(std::stoul(v)))throw std::runtime_error("ACK target was not transmitted");for(auto&v:dd)if(!v.empty()&&!sent.count(std::stoul(v)))throw std::runtime_error("DACK target was not transmitted");uint64_t ab=0,db=0;for(auto&v:aa)if(!v.empty()){auto s=static_cast<uint16_t>(std::stoul(v));if(top-s>=64)throw std::runtime_error("ACK window overflow");ab|=uint64_t(1)<<(top-s);}for(auto&v:dd)if(!v.empty()){auto s=static_cast<uint16_t>(std::stoul(v));if(top-s>=64)throw std::runtime_error("DACK window overflow");db|=uint64_t(1)<<(top-s);}
   auto before=c.nsdpReleases;CsrHeader hdr(2,8,top,7,false,true);hdr.SetType(CSR_PKT_ACK);hdr.SetDestType(CSR_DEST_UNICAST);hdr.SetHasAckWindow(true);hdr.SetAckBitmap(ab);hdr.SetDackBitmap(db);h->ReceiveFromMac(CsrTranche23Access::Protect(*peer,hdr),70,20);
   unsigned tally=0;for(auto&v:aa)if(!v.empty()&&completed.insert(static_cast<uint16_t>(std::stoul(v))).second){ackCompleted++;tally++;}for(auto&v:dd)if(!v.empty()&&completed.insert(static_cast<uint16_t>(std::stoul(v))).second){dackCompleted++;tally++;}if(c.nsdpReleases-before!=tally)throw std::runtime_error("feedback completion ownership mismatch");
  }else if(a!="PROBE")throw std::runtime_error("unknown action");
  // Frozen one-microsecond settling interval drains callback tics explicitly.
  Advance(std::stod(r.at("observe_s")));
  auto nr=nwk->GetNsdpCount(7,1),nl=nwk->GetNsdpCount(8,1);auto s=h->GetDataAdmissionSnapshot(2);
  if(nr+nl!=nwk->GetNwkQueueSize()+h->GetResendQueueSize())throw std::runtime_error("NWK ownership conservation failed");
  state<<name<<','<<r.at("step")<<','<<std::setprecision(17)<<Simulator::Now().GetSeconds()<<','<<a<<','<<alias<<','<<accepted<<','<<nr<<','<<nl<<','<<nwk->GetNwkQueueSize()<<','<<nr+nl<<','<<s.pendingData<<','<<s.neighborOutstanding<<','<<h->GetResendQueueSize()<<','<<CsrTranche23Access::Holds(*h)<<','<<CsrTranche23Access::Highest(*h)<<','<<Hex(CsrTranche23Access::Ack(*h))<<','<<Hex(CsrTranche23Access::Dack(*h))<<','<<acks<<','<<dacks<<','<<received<<','<<c.rxDelivered<<','<<duplicates<<','<<c.nsdpReleases<<','<<ackCompleted<<','<<dackCompleted<<','<<expired<<','<<tx<<'\n';
  if(observe){CsrDifferentialTraceEvent mark;mark.event="t23_checkpoint";mark.node="8";mark.sequence=r.at("step");WriteDifferentialTrace(mark);}
 }
 if(dev->GetMac().GetTransmittedFrameCount()!=0)throw std::runtime_error("uncontrolled MAC/RF transmission");if(observe)CloseDifferentialTraceCsv();SetDifferentialAdmissionTraceEnabled(false);Simulator::Destroy();
}
}
int main(int argc,char**argv){try{if(argc!=4)throw std::runtime_error("Usage: tranche23 actions.csv raw-output trace_on|trace_off");bool observe=std::string(argv[3])=="trace_on";if(!observe&&std::string(argv[3])!="trace_off")throw std::runtime_error("bad observer mode");auto rows=Read(argv[1]);std::vector<std::string>order;std::map<std::string,std::vector<Row>>cases;for(auto&r:rows){auto n=r.at("case_id");if(!cases.count(n))order.push_back(n);cases[n].push_back(r);}for(auto&n:order)Case(n,cases[n],argv[2],observe);std::cout<<"T23_NATIVE cases="<<order.size()<<" rows="<<rows.size()<<" uncontrolled_mac_tx=0 observer="<<observe<<'\n';return 0;}catch(const std::exception&e){std::cerr<<"T23_NATIVE_ERROR "<<e.what()<<'\n';return 2;}}
