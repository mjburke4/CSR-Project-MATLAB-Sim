#pragma once

// Passive, short-window native receiver input tape. The simulator always starts
// at t=0; this observer only writes rows during [25,85) seconds when enabled.
#include "ns3/simulator.h"

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <initializer_list>
#include <sstream>
#include <string>
#include <utility>

namespace DiscoveryCapture {

inline bool Enabled ()
{
  static const bool enabled = [] {
    const char *path = std::getenv ("CSR_DISCOVERY_CAPTURE");
    return path != nullptr && path[0] != '\0';
  } ();
  return enabled;
}

inline bool InWindow ()
{
  const int64_t ns = ns3::Simulator::Now ().GetNanoSeconds ();
  return Enabled () && ns >= 25000000000LL && ns < 85000000000LL;
}

inline std::string Number (double value)
{
  std::ostringstream out;
  out << std::setprecision (17) << value;
  return out.str ();
}

inline std::string Bool (bool value) { return value ? "true" : "false"; }

inline std::string Quote (const std::string &value)
{
  std::string output = "\"";
  for (unsigned char character : value)
    {
      if (character == '\"' || character == '\\')
        {
          output.push_back ('\\');
          output.push_back (static_cast<char> (character));
        }
      else if (character == '\n') { output += "\\n"; }
      else if (character == '\r') { output += "\\r"; }
      else if (character == '\t') { output += "\\t"; }
      else if (character < 0x20)
        {
          std::ostringstream hex;
          hex << "\\u" << std::hex << std::setw (4)
              << std::setfill ('0') << static_cast<unsigned> (character);
          output += hex.str ();
        }
      else { output.push_back (static_cast<char> (character)); }
    }
  return output + "\"";
}

inline std::ofstream &Stream ()
{
  static std::ofstream output;
  if (!output.is_open ())
    {
      const char *path = std::getenv ("CSR_DISCOVERY_CAPTURE");
      if (path != nullptr && path[0] != '\0')
        {
          output.open (path, std::ios::out | std::ios::trunc);
          NS_ABORT_MSG_IF (!output.is_open (),
                           "cannot open bounded discovery capture: " << path);
        }
    }
  return output;
}

using Detail = std::initializer_list<std::pair<std::string, std::string>>;
inline uint64_t eventOrder = 0;

inline void Write (const char *layer,
                   const char *event,
                   uint32_t node,
                   uint32_t peer,
                   uint64_t txId,
                   uint64_t frameId,
                   const char *reason,
                   const char *before,
                   const char *after,
                   Detail detail = {})
{
  if (!InWindow ()) { return; }
  auto &output = Stream ();
  output << "{\"case_id\":\"discovery131\",\"event_order\":"
         << ++eventOrder << ",\"time_ns\":"
         << ns3::Simulator::Now ().GetNanoSeconds ()
         << ",\"layer\":" << Quote (layer)
         << ",\"event\":" << Quote (event)
         << ",\"node\":" << node
         << ",\"peer\":";
  if (peer) { output << peer; } else { output << "null"; }
  output << ",\"frame_id\":";
  if (frameId) { output << frameId; } else { output << "null"; }
  output << ",\"tx_id\":";
  if (txId) { output << txId; } else { output << "null"; }
  output << ",\"app_source\":null,\"app_sequence\":null"
         << ",\"reason\":" << Quote (reason)
         << ",\"state_before\":" << Quote (before)
         << ",\"state_after\":" << Quote (after)
         << ",\"detail\":{";
  bool first = true;
  for (const auto &[key, value] : detail)
    {
      if (!first) { output << ','; }
      output << Quote (key) << ':' << Quote (value);
      first = false;
    }
  output << "}}\n";
}

struct ReceiverContext {
  uint32_t node = 0;
  uint32_t peer = 0;
  uint64_t signalId = 0;
  uint64_t intervalIndex = 0;
  const char *component = "unknown";
  uint64_t drawOrdinal = 0;
};
inline ReceiverContext current;

class ScopedReceiver {
public:
  ScopedReceiver (uint32_t node, uint32_t peer, uint64_t id,
                  uint64_t intervalIndex)
    : previous (current)
  {
    current = {node, peer, id, intervalIndex, "unknown", 0};
  }
  ~ScopedReceiver () { current = previous; }
  ScopedReceiver (const ScopedReceiver &) = delete;
  ScopedReceiver &operator= (const ScopedReceiver &) = delete;
private:
  ReceiverContext previous;
};

inline void SetComponent (const char *component)
{
  current.component = component;
}

inline void Uniform (uint32_t bits, double probability, double value)
{
  if (!current.signalId || !InWindow ()) { return; }
  Write ("PHY", "phy_uniform", current.node, current.peer,
         current.signalId, 0, "binomial", "", "",
         {{"ber_interval_index", std::to_string (current.intervalIndex)},
          {"component", current.component},
          {"draw_ordinal", std::to_string (++current.drawOrdinal)},
          {"bits", std::to_string (bits)},
          {"probability", Number (probability)},
          {"uniform", Number (value)}});
}

} // namespace DiscoveryCapture
