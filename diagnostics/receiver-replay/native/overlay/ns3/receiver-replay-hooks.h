#pragma once
#include <fstream>
#include <iomanip>
#include <cstdlib>
#include <map>
#include <sstream>
namespace Rpl {
inline bool replay=false;
inline std::ofstream stream;
inline uint64_t order=0, eventOrder=0;
inline bool contextActive=false;
inline uint64_t contextSignal=0;
inline double contextStart=0,contextEnd=0;
inline std::map<uint64_t,double> syncValues;
inline std::map<std::string,double> drawValues;
inline bool Active(uint32_t node) { return node==2 && Simulator::Now().GetSeconds()>=620.0; }
inline std::ofstream& Out() { if(!stream.is_open()){const char* p=std::getenv("CSR_REPLAY_CAPTURE");if(p)stream.open(p);}return stream; }
inline int64_t Ns(double value){return Seconds(value).GetNanoSeconds();}
inline bool IsReplay(uint32_t node){return replay && node==2;}
inline std::string DrawKey(uint64_t id,double start,double end,const char* phase){return std::to_string(id)+":"+std::to_string(Ns(start))+":"+std::to_string(Ns(end))+":"+phase;}
inline void Context(uint32_t node,uint64_t id,double start,double end){contextActive=Active(node);contextSignal=id;contextStart=start;contextEnd=end;}
inline void ClearContext(){contextActive=false;}
inline double Draw(const Ptr<UniformRandomVariable>& rng,uint32_t bits,double p,const char* phase){
 if(bits==0 || p<=0 || p>=1)return 1.0;
 double u;
 if(replay && contextActive){auto k=DrawKey(contextSignal,contextStart,contextEnd,phase);auto it=drawValues.find(k);NS_ABORT_MSG_IF(it==drawValues.end(),"Missing semantic draw "<<k);u=it->second;}
 else u=rng==nullptr?1.0:rng->GetValue(0.0,1.0);
 if(contextActive)Out()<<std::setprecision(17)<<"DRAW|"<<contextSignal<<"|"<<contextStart<<"|"<<contextEnd<<"|"<<phase<<"|"<<u<<"|"<<bits<<"|"<<p<<"\n";
 return u;
}
inline bool externalPrep=false;
inline std::map<int64_t,bool> finishEmpty;
inline bool Preparation(uint32_t node,bool actual){return IsReplay(node)?externalPrep:actual;}
inline void PrepChanged(uint32_t node,bool value){if(!replay && node==2)Out()<<"CONTROL|"<<++order<<"|"<<Simulator::Now().GetNanoSeconds()<<"|prep_tx|"<<value<<"\n";}
inline void CancelWait(uint32_t node){if(!replay && Active(node))Out()<<"CONTROL|"<<++order<<"|"<<Simulator::Now().GetNanoSeconds()<<"|cancel_post_tx_wait|1\n";}
inline bool FinishControl(uint32_t node,bool empty,uint32_t active){if(!Active(node))return empty;if(replay){auto t=Simulator::Now().GetNanoSeconds();NS_ABORT_MSG_IF(!finishEmpty.count(t),"Missing TX finish control");return finishEmpty.at(t);}Out()<<"FINISH|"<<Simulator::Now().GetNanoSeconds()<<"|"<<empty<<"|"<<active<<"\n";return empty;}
inline double SyncValue(uint64_t id){NS_ABORT_MSG_IF(!syncValues.count(id),"Missing SYNC draw");return syncValues.at(id);}
inline void Sync(uint32_t node,uint64_t id,double threshold){if(Active(node))Out()<<std::setprecision(17)<<"SYNC|"<<id<<"|"<<threshold<<"\n";}
inline void Event(uint32_t node,uint64_t id,const char* stage,uint32_t source,uint16_t seq,const std::string& result,const std::string& reason,int before,int after){if(Active(node))Out()<<"EVENT|"<<++eventOrder<<"|"<<Simulator::Now().GetNanoSeconds()<<"|"<<id<<"|"<<stage<<"|"<<source<<"|"<<seq<<"|"<<result<<"|"<<reason<<"|"<<before<<"|"<<after<<"\n";}
inline void Children(uint64_t id,const std::vector<Ptr<Packet>>& frames){
 for(size_t i=0;i<frames.size();++i){CsrHeader h;frames[i]->PeekHeader(h);std::vector<uint8_t> bytes(frames[i]->GetSize());frames[i]->CopyData(bytes.data(),bytes.size());std::ostringstream hex;hex<<std::hex<<std::setfill('0');for(auto b:bytes)hex<<std::setw(2)<<unsigned(b);Out()<<"CHILD|"<<id<<"|"<<i<<"|"<<h.GetSrc()<<"|"<<h.GetDst()<<"|"<<h.GetSeq()<<"|"<<unsigned(h.GetType())<<"|"<<CsrGetOpnetWireSize(frames[i])<<"|"<<hex.str()<<"\n";}
}
template<class S> inline void Input(uint32_t node,const S& s,int64_t time){if(!Active(node))return;CsrHeader h;s.frames.front()->PeekHeader(h);Out()<<std::setprecision(17)<<"INPUT|"<<++order<<"|"<<time<<"|signal|"<<s.id<<"|"<<s.txId<<"|"<<h.GetDst()<<"|"<<s.sequence<<"|"<<s.payloadBytes<<"|"<<(s.preamble==PREAMBLE_LONG?7888:104)<<"|"<<s.packetBits<<"|"<<s.rateKbps<<"|"<<s.txPowerDbm<<"|"<<s.rxPowerDbm<<"|"<<s.frontEnd.backgroundNoiseWatts<<"|"<<s.frontEnd.distanceMeters<<"|"<<s.startSec<<"|"<<s.endSec<<"|"<<s.preambleEndSec<<"|"<<s.reservedSlot<<"|"<<s.ackable<<"|"<<s.frontEnd.channelMatched<<"|"<<s.txRadio.baseFrequencyHz<<"|"<<s.txRadio.bandwidthHz<<"|"<<s.txRadio.antennaGainDb<<"|"<<s.txRadio.antennaHeightMeters<<"\n";Children(s.id,s.frames);}
inline void OwnTx(uint32_t node,uint64_t id,uint32_t txid,uint16_t seq,uint32_t bytes,uint32_t bits,int rate,double power,int preamble,int slot,bool ackable,double start,double duration,double preambleSec,const std::vector<Ptr<Packet>>& frames){if(!Active(node))return;CsrHeader h;frames.front()->PeekHeader(h);Out()<<std::setprecision(17)<<"INPUT|"<<++order<<"|"<<Simulator::Now().GetNanoSeconds()<<"|own_tx|"<<id<<"|"<<txid<<"|"<<h.GetDst()<<"|"<<seq<<"|"<<bytes<<"|"<<(preamble==PREAMBLE_LONG?7888:104)<<"|"<<bits<<"|"<<rate<<"|"<<power<<"|nan|nan|0|"<<start<<"|"<<start+duration<<"|"<<start+preambleSec<<"|"<<slot<<"|"<<ackable<<"|1|400000000|1000000|0|1\n";Children(id,frames);}
}
