#pragma once
// Read-only Tranche 9 side channel. The overlay captures native trace records
// and scalar state at decision sites. It adds no model events, RNG draws,
// packet metadata, queue mutation or radio/scheduler policy.
#include <array>

namespace ns3 {

inline std::ofstream g_tranche9ServiceStream;
inline uint64_t g_tranche9ServiceIndex {0};
inline double g_tranche9ServiceStart {300.0};
inline double g_tranche9ServiceStop {320.0};
inline uint64_t g_tranche9ServiceLimit {100000};

inline bool
Tranche9ServiceActive ()
{
  if (!g_tranche9ServiceStream.is_open ()) return false;
  const double now = Simulator::Now ().GetSeconds ();
  return now >= g_tranche9ServiceStart && now < g_tranche9ServiceStop;
}

inline void
Tranche9OpenServiceCsv (const std::string &path, double start, double stop,
                        uint64_t limit)
{
  if (path.empty ()) return;
  NS_ABORT_MSG_IF (!std::isfinite (start) || !std::isfinite (stop) ||
                   start < 0 || stop <= start || limit == 0,
                   "Invalid passive ACK service observation window");
  g_tranche9ServiceStart = start;
  g_tranche9ServiceStop = stop;
  g_tranche9ServiceLimit = limit;
  g_tranche9ServiceStream.open (path, std::ios::out | std::ios::trunc);
  NS_ABORT_MSG_IF (!g_tranche9ServiceStream.is_open (),
                   "Cannot open passive ACK service observer");
  g_tranche9ServiceStream
    << "schema,event_index,time_s,event,node,peer,packet_type,src,dst,sequence,"
       "success,reason,reservation_slot,reservation_counter,detail,packet_uid,"
       "prior_packet_uid,decision_id,prior_decision_id,mac_state,preparation_active,"
       "holdoff_over,sync_present,ack_queue,data_queue,tx_in_progress,rate_kbps,"
       "size_bytes,rx_power_dbm,pathloss_db,snr_db,jsr_db,header_errors,payload_errors,"
       "total_errors,statistic,value\n";
}

using Tranche9ExtraFields = std::array<std::string, 11>;

inline void
Tranche9WriteService (const CsrDifferentialTraceEvent &event,
                      const Tranche9ExtraFields &extra = {})
{
  if (!Tranche9ServiceActive ()) return;
  NS_ABORT_MSG_IF (g_tranche9ServiceIndex >= g_tranche9ServiceLimit,
                   "Passive ACK service observer record limit exceeded");
  const std::string fields[] = {
    "csr-ns3-ack-service-v1", CsrTraceInteger (++g_tranche9ServiceIndex),
    CsrTraceDouble (Simulator::Now ().GetSeconds ()), event.event, event.node,
    event.peer, event.packetType, event.source, event.destination, event.sequence,
    event.success, event.reason, event.reservationSlot, event.reservationCounter,
    event.detail, extra[0], extra[1], extra[2], extra[3], extra[4], extra[5],
    extra[6], extra[7], extra[8], extra[9], extra[10], event.rateKbps,
    event.sizeBytes, event.rxPowerDbm, event.pathlossDb, event.snrDb, event.jsrDb,
    event.headerErrors, event.payloadErrors, event.totalErrors, event.statistic,
    event.value
  };
  for (std::size_t index = 0; index < sizeof (fields)/sizeof (fields[0]); ++index)
    {
      if (index) g_tranche9ServiceStream << ',';
      g_tranche9ServiceStream << CsrTraceCsvEscape (fields[index]);
    }
  g_tranche9ServiceStream << '\n';
}

inline void
Tranche9ObserveDifferential (const CsrDifferentialTraceEvent &event)
{
  Tranche9WriteService (event);
}

inline void
Tranche9MacSnapshot (const char *stage, uint32_t node, uint32_t peer,
                     const char *state, bool preparing, bool holdoff, bool sync,
                     uint64_t acks, uint64_t data, bool transmitting,
                     int64_t slot, int64_t counter,
                     Ptr<const Packet> frame = nullptr,
                     Ptr<const Packet> prior = nullptr,
                     const std::string &detail = "")
{
  if (!Tranche9ServiceActive ()) return;
  CsrDifferentialTraceEvent event;
  event.event = stage;
  event.node = CsrTraceInteger (node);
  event.peer = CsrTraceInteger (peer);
  event.reservationSlot = CsrTraceSignedInteger (slot);
  event.reservationCounter = CsrTraceSignedInteger (counter);
  event.detail = detail;
  Tranche9ExtraFields extra;
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
          event.packetType = header.IsAck () ? "ack" : header.IsDack () ? "dack" : "other";
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
  Tranche9WriteService (event, extra);
}

inline void
Tranche9CloseServiceCsv ()
{
  if (!g_tranche9ServiceStream.is_open ()) return;
  g_tranche9ServiceStream.flush ();
  NS_ABORT_MSG_IF (!g_tranche9ServiceStream.good (),
                   "Passive ACK service observer flush failed");
  g_tranche9ServiceStream.close ();
}

} // namespace ns3
