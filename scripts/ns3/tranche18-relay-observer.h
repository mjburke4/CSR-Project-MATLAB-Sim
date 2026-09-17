#pragma once
// Read-only Tranche 18 side channel. The overlay captures native trace records
// and scalar state at decision sites. It adds no model events, RNG draws,
// packet metadata, queue mutation or radio/scheduler policy.
// next_hop is preserved separately: nwk_forward.peer denotes ingress.
// The hop_retry hook observes submission to MAC, not an OTA transmission.
#include <array>

namespace ns3 {

inline std::ofstream g_tranche18ServiceStream;
inline uint64_t g_tranche18ServiceIndex {0};
inline double g_tranche18ServiceStart {300.0};
inline double g_tranche18ServiceStop {320.0};
inline uint64_t g_tranche18ServiceLimit {100000};

inline bool
Tranche18ServiceActive ()
{
  if (!g_tranche18ServiceStream.is_open ()) return false;
  const double now = Simulator::Now ().GetSeconds ();
  return now >= g_tranche18ServiceStart && now < g_tranche18ServiceStop;
}

inline void
Tranche18OpenServiceCsv (const std::string &path, double start, double stop,
                        uint64_t limit)
{
  if (path.empty ()) return;
  NS_ABORT_MSG_IF (!std::isfinite (start) || !std::isfinite (stop) ||
                   start < 0 || stop <= start || limit == 0,
                   "Invalid passive ACK service observation window");
  g_tranche18ServiceStart = start;
  g_tranche18ServiceStop = stop;
  g_tranche18ServiceLimit = limit;
  g_tranche18ServiceStream.open (path, std::ios::out | std::ios::trunc);
  NS_ABORT_MSG_IF (!g_tranche18ServiceStream.is_open (),
                   "Cannot open passive ACK service observer");
  g_tranche18ServiceStream
    << "schema,event_index,time_s,event,node,peer,packet_type,src,dst,sequence,"
       "success,reason,reservation_slot,reservation_counter,detail,packet_uid,"
       "prior_packet_uid,decision_id,prior_decision_id,mac_state,preparation_active,"
       "holdoff_over,sync_present,ack_queue,data_queue,tx_in_progress,rate_kbps,"
       "size_bytes,rx_power_dbm,pathloss_db,snr_db,jsr_db,header_errors,payload_errors,"
       "total_errors,statistic,value,next_hop,route_cost\n";
}

using Tranche18ExtraFields = std::array<std::string, 11>;

inline void
Tranche18WriteService (const CsrDifferentialTraceEvent &event,
                      const Tranche18ExtraFields &extra = {})
{
  if (!Tranche18ServiceActive ()) return;
  NS_ABORT_MSG_IF (g_tranche18ServiceIndex >= g_tranche18ServiceLimit,
                   "Passive ACK service observer record limit exceeded");
  const std::string fields[] = {
    "csr-ns3-relay-service-v1", CsrTraceInteger (++g_tranche18ServiceIndex),
    CsrTraceDouble (Simulator::Now ().GetSeconds ()), event.event, event.node,
    event.peer, event.packetType, event.source, event.destination, event.sequence,
    event.success, event.reason, event.reservationSlot, event.reservationCounter,
    event.detail, extra[0], extra[1], extra[2], extra[3], extra[4], extra[5],
    extra[6], extra[7], extra[8], extra[9], extra[10], event.rateKbps,
    event.sizeBytes, event.rxPowerDbm, event.pathlossDb, event.snrDb, event.jsrDb,
    event.headerErrors, event.payloadErrors, event.totalErrors, event.statistic,
    event.value, event.nextHop, event.routeCost
  };
  for (std::size_t index = 0; index < sizeof (fields)/sizeof (fields[0]); ++index)
    {
      if (index) g_tranche18ServiceStream << ',';
      g_tranche18ServiceStream << CsrTraceCsvEscape (fields[index]);
    }
  g_tranche18ServiceStream << '\n';
}

inline void
Tranche18ObserveDifferential (const CsrDifferentialTraceEvent &event)
{
  Tranche18WriteService (event);
}

inline void
Tranche18MacSnapshot (const char *stage, uint32_t node, uint32_t peer,
                     const char *state, bool preparing, bool holdoff, bool sync,
                     uint64_t acks, uint64_t data, bool transmitting,
                     int64_t slot, int64_t counter,
                     Ptr<const Packet> frame = nullptr,
                     Ptr<const Packet> prior = nullptr,
                     const std::string &detail = "")
{
  if (!Tranche18ServiceActive ()) return;
  CsrDifferentialTraceEvent event;
  event.event = stage;
  event.node = CsrTraceInteger (node);
  event.peer = CsrTraceInteger (peer);
  event.reservationSlot = CsrTraceSignedInteger (slot);
  event.reservationCounter = CsrTraceSignedInteger (counter);
  event.detail = detail;
  Tranche18ExtraFields extra;
  if (frame != nullptr)
    {
      extra[0] = CsrTraceInteger (frame->GetUid ());
      const auto found = g_tranche8FeedbackByUid.find (frame->GetUid ());
      if (found != g_tranche8FeedbackByUid.end ())
        extra[2] = CsrTraceInteger (found->second.decisionId);
      CsrDifferentialAppTag app;
      if (frame->PeekPacketTag (app)) event.sequence = CsrTraceInteger (app.GetSequence ());
      ::CsrHeader header;
      if (frame->PeekHeader (header))
        {
          event.source = CsrTraceInteger (header.GetSrc ());
          event.destination = CsrTraceInteger (header.GetDst ());
          event.packetType = header.IsDack () ? "dack" : header.IsAck () ? "ack" : "other";
          event.detail += (event.detail.empty () ? "" : ";") +
            std::string ("hop_sequence=") + CsrTraceInteger (header.GetSeq ()) +
            ";has_ack_window=" + CsrTraceInteger (header.HasAckWindow () ? 1 : 0) +
            ";ack_bitmap=" + CsrTraceInteger (header.GetAckBitmap ()) +
            ";dack_bitmap=" + CsrTraceInteger (header.GetDackBitmap ());
        }
    }
  if (prior != nullptr)
    {
      extra[1] = CsrTraceInteger (prior->GetUid ());
      const auto found = g_tranche8FeedbackByUid.find (prior->GetUid ());
      if (found != g_tranche8FeedbackByUid.end ())
        extra[3] = CsrTraceInteger (found->second.decisionId);
    }
  extra[4] = state;
  extra[5] = preparing ? "1" : "0";
  extra[6] = holdoff ? "1" : "0";
  extra[7] = sync ? "1" : "0";
  extra[8] = CsrTraceInteger (acks);
  extra[9] = CsrTraceInteger (data);
  extra[10] = transmitting ? "1" : "0";
  Tranche18WriteService (event, extra);
}

inline void
Tranche18CloseServiceCsv ()
{
  if (!g_tranche18ServiceStream.is_open ()) return;
  g_tranche18ServiceStream.flush ();
  NS_ABORT_MSG_IF (!g_tranche18ServiceStream.good (),
                   "Passive ACK service observer flush failed");
  g_tranche18ServiceStream.close ();
}

} // namespace ns3
