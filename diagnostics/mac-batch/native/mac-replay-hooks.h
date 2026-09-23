#pragma once
#include <fstream>
#include <iomanip>
#include <cstdlib>
#include <map>
#include <sstream>
#include <deque>
namespace Mr {
class FrameTag: public Tag {
public:
 uint64_t id=0;
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::MacReplayFrameTag").SetParent<Tag>().AddConstructor<FrameTag>();return t;}
 TypeId GetInstanceTypeId()const override{return GetTypeId();}
 uint32_t GetSerializedSize()const override{return 8;}
 void Serialize(TagBuffer b)const override{b.WriteU64(id);}
 void Deserialize(TagBuffer b)override{id=b.ReadU64();}
 void Print(std::ostream&o)const override{o<<id;}
};
inline bool replay=false, internalState=false;
inline uint64_t order=0, frameId=0;
inline std::map<unsigned,unsigned> ordinals;
struct DrawRow { uint64_t time; int low,high,value; };
inline std::map<unsigned,std::deque<DrawRow>> draws;
inline std::ofstream stream;
inline bool Active(unsigned n){return n==2||n==4||n==8;}
inline std::ofstream& Out(){if(!stream.is_open()){const char*p=std::getenv("CSR_MAC_CAPTURE");if(p)stream.open(p);}return stream;}
template<class... T> inline void Input(unsigned node,const char* kind,T... values){if(replay||!Active(node))return;Out()<<std::setprecision(17)<<"INPUT|"<<++order<<"|"<<Simulator::Now().GetNanoSeconds()<<"|"<<node<<"|"<<kind;((Out()<<"|"<<values),...);Out()<<"\n";}
inline int Draw(const Ptr<UniformRandomVariable>& rng,unsigned node,int low,int high){int value;auto ordinal=++ordinals[node];if(replay&&Active(node)){auto&q=draws[node];NS_ABORT_MSG_IF(q.empty(),"MAC draw exhausted node "<<node);auto r=q.front();q.pop_front();NS_ABORT_MSG_IF(r.time!=uint64_t(Simulator::Now().GetNanoSeconds())||r.value<low||r.value>high||r.low!=low||r.high!=high,"MAC draw range mismatch node "<<node<<" ordinal "<<ordinal);value=r.value;}else value=rng->GetInteger(low,high);if(Active(node))Out()<<"DRAW|"<<++order<<"|"<<Simulator::Now().GetNanoSeconds()<<"|"<<node<<"|"<<ordinal<<"|"<<low<<"|"<<high<<"|"<<value<<"\n";return value;}
inline std::string Hex(Ptr<Packet> frame){std::vector<uint8_t>b(frame->GetSize());frame->CopyData(b.data(),b.size());std::ostringstream s;s<<std::hex<<std::setfill('0');for(auto v:b)s<<std::setw(2)<<unsigned(v);return s.str();}
inline void Frame(unsigned node,uint64_t id,Ptr<Packet> frame){CsrHeader h;frame->PeekHeader(h);CsrOpnetPacketFormat format;uint32_t wire;CsrGetOpnetEnvelope(frame,format,wire);std::ostringstream dest;for(auto d:h.GetDestinationSequences()){if(dest.tellp()>0)dest<<";";dest<<d.first<<":"<<d.second;}Out()<<std::setprecision(17)<<"FRAME|"<<id<<"|"<<node<<"|"<<h.GetSrc()<<"|"<<h.GetDst()<<"|"<<h.GetSeq()<<"|"<<unsigned(h.GetType())<<"|"<<unsigned(h.GetDscp())<<"|"<<h.IsAckable()<<"|"<<h.IsAck()<<"|"<<h.IsDack()<<"|"<<h.HasAckWindow()<<"|"<<h.GetAckBitmap()<<"|"<<h.GetDackBitmap()<<"|"<<h.GetSpeedKey()<<"|"<<h.HasLinkControl()<<"|"<<h.GetTxPowerDbm()<<"|"<<h.GetRxPowerDbm()<<"|"<<CsrGetOpnetWireSize(frame)<<"|"<<int(format)<<"|"<<(frame->GetSize()-h.GetSerializedSize())<<"|"<<dest.str()<<"|"<<Hex(frame)<<"\n";}
inline void Enqueue(unsigned node,Ptr<Packet> frame,unsigned dest,unsigned dscp,bool ackable){if(replay||!Active(node))return;auto id=++frameId;FrameTag tag;tag.id=id;frame->ReplacePacketTag(tag);Frame(node,id,frame);Input(node,"enqueue",dest,dscp,ackable,id);}
inline void Tx(unsigned node,const std::vector<Ptr<Packet>>&frames,int rate,double power,int preamble,int slot,int consumed){if(!Active(node))return;Out()<<std::setprecision(17)<<"TX|"<<++order<<"|"<<Simulator::Now().GetNanoSeconds()<<"|"<<node<<"|"<<rate<<"|"<<power<<"|"<<preamble<<"|"<<slot<<"|"<<consumed<<"|"<<frames.size()<<"\n";for(size_t i=0;i<frames.size();++i){CsrHeader h;frames[i]->PeekHeader(h);FrameTag tag;frames[i]->PeekPacketTag(tag);Out()<<"TXFRAME|"<<Simulator::Now().GetNanoSeconds()<<"|"<<node<<"|"<<i<<"|"<<h.GetSrc()<<"|"<<h.GetDst()<<"|"<<h.GetSeq()<<"|"<<unsigned(h.GetType())<<"|"<<CsrGetOpnetWireSize(frames[i])<<"|"<<tag.id<<"\n";}}
}
