#pragma once
// Passive diagnostic side channel. No packet tags, RNG calls, policy writes,
// simulator events, or callbacks are added by this observer.
#include <iomanip>
#include <limits>
#include <map>

// Defined unchanged later by the pinned csr-phy-model.h. The observer uses the
// same physical rate conversion (an 8-kbit/s key is not exactly 8000 bit/s).
inline double CsrRateKeyToBps (int rateKbpsKey);

struct Tranche8FeedbackObservation
{
  uint64_t decisionId {0};
  uint64_t packetUid {0};
  bool peerKnown {false};
  double peerS0Dbm {std::numeric_limits<double>::quiet_NaN ()};
  double pathLossDb {std::numeric_limits<double>::quiet_NaN ()};
  double failures {std::numeric_limits<double>::quiet_NaN ()};
  int selectedRate {0};
  double selectedPower {std::numeric_limits<double>::quiet_NaN ()};
  double advertisedRxPower {std::numeric_limits<double>::quiet_NaN ()};
  int minRate {0};
  int maxRate {0};
  double minPower {std::numeric_limits<double>::quiet_NaN ()};
  double maxPower {std::numeric_limits<double>::quiet_NaN ()};
  double linkMargin {std::numeric_limits<double>::quiet_NaN ()};
  int incomingRate {0};
  double incomingPower {std::numeric_limits<double>::quiet_NaN ()};
};

static std::ofstream g_tranche8FeedbackStream;
static uint64_t g_tranche8DecisionId {0};
static std::map<uint64_t, Tranche8FeedbackObservation> g_tranche8FeedbackByUid;

static void
Tranche8OpenFeedbackCsv (const std::string &path)
{
  if (path.empty ())
    {
      return;
    }
  g_tranche8FeedbackStream.open (path, std::ios::out | std::ios::trunc);
  NS_ABORT_MSG_IF (!g_tranche8FeedbackStream.is_open (), "Cannot open passive feedback observer");
  g_tranche8FeedbackStream << std::setprecision (17)
    << "schema,stage,time_s,node_id,peer_id,frame_type,hop_sequence,decision_id,packet_uid,"
       "has_ack_window,ack_bitmap,dack_bitmap,selected_rate_key_kbps,selected_rate_bps,"
       "selected_power_dbm,advertised_rx_power_dbm,peer_known,peer_s0_dbm,path_loss_db,"
       "hop_failure_count,min_rate_key_kbps,max_rate_key_kbps,min_power_dbm,max_power_dbm,"
       "link_margin_db,incoming_rate_key_kbps,incoming_rate_bps,incoming_power_dbm,"
       "actual_rate_key_kbps,actual_rate_bps,actual_power_dbm,aggregate_id,segment_index,segment_count\n";
}

static void
Tranche8WriteNumber (double value)
{
  if (std::isfinite (value))
    {
      g_tranche8FeedbackStream << value;
    }
}

static void
Tranche8WriteFeedback (const char *stage,
                      const CsrHeader &header,
                      const Tranche8FeedbackObservation &observation,
                      int actualRate = 0,
                      double actualPower = std::numeric_limits<double>::quiet_NaN (),
                      uint64_t aggregateId = 0,
                      uint32_t segmentIndex = 0,
                      uint32_t segmentCount = 0)
{
  auto &stream = g_tranche8FeedbackStream;
  stream << "csr-ns3-feedback-observation-v1," << stage << ','
         << Simulator::Now ().GetSeconds () << ',' << header.GetSrc () << ','
         << header.GetDst () << ',' << (header.IsDack () ? "DACK" : "ACK") << ','
         << header.GetSeq () << ',' << observation.decisionId << ','
         << observation.packetUid << ',' << header.HasAckWindow () << ','
         << header.GetAckBitmap () << ',' << header.GetDackBitmap () << ','
         << observation.selectedRate << ',';
  if (observation.selectedRate > 0)
    {
      stream << CsrRateKeyToBps (observation.selectedRate);
    }
  stream << ','; Tranche8WriteNumber (observation.selectedPower);
  stream << ','; Tranche8WriteNumber (observation.advertisedRxPower);
  stream << ',' << observation.peerKnown << ',';
  Tranche8WriteNumber (observation.peerS0Dbm);
  stream << ','; Tranche8WriteNumber (observation.pathLossDb);
  stream << ','; Tranche8WriteNumber (observation.failures);
  stream << ',' << observation.minRate << ',' << observation.maxRate << ',';
  Tranche8WriteNumber (observation.minPower);
  stream << ','; Tranche8WriteNumber (observation.maxPower);
  stream << ','; Tranche8WriteNumber (observation.linkMargin);
  stream << ',';
  if (observation.incomingRate > 0)
    {
      stream << observation.incomingRate;
    }
  stream << ',';
  if (observation.incomingRate > 0)
    {
      stream << CsrRateKeyToBps (observation.incomingRate);
    }
  stream << ','; Tranche8WriteNumber (observation.incomingPower);
  stream << ',';
  if (actualRate > 0)
    {
      stream << actualRate;
    }
  stream << ',';
  if (actualRate > 0)
    {
      stream << CsrRateKeyToBps (actualRate);
    }
  stream << ','; Tranche8WriteNumber (actualPower);
  stream << ',';
  if (aggregateId > 0)
    {
      stream << aggregateId;
    }
  stream << ',';
  if (segmentCount > 0)
    {
      stream << segmentIndex;
    }
  stream << ',';
  if (segmentCount > 0)
    {
      stream << segmentCount;
    }
  stream << '\n';
  NS_ABORT_MSG_IF (!stream.good (), "Passive feedback observer write failed");
}

static void
Tranche8ObserveFeedbackSelection (Ptr<const Packet> frame,
                                  const CsrHeader &header,
                                  bool peerKnown,
                                  double peerS0,
                                  double pathLoss,
                                  double failures,
                                  int minRate,
                                  int maxRate,
                                  double minPower,
                                  double maxPower,
                                  double linkMargin)
{
  if (!g_tranche8FeedbackStream.is_open ())
    {
      return;
    }
  Tranche8FeedbackObservation observation;
  observation.decisionId = ++g_tranche8DecisionId;
  observation.packetUid = frame->GetUid ();
  observation.peerKnown = peerKnown;
  observation.peerS0Dbm = peerS0;
  observation.pathLossDb = pathLoss;
  observation.failures = failures;
  observation.selectedRate = header.GetSpeedKey ();
  observation.selectedPower = header.GetTxPowerDbm ();
  observation.advertisedRxPower = header.GetRxPowerDbm ();
  observation.minRate = minRate;
  observation.maxRate = maxRate;
  observation.minPower = minPower;
  observation.maxPower = maxPower;
  observation.linkMargin = linkMargin;
  g_tranche8FeedbackByUid[observation.packetUid] = observation;
  Tranche8WriteFeedback ("feedback_selection", header, observation);
}

static void
Tranche8ObserveFeedbackContext (Ptr<const Packet> frame, const CsrHeader &incoming)
{
  if (!g_tranche8FeedbackStream.is_open ())
    {
      return;
    }
  auto found = g_tranche8FeedbackByUid.find (frame->GetUid ());
  NS_ABORT_MSG_IF (found == g_tranche8FeedbackByUid.end (), "Missing constructed feedback observation");
  found->second.incomingRate = incoming.GetSpeedKey ();
  found->second.incomingPower = incoming.HasLinkControl ()
    ? incoming.GetTxPowerDbm ()
    : std::numeric_limits<double>::quiet_NaN ();
  CsrHeader header;
  frame->PeekHeader (header);
  Tranche8WriteFeedback ("ack_response_context", header, found->second);
}

static void
Tranche8ObserveFeedbackTransmission (const std::vector<Ptr<Packet>> &frames,
                                    int actualRate,
                                    double actualPower,
                                    uint64_t aggregateId)
{
  if (!g_tranche8FeedbackStream.is_open ())
    {
      return;
    }
  for (uint32_t index = 0; index < frames.size (); ++index)
    {
      CsrHeader header;
      frames[index]->PeekHeader (header);
      if (!(header.IsAck () || header.IsDack ()))
        {
          continue;
        }
      auto found = g_tranche8FeedbackByUid.find (frames[index]->GetUid ());
      NS_ABORT_MSG_IF (found == g_tranche8FeedbackByUid.end (), "Missing feedback-to-OTA observation");
      Tranche8WriteFeedback ("ota_segment", header, found->second, actualRate, actualPower,
                            aggregateId, index + 1, frames.size ());
    }
}

static void
Tranche8CloseFeedbackCsv ()
{
  if (g_tranche8FeedbackStream.is_open ())
    {
      g_tranche8FeedbackStream.flush ();
      NS_ABORT_MSG_IF (!g_tranche8FeedbackStream.good (), "Passive feedback observer flush failed");
      g_tranche8FeedbackStream.close ();
    }
}
