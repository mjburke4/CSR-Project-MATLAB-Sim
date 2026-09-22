// Compile pristine pinned CSR headers with -fno-access-control for read-only
// snapshots and explicit fixture inputs. No production header is altered.
#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include "ns3/csr-nwk-layer.h"
#include <fstream>
#include <iomanip>
#include <functional>
#include <sstream>
#include <string>
#include <vector>
#include <set>
using namespace ns3;

std::string Quote(const std::string& s) { std::ostringstream o; o<<'"'; for(char c:s){if(c=='"'||c=='\\')o<<'\\'<<c; else if(c=='\n')o<<"\\n";else if(c=='\r')o<<"\\r";else if(c=='\t')o<<"\\t";else o<<c;}o<<'"';return o.str(); }
template<class T> std::string Array(const T& a) {std::ostringstream o;o<<'[';bool first=true;for(auto x:a){if(!first)o<<',';first=false;o<<x;}o<<']';return o.str();}
struct LineObserver:std::streambuf {
 std::ostream& log;std::string pending;std::function<void(const std::string&)> observe;
 explicit LineObserver(std::ostream& stream):log(stream){}
 int overflow(int c) override {if(c==traits_type::eof())return traits_type::not_eof(c);char ch=static_cast<char>(c);log.put(ch);if(ch=='\n'){auto line=pending;pending.clear();if(observe)observe(line);}else pending+=ch;return c;}
 int sync() override{log.flush();return 0;}
};
struct Fixture {
 std::string id;Ptr<CsrNetLayer> nwk;Ptr<CsrHopLayer> hop;CsrMacCore mac;
 std::vector<std::string> states,controls,preSend;
 CsrNodeId lastStart=CSR_BROADCAST_ID;uint32_t lastWatchUid=0,generation=0;std::set<uint64_t> controlPacketUids;
 bool observerEnabled=true;unsigned maximumQueue=0;
 Fixture(std::string name,bool observe):id(name),observerEnabled(observe){
  mac.SetNodeId(1); // No device attached: native MAC queues, never schedules PHY.
  hop=CreateObject<CsrHopLayer>();hop->SetNodeId(1);hop->SetMac(&mac);
  nwk=CreateObject<CsrNetLayer>();nwk->SetNodeId(1);nwk->SetNodeType(CsrNodeType::Gateway);
  nwk->SetArlNeighborAdmissionEnabled(false);nwk->SetAutomaticRoutePropagationEnabled(false);nwk->SetHop(hop);
 }
 void Snapshot(const std::string& event){
  auto& report=nwk->m_snmpReportEvent;bool active=report.IsPending();uint32_t uid=report.GetUid();if(active&&uid!=lastWatchUid){lastWatchUid=uid;generation++;}
  CsrNodeId gateway=CSR_BROADCAST_ID;bool hasGateway=nwk->FindApplicationGateway(gateway);
  std::ostringstream o;o<<std::setprecision(17)<<"{\"time_s\":"<<Simulator::Now().GetSeconds()<<",\"event\":"<<Quote(event)
    <<",\"local_discovery_active\":"<<(nwk->IsDiscoveryActive()?"true":"false")<<",\"local_discovery_state\":"<<unsigned(nwk->m_discState)
    <<",\"logical_destinations\":"<<Array(nwk->m_destinationCreationOrder)<<",\"reachable_destinations\":"<<Array(nwk->GetKnownDiscoveryNodes())<<",\"worklist\":[";
  bool first=true;for(auto entry:nwk->m_discoveryTable){if(!first)o<<',';first=false;o<<"{\"node\":"<<entry.nodeId<<",\"requested\":"<<(!entry.discoveryNeeded?"true":"false")<<'}';}
  o<<"],\"pending_target\":"<<(active&&lastStart!=CSR_BROADCAST_ID?std::to_string(lastStart):"null")
   <<",\"watchdog_active\":"<<(active?"true":"false")<<",\"watchdog_deadline_s\":";
  if(active)o<<TimeStep(report.GetTs()).GetSeconds();else o<<"null";
  o<<",\"watchdog_generation\":"<<generation<<",\"watchdog_event_uid\":"<<uid
   <<",\"topology_known\":"<<(nwk->HasApplicationTopologyKnowledge()?"true":"false")
   <<",\"gateway_available\":"<<(hasGateway?"true":"false")<<",\"local_is_gateway\":true,\"starts_sent\":"<<nwk->GetSnmpStartSentCount()<<",\"done_received\":"<<nwk->GetSnmpDoneReceivedCount()<<'}';
  states.push_back(o.str());
 }
 void ScanControls(){
  maximumQueue=std::max(maximumQueue,static_cast<unsigned>(mac.m_queue.size()));
  for(const auto& e:mac.m_queue){auto p=e.frame->Copy();CsrHeader h;if(!p->RemoveHeader(h)||h.GetType()!=CSR_PKT_SNMP)continue;
   if(!controlPacketUids.insert(e.frame->GetUid()).second)continue;CsrSnmpHeader s;NS_ABORT_MSG_IF(!p->RemoveHeader(s),"Bad SNMP payload");
   bool requested=false;for(auto entry:nwk->m_discoveryTable)if(entry.nodeId==s.GetDestination())requested=!entry.discoveryNeeded;
   if(s.GetCommand()==CSR_SNMP_START_DISCOVERY)lastStart=s.GetDestination();
   std::ostringstream o;o<<std::setprecision(17)<<"{\"time_s\":"<<e.enqueuedAt.GetSeconds()<<",\"command\":"<<Quote(s.GetCommand()==CSR_SNMP_START_DISCOVERY?"START":"DONE")
    <<",\"command_code\":"<<unsigned(s.GetCommand())<<",\"source\":"<<s.GetSource()<<",\"final_destination\":"<<s.GetDestination()
    <<",\"next_hop\":"<<h.GetDst()<<",\"destination_type\":"<<unsigned(s.GetDestinationType())<<",\"sequence\":"<<h.GetSeq()<<",\"dscp\":"<<unsigned(h.GetDscp())
    <<",\"ackable\":"<<(h.IsAckable()?"true":"false")<<",\"send_result\":true,\"requested_at_capture\":"<<(requested?"true":"false")<<",\"advertised_nodes\":"<<Array(s.GetNodes())<<'}';controls.push_back(o.str());
  }
 }
 void Observe(const std::string& line){if(!observerEnabled)return;
  if(line.find("[NWK 1] TX legacy SNMP")!=std::string::npos){auto pos=line.find("finalDestination=");auto target=std::stoul(line.substr(pos+17));bool mark=false;for(auto e:nwk->m_discoveryTable)if(e.nodeId==target)mark=!e.discoveryNeeded;
   std::ostringstream o;o<<std::setprecision(17)<<"{\"time_s\":"<<Simulator::Now().GetSeconds()<<",\"target\":"<<target<<",\"requested_before_send\":"<<(mark?"true":"false")<<'}';preSend.push_back(o.str());Snapshot("before_snmp_enqueue");
  }
  if(line.find("SNMP discovery handoff")!=std::string::npos){ScanControls();Snapshot("after_handoff");}
  if(line.find("SNMP discovery report watchdog expired")!=std::string::npos)Snapshot("watchdog_callback_enter");
  if(line.find("DiscoveryStop sequence=")!=std::string::npos)Snapshot("local_stop_callback");
 }
 void Peer(unsigned peer){CsrHelloHeader h;h.SetNodeId(peer);h.SetHelloSeq(1);h.SetNodeType(CsrNodeType::Routable);h.SetSpeedKey(8);h.SetRxPowerDbmX10(-1050);h.SetActiveNodes(1);h.SetArlRouteMsgType(CsrArlRouteMsgType::None);auto p=Create<Packet>();p->AddHeader(h);nwk->ProcessHello(p,peer,70,20);
  NS_ABORT_MSG_IF(!nwk->IsArlNeighborActive(peer),"Peer input did not create active neighbor");
  NS_ABORT_MSG_IF(!nwk->HasRelayRoute(peer),"Peer input did not create route");Snapshot("peer_"+std::to_string(peer));}
 void Done(unsigned source){Snapshot("before_done_"+std::to_string(source));CsrSnmpHeader h;h.SetSource(source);h.SetDestination(1);h.SetDestinationType(CSR_DEST_UNICAST);h.SetCommand(CSR_SNMP_DISCOVERY_DONE);h.SetValue(0);h.SetNodes({});auto p=Create<Packet>();p->AddHeader(h);nwk->ReceiveSnmpFromHop(p,source);ScanControls();Snapshot("after_done_"+std::to_string(source));}
 void Checkpoint(const std::string& s){ScanControls();Snapshot(s);}
 std::string Dump(){std::ostringstream o;o<<"{\"schema\":\"csr-tranche27-native-controller-case-v1\",\"case_id\":"<<Quote(id)<<",\"engine\":\"ns3\",\"observer_enabled\":"<<(observerEnabled?"true":"false")<<",\"states\":[";bool f=true;for(auto x:states){if(!f)o<<',';f=false;o<<x;}o<<"],\"controls\":[";f=true;for(auto x:controls){if(!f)o<<',';f=false;o<<x;}o<<"],\"pre_send\":[";f=true;for(auto x:preSend){if(!f)o<<',';f=false;o<<x;}o<<"],\"maximum_mac_queue\":"<<maximumQueue<<",\"mac_data_queue_drops\":"<<mac.m_dataQueueDropCount<<",\"phy_executed\":false,\"production_source_modified\":false}";return o.str();}
};
struct CaseConfig {std::string id;std::vector<unsigned> peers;unsigned doneSource,latePeer;double doneTime,lateTime,duration,stop;std::vector<double> checkpoints;};
#include "tranche27-plan.generated.h"
int main(int argc,char**argv){if(argc!=3){std::cerr<<"usage: fixture OUTDIR observer(0|1)\n";return 2;}Time::SetResolution(Time::NS);bool observe=std::string(argv[2])=="1";
 std::ofstream raw(std::string(argv[1])+"/native.log");LineObserver buffer(raw);auto old=std::cout.rdbuf(&buffer);
 for(const auto& c:kCases){
  Fixture f(c.id,observe);buffer.observe=[&f](const std::string& s){f.Observe(s);};f.Snapshot("initial");for(auto peer:c.peers)f.Peer(peer);
  f.nwk->StartDiscovery(Seconds(0),Seconds(c.duration));f.Snapshot("local_discovery_scheduled");
  if(c.doneSource)Simulator::Schedule(Seconds(c.doneTime),[&f,&c]{f.Done(c.doneSource);});
  if(c.latePeer)Simulator::Schedule(Seconds(c.lateTime),[&f,&c]{f.Peer(c.latePeer);});
  for(double t:c.checkpoints)Simulator::Schedule(Seconds(t),[&f]{f.Checkpoint("checkpoint");});
  Simulator::Schedule(Seconds(c.stop),[&f]{f.Checkpoint("stop");Simulator::Stop();});Simulator::Run();
  std::ofstream result(std::string(argv[1])+"/"+c.id+".json");result<<f.Dump()<<'\n';buffer.observe=nullptr;Simulator::Destroy();
 }
 std::cout.rdbuf(old);std::cout<<"Executed five native controller fixtures\n";return 0;}
