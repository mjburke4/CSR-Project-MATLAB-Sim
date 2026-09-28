#include "ns3/core-module.h"
#include "ns3/csr-phy-model.h"
#include <cmath>
#include <cstring>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <string>

using namespace ns3;
void number(const char *name,double x) {
  uint64_t bits; std::memcpy(&bits,&x,sizeof(bits));
  std::cout<<name<<","<<std::setprecision(17)<<x<<",0x"<<std::hex<<bits<<std::dec<<"\n";
}
void allocation(const char *name,double start,double intervalStart,double intervalEnd) {
  const double rate=CsrRateKeyToBps(8);
  const double headerStart=start+7888.0/rate;
  const double payloadStart=start+7936.0/rate;
  const double packetEnd=payloadStart+184.0/rate;
  const double end=std::min(intervalEnd,packetEnd);
  const double headerBegin=std::max(intervalStart,headerStart);
  const double headerEnd=std::min(end,payloadStart);
  const double payloadBegin=std::max(intervalStart,payloadStart);
  const double headerProduct=std::max(0.0,headerEnd-headerBegin)*rate;
  const double payloadProduct=std::max(0.0,end-payloadBegin)*rate;
  std::string p=std::string(name)+".";
  number((p+"signal_start").c_str(),start);
  number((p+"interval_start").c_str(),intervalStart);
  number((p+"interval_end").c_str(),intervalEnd);
  number((p+"header_start").c_str(),headerStart);
  number((p+"payload_start").c_str(),payloadStart);
  number((p+"packet_end").c_str(),packetEnd);
  number((p+"bounded_end").c_str(),end);
  number((p+"header_product").c_str(),headerProduct);
  number((p+"payload_product").c_str(),payloadProduct);
  number((p+"header_bits").c_str(),static_cast<uint32_t>(headerProduct));
  number((p+"payload_bits").c_str(),static_cast<uint32_t>(payloadProduct));
}
int main(int argc,char **argv) {
  if(argc>1 && std::string(argv[1])=="--clock-values") {
    std::cout<<"time_ns,native_seconds,native_bits,division_seconds,division_bits,multiplication_seconds,multiplication_bits\n";
    int64_t ns;
    while(std::cin>>ns) {
      const double native=NanoSeconds(ns).GetSeconds();
      const double divided=double(ns)/1e9;
      const double multiplied=double(ns)*1e-9;
      uint64_t n,d,m;std::memcpy(&n,&native,8);std::memcpy(&d,&divided,8);std::memcpy(&m,&multiplied,8);
      std::cout<<ns<<","<<std::setprecision(17)<<native<<",0x"<<std::hex<<n<<std::dec
        <<","<<divided<<",0x"<<std::hex<<d<<std::dec<<","<<multiplied<<",0x"<<std::hex<<m<<std::dec<<"\n";
    }
    return 0;
  }
  // Captured raw signal geometry and per-node native draws. No simulator run
  // or random call occurs: SampleSourceBinomial uses its explicit-u overload.
  const double rawStart=10.465023527005155;
  const double rawEnd=11.500323527005154;
  const double nativeStart=NanoSeconds(10465023527LL).GetSeconds();
  const double nativeEnd=NanoSeconds(11500323527LL).GetSeconds();
  const double p=0.015116561887016548;
  const double u=0.45559117029490032;
  std::cout<<"quantity,value,double_bits\n";
  number("rate",CsrRateKeyToBps(8));
  number("raw_end_minus_native_end",rawEnd-nativeEnd);
  number("native_end_get_seconds",nativeEnd);
  number("ns_division_end",double(11500323527LL)/1e9);
  number("ns_multiply_end",double(11500323527LL)*1e-9);
  allocation("native_mixed_time",rawStart,nativeStart,nativeEnd);
  allocation("matlab_raw_callbacks",rawStart,rawStart,rawEnd);
  allocation("only_end_callback_quantized",rawStart,rawStart,nativeEnd);
  allocation("all_signal_fields_quantized",nativeStart,nativeStart,nativeEnd);
  number("native_payload_errors_n183",CsrPhyModel::SampleSourceBinomial(183,p,u));
  number("matlab_payload_errors_n184_same_u",CsrPhyModel::SampleSourceBinomial(184,p,u));
  number("header_errors_n47",CsrPhyModel::SampleSourceBinomial(47,p,0.91001119820455312));
  CsrPhyModel model;
  const auto ecc=model.EvaluateEcc(8120,7888,4,true,false,false);
  number("protected_bits",ecc.protectedBits);
  number("correctable_bits",ecc.correctableBits);
  number("default_ecc_accepted_if_prior_accepted",ecc.accepted);
}
