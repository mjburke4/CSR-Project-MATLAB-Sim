#pragma once
// Observation-only bounded native CSR capture. No scheduling or RNG draws.
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <initializer_list>
#include <map>
#include <sstream>
#include <string>
#include <utility>

namespace Sc {

inline uint64_t ordinal = 0;
inline std::ofstream stream;
inline unsigned receiver = 0;
inline uint64_t signal = 0;
inline std::map<unsigned,uint64_t> uniformOrdinal, normalOrdinal;
inline std::map<std::pair<unsigned,uint64_t>,uint64_t> signalIntervalOrdinal;
inline uint64_t intervalOrdinal = 0;
inline const char *component = "";
inline double intervalStart = 0.0, intervalEnd = 0.0;
inline double componentStart = 0.0, componentEnd = 0.0;

inline bool Window ()
{
  const auto now = Simulator::Now ().GetNanoSeconds ();
  return now >= 300000000000LL && now < 330000000000LL;
}

inline bool Selected (unsigned node)
{
  return node == 1 || node == 2 || node == 3 || node == 4 ||
         node == 5 || node == 7 || node == 8;
}

inline std::string EscapeJson (const std::string &s)
{
  std::ostringstream out;
  out << '"';
  for (unsigned char ch : s)
    {
      if (ch == '"' || ch == '\\') { out << '\\' << ch; }
      else if (ch == '\n') { out << "\\n"; }
      else if (ch == '\r') { out << "\\r"; }
      else if (ch == '\t') { out << "\\t"; }
      else if (ch < 0x20) { out << "\\u" << std::hex << std::setw (4)
                                << std::setfill ('0') << unsigned (ch)
                                << std::dec << std::setfill (' '); }
      else { out << ch; }
    }
  out << '"';
  return out.str ();
}

inline std::string Cell (const std::string &s)
{
  std::string result;
  for (char ch : s)
    {
      if (ch == '\t') { result += "\\t"; }
      else if (ch == '\n') { result += "\\n"; }
      else if (ch == '\r') { result += "\\r"; }
      else { result += ch; }
    }
  return result;
}

template <typename T>
inline std::string To (const T &value)
{
  std::ostringstream out;
  out << std::setprecision (17) << value;
  return out.str ();
}

template <typename T>
inline std::pair<std::string, std::string> V (const char *key, const T &value)
{
  return {key, To (value)};
}

inline void Record (unsigned node, const char *layer, const char *event,
                    std::initializer_list<std::pair<std::string, std::string>> data)
{
  if (!Selected (node) || !Window ()) { return; }
  if (!stream.is_open ())
    {
      const char *path = std::getenv ("CSR_SOURCE5_CAPTURE");
      if (!path) { return; }
      stream.open (path);
      NS_ABORT_MSG_IF (!stream.is_open (), "Cannot open CSR_SOURCE5_CAPTURE");
      stream << "time_ns\tevent_order\tcase_id\tnode\tlayer\tevent\tpeer"
                "\tframe_id\ttx_id\tapp_source\tapp_sequence\tkind"
                "\toutcome\treason\tstate_before\tstate_after\tpending_data"
                "\tpeer_outstanding\tpeer_threshold\tnwk_waiting"
                "\tmac_ack_depth\tmac_data_depth\tdetail_json\n";
    }
  std::map<std::string, std::string> values (data.begin (), data.end ());
  std::array<std::string, 16> columns = {
      "peer", "frame_id", "tx_id", "app_source", "app_sequence",
      "kind", "outcome", "reason", "state_before", "state_after",
      "pending_data", "peer_outstanding", "peer_threshold", "nwk_waiting",
      "mac_ack_depth", "mac_data_depth"};
  stream << Simulator::Now ().GetNanoSeconds () << '\t' << ++ordinal
         << "\tsource5_132\t" << node << '\t';
  for (const char *p = layer; *p; ++p)
    {
      stream << char (std::toupper (static_cast<unsigned char> (*p)));
    }
  stream << '\t' << event;
  for (const auto &key : columns)
    {
      auto it = values.find (key);
      stream << '\t' << (it == values.end () ? "" : Cell (it->second));
      if (it != values.end ()) { values.erase (it); }
    }
  stream << '\t' << '{';
  bool first = true;
  for (const auto &[key, value] : values)
    {
      if (!first) { stream << ','; }
      first = false;
      stream << EscapeJson (key) << ':' << EscapeJson (value);
    }
  stream << "}\n";
}

struct RxContext
{
  unsigned prevReceiver;
  uint64_t prevSignal;
  RxContext (unsigned node, uint64_t id)
    : prevReceiver (receiver), prevSignal (signal)
  { receiver = node; signal = id; }
  ~RxContext () { receiver = prevReceiver; signal = prevSignal; }
};

inline void BeginErrorInterval (unsigned node, uint64_t id, double begin,
                                double end, double noiseWatts,
                                double jsrDb, double offsetSeconds,
                                uint32_t collisions, bool sameRate)
{
  intervalOrdinal = ++signalIntervalOrdinal[{node, id}];
  intervalStart = begin;
  intervalEnd = end;
  Record (node, "phy", "rx_error_interval",
          {V ("tx_id", id), V ("interval_ordinal", intervalOrdinal),
           V ("interval_start_sec", begin), V ("interval_end_sec", end),
           V ("interval_start_ns", Seconds (begin).GetNanoSeconds ()),
           V ("interval_end_ns", Seconds (end).GetNanoSeconds ()),
           V ("noise_watts", noiseWatts), V ("jsr_db", jsrDb),
           V ("offset_sec", offsetSeconds), V ("collisions", collisions),
           V ("same_rate_interference", sameRate)});
}

struct ErrorIntervalContext
{
  uint64_t previousOrdinal;
  double previousStart, previousEnd;
  ErrorIntervalContext (unsigned node, uint64_t id, double begin,
                        double end, double noiseWatts, double jsrDb,
                        double offsetSeconds, uint32_t collisions,
                        bool sameRate)
    : previousOrdinal (intervalOrdinal), previousStart (intervalStart),
      previousEnd (intervalEnd)
  {
    BeginErrorInterval (node, id, begin, end, noiseWatts, jsrDb,
                        offsetSeconds, collisions, sameRate);
  }
  ~ErrorIntervalContext ()
  {
    intervalOrdinal = previousOrdinal;
    intervalStart = previousStart;
    intervalEnd = previousEnd;
  }
};

struct DrawSite
{
  const char *lastComponent;
  double lastStart, lastEnd;
  DrawSite (const char *label, double begin, double end)
    : lastComponent (component), lastStart (componentStart),
      lastEnd (componentEnd)
  { component = label; componentStart = begin; componentEnd = end; }
  ~DrawSite ()
  { component = lastComponent; componentStart = lastStart; componentEnd = lastEnd; }
};

inline double Uniform (const Ptr<UniformRandomVariable> &rng,
                       double lower, double upper, uint32_t bits,
                       double probability)
{
  double value = rng == nullptr ? 1.0 : rng->GetValue (lower, upper);
  const auto drawOrdinal = rng == nullptr ? 0 : ++uniformOrdinal[receiver];
  Record (receiver, "phy", "rx_binomial_draw",
          {V ("tx_id", signal), V ("kind", "uniform"),
           V ("draw", value), V ("low", lower), V ("high", upper),
           V ("bits", bits), V ("probability", probability),
           V ("draw_ordinal", drawOrdinal),
           V ("interval_ordinal", intervalOrdinal),
           V ("component", component),
           V ("interval_start_sec", intervalStart),
           V ("interval_end_sec", intervalEnd),
           V ("interval_start_ns", Seconds (intervalStart).GetNanoSeconds ()),
           V ("interval_end_ns", Seconds (intervalEnd).GetNanoSeconds ()),
           V ("component_start_sec", componentStart),
           V ("component_end_sec", componentEnd),
           V ("component_start_ns", Seconds (componentStart).GetNanoSeconds ()),
           V ("component_end_ns", Seconds (componentEnd).GetNanoSeconds ()),
           V ("rng_consumed", rng != nullptr)});
  return value;
}

inline double Normal (const Ptr<NormalRandomVariable> &rng,
                      double mean, double variance)
{
  const double value = rng->GetValue (mean, variance);
  const auto drawOrdinal = ++normalOrdinal[receiver];
  Record (receiver, "phy", "rx_sync_draw",
          {V ("tx_id", signal), V ("kind", "normal"),
           V ("draw", value), V ("mean", mean), V ("variance", variance),
           V ("draw_ordinal", drawOrdinal)});
  return value;
}

} // namespace Sc
