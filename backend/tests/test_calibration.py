"""lens calibration from outcomes: observed scores next to observed outcomes,
with the sample size always in the answer and no prediction claimed."""

from app.brain.calibration import calibrate


def _row(outcome, total, scores):
    return {
        "outcome": outcome,
        "weighted_total": total,
        "per_criterion": [{"criterion": n, "weight": w, "score": s} for n, w, s in scores],
    }


def _pair(outcome, total, depth, clarity):
    return _row(outcome, total, [("depth", 0.5, depth), ("clarity", 0.5, clarity)])


def test_no_outcomes_says_so():
    c = calibrate("l1", [])
    assert c.recorded == 0
    assert "no outcomes recorded" in c.reading
    assert c.criterion_gaps == []


def test_too_few_outcomes_says_so_and_names_the_counts():
    rows = [_pair("advanced", 4.0, 4, 4), _pair("rejected", 2.0, 2, 2)]
    c = calibrate("l1", rows, min_sample=3)
    assert c.recorded == 2
    assert "too few to say anything" in c.reading
    assert c.criterion_gaps == []  # no per-criterion claims below the gate
    # the group means are still shown: they are facts about the sample
    assert [g.targets for g in c.groups] == [1, 1]


def test_enough_outcomes_surfaces_the_separating_criterion():
    rows = [
        _pair("advanced", 4.4, 4.6, 4.2),
        _pair("advanced", 4.2, 4.4, 4.0),
        _pair("funded", 4.6, 4.8, 4.4),
        _pair("rejected", 2.4, 2.2, 2.6),
        _pair("rejected", 2.6, 2.0, 3.2),
        _pair("rejected", 2.2, 2.4, 2.0),
    ]
    c = calibrate("l1", rows, min_sample=3)
    assert c.recorded == 6
    assert "observed on this sample, not a prediction" in c.reading
    top = c.criterion_gaps[0]
    assert top.criterion in ("depth", "clarity")
    assert top.difference > 0
    assert "higher" in c.reading


def test_a_lens_that_separates_nothing_says_so():
    rows = [
        _pair("advanced", 3.0, 3.0, 3.0),
        _pair("advanced", 3.0, 3.0, 3.0),
        _pair("advanced", 3.0, 3.0, 3.0),
        _pair("rejected", 3.0, 3.0, 3.0),
        _pair("rejected", 3.0, 3.0, 3.0),
        _pair("rejected", 3.0, 3.0, 3.0),
    ]
    c = calibrate("l1", rows, min_sample=3)
    assert "scored both groups alike" in c.reading


def test_withdrawn_targets_do_not_count_as_rejections():
    """a withdrawal is not a verdict on the project, so it neither pads the
    rejected group nor gets a claim made about it."""
    rows = [_pair("withdrawn", 1.0, 1, 1), _pair("advanced", 4.0, 4, 4)]
    c = calibrate("l1", rows, min_sample=1)
    assert c.recorded == 2
    assert c.groups[1].targets == 0  # nothing in the rejected group
    assert c.criterion_gaps == []
