#pragma once
// Test-only seams for an isolated native header overlay. Production sources
// and shared libraries never include this file. Empty hooks preserve the
// pinned raw RNG draw and ordinary physical transport exactly.
#include "ns3/packet.h"
#include "ns3/nstime.h"
#include <functional>
#include <vector>

namespace csr_t12 {
inline std::function<int(uint32_t, int, int)> rawDraw;
inline std::function<void(uint32_t, int, uint32_t)> resolvedDraw;
inline std::function<void(uint32_t, const std::vector<ns3::Ptr<ns3::Packet>>&,
                         ns3::Time, int, double, int, int)> transport;
}
