"""
Every headline number in the README must regenerate from the code.

Six modules were built in sequence, each producing figures that went straight
into the README. Nothing stops a later change from silently invalidating an
earlier claim — a module edit moves a number, the document keeps the old one,
and the repository quietly starts lying.

These tests recompute the load-bearing figures and assert the document still
matches. They are deliberately tolerant on the last digit (Monte Carlo runs
vary with trial count) and strict on the claim: if a finding reverses, a test
fails.

What is NOT checked here: numbers that appear only in prose as illustration.
The test set covers the figures a reader would quote, because those are the
ones that must not go stale.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def readme() -> str:
    return (ROOT / "README.md").read_text()


def prereg() -> str:
    return (ROOT / "docs" / "preregistration.md").read_text()


def cited(text: str, value: float, tolerance: float = 0.02) -> bool:
    """Does the document cite a percentage within tolerance of this value?"""
    for m in re.finditer(r"([0-9]+\.?[0-9]*)%", text):
        if abs(float(m.group(1)) / 100 - value) <= tolerance:
            return True
    return False


# ===========================================================================

class TestShiftFiguresAreCurrent:

    def test_the_headline_failure_rate(self):
        """
        The claim the whole repository rests on: split conformal fails in
        about nine deployments out of ten under confidence-dependent routing.
        """
        from doubt.shift import RoutingPolicy, run_experiment
        r = run_experiment(RoutingPolicy("reviews_high_stakes", 1.0),
                           trials=80, n_cal=700, n_dep=700, seed=41)
        assert r.naive_violation_rate > 0.75, (
            f"README claims ~90%; measured {r.naive_violation_rate:.1%}")
        assert cited(readme(), r.naive_violation_rate, tolerance=0.15)

    def test_the_direction_claim_still_holds(self):
        """
        Reviewing what the model DOUBTS must remain safer than calibrated.
        If this reversed, the central asymmetry in the README would be wrong.
        """
        from doubt.shift import RoutingPolicy, run_experiment
        low = run_experiment(RoutingPolicy("reviews_low_confidence", 1.0),
                             trials=60, n_cal=600, n_dep=600, seed=5)
        high = run_experiment(RoutingPolicy("reviews_high_stakes", 1.0),
                              trials=60, n_cal=600, n_dep=600, seed=5)
        assert low.naive_violation_rate < 0.1
        assert high.naive_violation_rate > 0.6


class TestEstimationFiguresAreCurrent:

    def test_the_gap_to_oracle_closes_with_pilot_size(self):
        from doubt.estimate import compare_oracle_and_estimated
        from doubt.shift import RoutingPolicy
        pol = RoutingPolicy("reviews_high_stakes", 1.0)
        small = compare_oracle_and_estimated(pol, n_pilot=100, trials=50,
                                             seed=7).as_dict()
        large = compare_oracle_and_estimated(pol, n_pilot=1600, trials=50,
                                             seed=7).as_dict()
        gap_small = (small["estimated_violation_rate"]
                     - small["oracle_violation_rate"])
        gap_large = (large["estimated_violation_rate"]
                     - large["oracle_violation_rate"])
        assert gap_large < gap_small, "README claims the gap closes"

    def test_the_oracle_arm_is_still_flat(self):
        """
        The check that the arms are comparable at all. If this ever fails, a
        shared random stream has crept back in.
        """
        from doubt.estimate import compare_oracle_and_estimated
        from doubt.shift import RoutingPolicy
        pol = RoutingPolicy("reviews_high_stakes", 1.0)
        a = compare_oracle_and_estimated(pol, n_pilot=100, trials=30,
                                         seed=7).as_dict()
        b = compare_oracle_and_estimated(pol, n_pilot=1600, trials=30,
                                         seed=7).as_dict()
        assert a["oracle_violation_rate"] == b["oracle_violation_rate"]


class TestReviewerFiguresAreCurrent:

    def test_the_gradient_swing_the_theory_claims(self):
        """
        The README and the power section both rest on the model predicting a
        swing of roughly fifty points. Powering for fifteen is justified by
        this number.
        """
        from doubt.reviewer import ReviewerModel, simulate_routing
        process = simulate_routing(ReviewerModel(gamma=1.2, a=0.0), seed=3)
        outcome = simulate_routing(ReviewerModel(gamma=1.2, a=1.0), seed=3)
        swing = outcome.confidence_gradient - process.confidence_gradient
        assert swing > 0.40, (
            f"power section assumes a ~50pt swing; measured {swing:.1%}")

    def test_process_accountability_still_protects(self):
        from doubt.reviewer import ReviewerModel, simulate_routing
        assert simulate_routing(ReviewerModel(gamma=1.2, a=0.0),
                                seed=3).confidence_gradient < 0


class TestBridgeFiguresAreCurrent:

    def test_the_uncomfortable_result_still_holds(self):
        """
        Process-based accountability keeps its guarantee AND produces more
        total errors. If this reversed, the README's central managerial
        caution would be wrong in the flattering direction.
        """
        from doubt.bridge import compare_interventions, cost_of_accountability
        c = cost_of_accountability(compare_interventions(trials=35, seed=17))
        proc, outc = c["process_based"], c["outcome_based"]
        assert proc["guarantee_violation_rate"] < outc["guarantee_violation_rate"]
        assert proc["errors_reaching_production"] > outc["errors_reaching_production"]

    def test_the_manual_review_load_claim(self):
        from doubt.bridge import compare_interventions, cost_of_accountability
        c = cost_of_accountability(compare_interventions(trials=35, seed=17))
        manual = c["outcome_based"]["decisions_reviewed_manually"]
        assert manual > 700_000, (
            f"README claims ~832,000 manual reviews; measured {manual:,.0f}")


class TestPowerFiguresAreCurrent:

    def test_the_corrected_power_figure(self):
        """
        The pre-registration states 11% power for the originally asserted
        design. If the calculation changes, the document must change with it.
        """
        from doubt.power import power_for
        r = power_for(reviewers=40, weeks=12, icc=0.05, effect_size=0.05)
        assert r.power < 0.20
        assert cited(prereg(), r.power, tolerance=0.05)

    def test_the_information_ceiling_claim(self):
        from doubt.power import information_ceiling
        assert information_ceiling(40, 0.05) == pytest.approx(800)
        assert "800" in prereg()

    def test_the_revised_reviewer_requirement(self):
        from doubt.power import reviewers_required
        n = reviewers_required(weeks=12, icc=0.05, effect_size=0.15)
        assert 40 <= n <= 90, f"pre-registration says 60+; computed {n}"
        assert "26 reviewers" in prereg()


class TestDriftFiguresAreCurrent:

    def test_unguarded_adaptation_still_loses(self):
        from doubt.drift import compare_procedures
        by = {r["procedure"]: r for r in
              compare_procedures(weeks=12, trials=12, seed=101)}
        assert by["adaptive"]["violation_rate"] > by["fixed"]["violation_rate"]

    def test_guarded_still_wins_on_both_columns(self):
        """
        Both columns, because winning on violations alone is the
        accept-nothing failure that has appeared three times here.
        """
        from doubt.drift import compare_procedures
        by = {r["procedure"]: r for r in
              compare_procedures(weeks=12, trials=12, seed=101)}
        assert by["guarded"]["violation_rate"] < by["fixed"]["violation_rate"]
        assert by["guarded"]["mean_exposed"] > by["fixed"]["mean_exposed"] * 0.7


class TestDocumentIntegrity:

    def test_every_internal_link_resolves(self):
        for name in ("README.md", "docs/preregistration.md", "docs/theory.md"):
            p = ROOT / name
            for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", p.read_text()):
                target = m.group(2).split("#")[0]
                if target.startswith(("http", "mailto:")) or not target:
                    continue
                assert (p.parent / target).resolve().exists(), (
                    f"{name} links to missing {target}")

    def test_theory_marks_what_is_not_proved(self):
        """
        Proposition 2 is prior work and Proposition 3 is conjectured. A theory
        document that blurs those is the easiest way to lose a referee.
        """
        t = (ROOT / "docs" / "theory.md").read_text()
        assert "This proposition is not new" in t
        assert "Status: conjectured, not proved" in t
        assert "Tibshirani" in t

    def test_the_simulation_disclaimer_survives(self):
        import doubt.shift as sh
        doc = " ".join(sh.__doc__.split())
        assert "Nothing is proved here" in doc

    def test_exposure_is_reported_wherever_violations_are(self):
        """
        The discipline that caught the accept-nothing failure all three times.
        Any results dict carrying a violation rate must carry exposure too.
        """
        from doubt.bridge import compare_interventions
        from doubt.drift import compare_procedures

        for row in compare_procedures(weeks=8, trials=6, seed=1):
            assert "mean_exposed" in row
        for row in compare_interventions(trials=6, seed=1):
            assert "uncorrected_exposed" in row
            assert "corrected_exposed" in row
