import pandas as pd
from analytics.scoring.risk_scoring import score_cases, zone_scores
from analytics.scoring.scheduling import recommend_dispatch


def candidates():
    return pd.DataFrame([
        {"case_id":"Z1-L1", "zone_id":"Z1", "location_id":"L1", "meter_id":"M1", "anomaly_type":"SUSTAINED_INCREASE", "persistent_night_flow":True,
         "recent_independent_complaints":5, "elevated_recent_days":5, "access_status":"REPORTED_RESTRICTION"},
        {"case_id":"Z2-L2", "zone_id":"Z2", "location_id":"L2", "meter_id":"M2", "anomaly_type":"SUSTAINED_INCREASE", "persistent_night_flow":False,
         "recent_independent_complaints":2, "elevated_recent_days":3, "access_status":"UNVERIFIED"},
        {"case_id":"Z2-L3", "zone_id":"Z2", "location_id":"L3", "meter_id":"M3", "anomaly_type":"TEMPORARY_SPIKE", "persistent_night_flow":False,
         "recent_independent_complaints":2, "elevated_recent_days":1, "access_status":"UNVERIFIED"},
    ])


def crews():
    return pd.DataFrame([{"crew_id":"C1", "availability_status":"Available"},
                         {"crew_id":"C2", "availability_status":"Assigned"}])


def test_risk_components_sum_and_no_spike_credit():
    s = score_cases(candidates())
    assert s.iloc[0].risk_score == 100
    assert s.set_index("case_id").loc["Z2-L3", "consumption_points"] == 0
    assert (s.risk_score.between(0,100)).all()
    assert len(zone_scores(s)) == 2


def test_blocked_highest_does_not_consume_crew():
    s = score_cases(candidates())
    overrides = pd.DataFrame([
        {"case_id":"Z1-L1", "access_status":"BLOCKED", "access_note":"Closure"},
        {"case_id":"Z2-L2", "access_status":"OPEN", "access_note":"Verified"}
    ])
    out, available = recommend_dispatch(s, crews(), overrides)
    rows = out.set_index("case_id")
    assert rows.loc["Z1-L1", "risk_rank"] == 1
    assert rows.loc["Z1-L1", "dispatch_decision"] == "DEFER_BLOCKED"
    assert rows.loc["Z2-L2", "dispatch_decision"] == "PROPOSE_ASSIGN"
    assert rows.loc["Z2-L2", "suggested_crew_id"] == "C1"
    assert len(available) == 1


def test_unverified_access_cannot_be_auto_assigned():
    out, _ = recommend_dispatch(score_cases(candidates()), crews())
    assert not out.dispatch_decision.eq("PROPOSE_ASSIGN").any()


def test_no_mutation_of_crew_status():
    c = crews()
    recommend_dispatch(score_cases(candidates()), c)
    assert c.loc[0,"availability_status"] == "Available"
