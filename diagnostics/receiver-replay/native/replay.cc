#include "ns3/core-module.h"
#include "ns3/csr-net-device.h"
#include <filesystem>
#include <sstream>
#include <map>
using Row=std::map<std::string,std::string>;
std::vector<std::string> Split(const std::string&s){std::vector<std::string> v;std::stringstream ss(s);std::string x;while(std::getline(ss,x,','))v.push_back(x);if(!s.empty()&&s.back()==',')v.push_back("");return v;}
std::vector<Row> Read(const std::string& path){std::ifstream f(path);NS_ABORT_MSG_IF(!f,"Cannot read "<<path);std::string s;std::getline(f,s);if(!s.empty()&&s.back()=='\r')s.pop_back();auto h=Split(s);std::vector<Row> rows;while(std::getline(f,s)){if(!s.empty()&&s.back()=='\r')s.pop_back();auto v=Split(s);NS_ABORT_MSG_IF(v.size()!=h.size(),"CSV shape "<<path);Row r;for(size_t i=0;i<h.size();++i)r[h[i]]=v[i];rows.push_back(r);}return rows;}
uint64_t U(const Row&r,const char*k){return std::stoull(r.at(k));} double D(const Row&r,const char*k){return std::stod(r.at(k));}
struct CsrPhyFrontEndSmokeAccess {
 static void Cancel(Ptr<CsrNetDevice>d){d->CancelPostTxWait();}
 static void Receive(Ptr<CsrNetDevice> d,const Row&r,const std::vector<Ptr<Packet>>&frames){
  CsrNetDevice::RxSignal s;s.id=U(r,"signal_id");s.txId=U(r,"source");s.sequence=U(r,"sequence");s.frames=frames;s.rateKbps=U(r,"rate");s.txPowerDbm=D(r,"tx_dbm");s.preamble=U(r,"preamblebits")==7888?PREAMBLE_LONG:PREAMBLE_SHORT;s.reservedSlot=std::stoi(r.at("slot"));s.ackable=U(r,"ackable");s.payloadBytes=U(r,"wirebytes");s.packetBits=U(r,"packetbits");s.txRadio.baseFrequencyHz=D(r,"tx_frequency_hz");s.txRadio.bandwidthHz=D(r,"tx_bandwidth_hz");s.txRadio.antennaGainDb=D(r,"tx_gain_db");s.txRadio.antennaHeightMeters=D(r,"tx_height_m");s.startSec=D(r,"start_s");s.endSec=D(r,"end_s");s.preambleEndSec=D(r,"preamble_end_s");d->m_phy.SetLinkDistanceMeters(s.txId,2,D(r,"distance_m"));d->BeginReceiveSignal(s);
 }
};
int main(int argc,char**argv){NS_ABORT_MSG_IF(argc!=3,"Usage: replay INPUT_DIR OUTPUT_LOG");std::filesystem::path I=argv[1];setenv("CSR_REPLAY_CAPTURE",argv[2],1);Rpl::replay=true;
 auto rows=Read((I/"inputs.csv").string());auto draws=Read((I/"draws.csv").string());std::map<uint64_t,std::vector<Ptr<Packet>>> children;
 for(const auto&r:Read((I/"children.csv").string())){auto hex=r.at("packet_hex");std::vector<uint8_t>b;for(size_t j=0;j<hex.size();j+=2)b.push_back(std::stoul(hex.substr(j,2),nullptr,16));children[U(r,"signal_id")].push_back(Create<Packet>(b.data(),b.size()));}
 for(const auto&r:draws)Rpl::drawValues[Rpl::DrawKey(U(r,"signal_id"),D(r,"interval_start_s"),D(r,"interval_end_s"),r.at("phase").c_str())]=D(r,"uniform");
 auto d=CreateObject<CsrNetDevice>(2);d->GetPhy().profile.rxBaseFrequencyHz=400000000;d->GetPhy().profile.txBaseFrequencyHz=400000000;d->SetActiveNodesForPostTx(3);d->EnableOpnetAlignedDutyCycling(true);
 std::vector<Row> all=rows;
 for(auto r:Read((I/"controls.csv").string()))all.push_back(r);
 std::stable_sort(all.begin(),all.end(),[](const Row&a,const Row&b){return std::pair(U(a,"time_ns"),U(a,"event_order"))<std::pair(U(b,"time_ns"),U(b,"event_order"));});
 for(const auto&r:all){
  if(U(r,"time_ns")>=669000000000ULL)continue;
  if(r.at("kind")=="prep_tx" || r.at("kind")=="cancel_post_tx_wait"){
   Simulator::Schedule(NanoSeconds(U(r,"time_ns")),[d,r](){if(r.at("kind")=="prep_tx")Rpl::externalPrep=U(r,"value");else CsrPhyFrontEndSmokeAccess::Cancel(d);});
  } else if(r.at("kind")=="signal"){
   if(!r.at("sync_threshold_db").empty())Rpl::syncValues[U(r,"signal_id")]=D(r,"sync_threshold_db");
   Simulator::Schedule(NanoSeconds(U(r,"time_ns")),[d,r,&children](){CsrPhyFrontEndSmokeAccess::Receive(d,r,children.at(U(r,"signal_id")));});
  } else {
   if(U(r,"end_ns")<669000000000ULL)Rpl::finishEmpty[U(r,"end_ns")]=U(r,"queues_empty_at_end");
   Simulator::Schedule(NanoSeconds(U(r,"time_ns")),[d,r](){double duration=((U(r,"preamblebits")+48)/4.0)*.00051+(U(r,"wirebytes")*8+32)/CsrRateKeyToBps(U(r,"rate"));d->GetMac().NotifyPhyTxStart(Seconds(duration));});
  }
 }
 Simulator::Stop(Seconds(669));Simulator::Run();Simulator::Destroy();Rpl::Out().flush();
}
