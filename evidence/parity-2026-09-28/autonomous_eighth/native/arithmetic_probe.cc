#include "ns3/core-module.h"
#include "ns3/csr-phy-model.h"
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>
using namespace ns3;
void number(const std::string& label,double value) {
  uint64_t bits;std::memcpy(&bits,&value,8);
  std::cout<<label<<','<<std::setprecision(17)<<value<<",0x"<<std::hex<<bits<<std::dec<<'\n';
}
int main(int argc,char**argv) {
  if(argc>1 && std::string(argv[1])=="--clock") {
    std::cout<<"time_ns,native_seconds,division_seconds,native_bits,division_bits\n";
    int64_t ticks;
    while(std::cin>>ticks) {
      double native=NanoSeconds(ticks).GetSeconds(),division=double(ticks)/1e9;
      uint64_t n,d;std::memcpy(&n,&native,8);std::memcpy(&d,&division,8);
      std::cout<<ticks<<','<<std::setprecision(17)<<native<<','<<division<<",0x"<<std::hex<<n<<",0x"<<d<<std::dec<<'\n';
    }
    return 0;
  }
  // Arithmetic-only. No Simulator::Run, callback, or random draw.
  const int64_t origin=45656008077LL;
  const double start=NanoSeconds(origin).GetSeconds(),delay=0.006630;
  const Time deadline=NanoSeconds(origin)+Seconds(delay);
  const double nativeEnd=deadline.GetSeconds();
  const double floatingEnd=start+delay;
  const double divisionEnd=double(origin+6630000LL)/1e9;
  const double rate=CsrRateKeyToBps(8);
  std::cout<<"quantity,value,binary64_bits\n";
  number("delay_seconds",delay);number("delay_native_ns",Seconds(delay).GetNanoSeconds());
  number("origin_seconds",start);number("deadline_native_ns",deadline.GetNanoSeconds());
  number("native_deadline_seconds",nativeEnd);number("floating_sum_seconds",floatingEnd);
  number("ns_sum_division_seconds",divisionEnd);number("end_delta_seconds",floatingEnd-nativeEnd);
  number("payload_rate",rate);number("native_product",(nativeEnd-start)*rate);
  number("floating_product",(floatingEnd-start)*rate);
  number("native_bits",static_cast<uint32_t>((nativeEnd-start)*rate));
  number("floating_bits",static_cast<uint32_t>((floatingEnd-start)*rate));
  number("native_errors",CsrPhyModel::SampleSourceBinomial(51,5.4585990544445831e-5,0.57293482082207758));
  number("floating_errors_same_uniform",CsrPhyModel::SampleSourceBinomial(52,5.4585990544445831e-5,0.57293482082207758));
  if(deadline.GetNanoSeconds()!=45662638077LL || nativeEnd!=divisionEnd ||
     static_cast<uint32_t>((nativeEnd-start)*rate)!=51 ||
     static_cast<uint32_t>((floatingEnd-start)*rate)!=52) return 1;
}
