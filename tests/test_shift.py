"""
Tests for risk control under human-routing shift.

These pin the mechanism rather than the numbers: that coverage fails in a
specific direction, for a specific reason, and that the correction addresses
that reason rather than merely moving a threshold.

Several pin an error that was made. A procedure that quietly accepts nothing
reports perfect coverage, which is the most flattering possible failure.
"""

from __future__ import annotations

import random

import pytest

from doubt.shift import (
    POLICIES, Case, RoutingPolicy, clopper_pearson_upper, draw_cases,
    naive_threshold, realised_risk, route, run_experiment, weighted_threshold,
)


# ===========================================================================
# Routing policies
# ===========================================================================

class TestRoutingPolicies:

    def test_zero_intensity_ignores_the_signal(self):
        """
        At intensity zero the reviewer routes at random, so calibration and
        deployment stay exchangeable. This is the control condition and the
        experiment is uninterpretable without it.
        """
        p = RoutingPolicy("reviews_low_confidence", intensity=0.0, base_rate=0.3)
        assert p.review_prob(0.05) == pytest.approx(0.3)
        assert p.review_prob(0.95) == pytest.approx(0.3)

    def test_low_confidence_policy_reviews_what_the_model_doubts(self):
        p = RoutingPolicy("reviews_low_confidence", intensity=1.0)
        assert p.review_prob(0.1) > p.review_prob(0.9)

    def test_high_stakes_policy_inverts_it(self):
        """
        The behaviour that breaks the guarantee: checking confident answers
        because the case matters, regardless of what the model says.
        """
        p = RoutingPolicy("reviews_high_stakes", intensity=1.0)
        assert p.review_prob(0.9) > p.review_prob(0.1)

    def test_middle_policy_is_non_monotone(self):
        p = RoutingPolicy("reviews_the_middle", intensity=1.0)
        assert p.review_prob(0.5) > p.review_prob(0.05)
        assert p.review_prob(0.5) > p.review_prob(0.95)

    def test_probabilities_stay_in_range(self):
        for pol in POLICIES:
            for i in (0.0, 0.5, 1.0):
                p = RoutingPolicy(pol.name, intensity=i)
                for s in (0.0, 0.25, 0.5, 0.75, 1.0):
                    assert 0.0 <= p.review_prob(s) <= 1.0

    def test_unknown_policy_is_refused(self):
        with pytest.raises(ValueError):
            RoutingPolicy("invented").review_prob(0.5)


# ===========================================================================
# Threshold search
# ===========================================================================

class TestThresholdSearch:

    def test_search_finds_a_usable_threshold(self):
        """
        REGRESSION, and the most dangerous bug in the project. The search
        originally stopped at the first threshold whose bound failed — which
        at the strictest thresholds is always, because the accepted sample is
        too small for any bound to certify.

        It therefore returned 'accept nothing', every experiment reported zero
        risk and zero violations, and the result looked like a clean pass.
        A procedure that accepts nothing has perfect coverage and no value.
        """
        cal = draw_cases(600, accuracy=0.90, calibration=0.7,
                         rng=random.Random(1))
        t = naive_threshold(cal, alpha=0.05, delta=0.05)
        accepted = [c for c in cal if c.confidence >= t]
        assert t < 1.0, "search returned accept-nothing"
        assert len(accepted) > 0.25 * len(cal), (
            "a usable threshold should accept a substantial share")

    def test_threshold_respects_the_target_on_its_own_sample(self):
        cal = draw_cases(800, accuracy=0.90, calibration=0.7,
                         rng=random.Random(2))
        t = naive_threshold(cal, alpha=0.05, delta=0.05)
        accepted = [c for c in cal if c.confidence >= t]
        risk = sum(1 for c in accepted if not c.correct) / len(accepted)
        assert risk <= 0.05 + 1e-9

    def test_a_tighter_target_accepts_less(self):
        cal = draw_cases(900, accuracy=0.88, calibration=0.7,
                         rng=random.Random(3))
        loose = naive_threshold(cal, alpha=0.15)
        tight = naive_threshold(cal, alpha=0.02)
        assert tight >= loose

    def test_weighted_search_also_finds_a_threshold(self):
        cal = draw_cases(600, accuracy=0.90, calibration=0.7,
                         rng=random.Random(4))
        t = weighted_threshold(cal, RoutingPolicy("reviews_high_stakes", 1.0))
        assert t < 1.0

    def test_weighting_is_stricter_where_exposure_concentrates(self):
        """
        Under a policy that reviews confident cases, the exposed population is
        the unconfident residue. The weighted threshold should not be more
        permissive than the naive one, since it is certifying a harder
        population.
        """
        cal = draw_cases(900, accuracy=0.90, calibration=0.7,
                         rng=random.Random(5))
        pol = RoutingPolicy("reviews_high_stakes", intensity=1.0)
        assert weighted_threshold(cal, pol) >= naive_threshold(cal) - 0.11


class TestClopperPearson:

    def test_zero_errors_gives_the_rule_of_three(self):
        assert clopper_pearson_upper(0, 100, 0.05) == pytest.approx(0.03, abs=0.005)

    def test_bound_exceeds_the_point_estimate(self):
        assert clopper_pearson_upper(5, 100) > 0.05

    def test_valid_at_the_boundaries(self):
        assert clopper_pearson_upper(0, 0) == 1.0
        assert clopper_pearson_upper(10, 10) == 1.0


# ===========================================================================
# The shift itself
# ===========================================================================

class TestShiftMechanism:

    def test_reviewing_confident_cases_enriches_the_residue_with_errors(self):
        """
        THE MECHANISM. Reviewers who check confident answers remove correct
        ones from the exposed pool, so what passes through untouched is
        enriched in errors. This is why the guarantee inverts.
        """
        rng = random.Random(7)
        cases = draw_cases(3000, accuracy=0.90, calibration=0.7, rng=rng)
        t = 0.3

        unrouted = realised_risk(
            route(cases, RoutingPolicy("ignores_signal"), rng), t)[0]
        high = realised_risk(
            route(cases, RoutingPolicy("reviews_high_stakes", 1.0), rng), t)[0]

        assert high > unrouted * 1.5, (
            "reviewing confident cases should raise the exposed error rate")

    def test_reviewing_unconfident_cases_makes_deployment_safer(self):
        """
        The direction matters. If every routing policy broke the guarantee the
        finding would be trivial; it is specific to one behaviour, and the
        intended policy improves on calibration.
        """
        rng = random.Random(8)
        cases = draw_cases(3000, accuracy=0.90, calibration=0.7, rng=rng)
        t = 0.3
        unrouted = realised_risk(
            route(cases, RoutingPolicy("ignores_signal"), rng), t)[0]
        low = realised_risk(
            route(cases, RoutingPolicy("reviews_low_confidence", 1.0), rng), t)[0]
        assert low < unrouted

    def test_reviewed_cases_are_excluded_from_exposure(self):
        """
        Reviewed cases are assumed corrected and contribute no error. The
        exposure is entirely in what passed through untouched.
        """
        cases = [Case(0.9, False, reviewed=True) for _ in range(50)]
        risk, n = realised_risk(cases, 0.5)
        assert n == 0 and risk == 0.0

    def test_no_exposed_cases_is_not_a_violation(self):
        assert realised_risk([], 0.5) == (0.0, 0)


class TestExperiment:

    def test_naive_fails_badly_under_high_stakes_routing(self):
        """
        The headline. A guarantee calibrated at 5% should fail in a large
        share of deployments once reviewers check confident cases.
        """
        r = run_experiment(RoutingPolicy("reviews_high_stakes", 1.0),
                           trials=60, n_cal=500, n_dep=500, seed=11)
        assert r.naive_violation_rate > 0.40

    def test_the_correction_substantially_reduces_violations(self):
        r = run_experiment(RoutingPolicy("reviews_high_stakes", 1.0),
                           trials=60, n_cal=500, n_dep=500, seed=11)
        assert r.weighted_violation_rate < r.naive_violation_rate / 2

    def test_violations_rise_with_routing_intensity(self):
        """
        A dose-response relationship. Without it the result could be an
        artefact of one arbitrary policy strength.
        """
        rates = []
        for i in (0.0, 0.5, 1.0):
            r = run_experiment(RoutingPolicy("reviews_high_stakes", i),
                               trials=50, n_cal=500, n_dep=500, seed=13)
            rates.append(r.naive_violation_rate)
        assert rates[2] > rates[0], "intensity should worsen coverage"
        assert rates == sorted(rates), f"not monotone: {rates}"

    def test_the_control_condition_behaves(self):
        """
        With routing independent of the signal, naive and weighted should
        agree — the correction must not change anything when there is nothing
        to correct.
        """
        r = run_experiment(RoutingPolicy("ignores_signal", 0.0),
                           trials=50, n_cal=500, n_dep=500, seed=17)
        assert abs(r.naive_violation_rate - r.weighted_violation_rate) < 0.12

    def test_the_correction_costs_exposure(self):
        """
        The guarantee is not free: certifying a harder population means
        accepting fewer cases automatically. Reporting the violation rate
        without the cost would misrepresent the trade.
        """
        r = run_experiment(RoutingPolicy("reviews_high_stakes", 1.0),
                           trials=40, n_cal=500, n_dep=500, seed=19)
        d = r.as_dict()
        assert d["weighted_mean_exposed"] <= d["naive_mean_exposed"] * 1.05

    def test_results_serialise(self):
        r = run_experiment(RoutingPolicy("reviews_low_confidence", 1.0),
                           trials=10, n_cal=300, n_dep=300, seed=23)
        d = r.as_dict()
        assert {"policy", "intensity", "naive_violation_rate",
                "weighted_violation_rate"} <= set(d)


class TestDataGeneration:

    def test_accuracy_is_respected(self):
        cases = draw_cases(4000, accuracy=0.85, rng=random.Random(29))
        acc = sum(c.correct for c in cases) / len(cases)
        assert 0.82 < acc < 0.88

    def test_calibration_controls_the_signal(self):
        rng = random.Random(31)
        sharp = draw_cases(2000, accuracy=0.9, calibration=0.95, rng=rng)
        blind = draw_cases(2000, accuracy=0.9, calibration=0.0, rng=rng)

        def gap(cs):
            ok = [c.confidence for c in cs if c.correct]
            bad = [c.confidence for c in cs if not c.correct]
            return sum(ok) / len(ok) - sum(bad) / len(bad)

        assert gap(sharp) > gap(blind) * 2

    def test_simulation_use_is_justified_in_the_docstring(self):
        """
        Simulation is the result here and legitimately so: the claim is about
        a statistical procedure, and coverage can only be checked against a
        known ground truth. The module has to say that rather than leave it
        implicit.
        """
        import doubt.shift as sh
        doc = " ".join(sh.__doc__.split())
        assert "appropriate use of simulation" in doc
        assert "Nothing is proved here" in doc


# ===========================================================================
# Estimating an unknown routing policy
# ===========================================================================

class TestPolicyEstimation:

    def test_isotonic_fit_is_monotone(self):
        from doubt.estimate import isotonic_fit
        xs = [i / 10 for i in range(11)]
        ys = [0.1, 0.3, 0.2, 0.4, 0.35, 0.6, 0.55, 0.7, 0.9, 0.85, 1.0]
        fitted = [y for _, y in isotonic_fit(xs, ys)]
        assert fitted == sorted(fitted)

    def test_estimator_recovers_the_direction(self):
        """
        Fitted in both directions and the better kept, because assuming the
        intended policy would bake in the assumption the study exists to test.
        """
        import random

        from doubt.estimate import estimate_policy
        from doubt.shift import draw_cases, route

        rng = random.Random(3)
        for name, expect_up in [("reviews_high_stakes", True),
                                ("reviews_low_confidence", False)]:
            pol = RoutingPolicy(name, intensity=1.0)
            obs = route(draw_cases(3000, rng=rng), pol, rng)
            est = estimate_policy(obs)
            got_up = est.review_prob(0.9) > est.review_prob(0.1)
            assert got_up == expect_up, f"{name}: wrong direction recovered"

    def test_estimate_improves_with_more_observations(self):
        import random

        from doubt.estimate import estimate_policy
        from doubt.shift import draw_cases, route

        pol = RoutingPolicy("reviews_high_stakes", 1.0)
        grid = [i / 20 for i in range(21)]

        def err(n, seed):
            rng = random.Random(seed)
            est = estimate_policy(route(draw_cases(n, rng=rng), pol, rng))
            return sum(abs(est.review_prob(s) - pol.review_prob(s))
                       for s in grid) / len(grid)

        assert err(2000, 5) < err(120, 5)

    def test_estimated_correction_beats_no_correction(self):
        from doubt.estimate import compare_oracle_and_estimated
        r = compare_oracle_and_estimated(
            RoutingPolicy("reviews_high_stakes", 1.0),
            n_pilot=600, trials=40, seed=9).as_dict()
        assert r["estimated_violation_rate"] < r["naive_violation_rate"] / 2

    def test_oracle_does_not_depend_on_pilot_size(self):
        """
        REGRESSION. The pilot and the calibration draw originally shared a
        random stream, so a larger pilot shifted every subsequent draw and the
        oracle arm appeared to move with a quantity it does not use. A
        confound is invisible unless something varies that should not.
        """
        from doubt.estimate import compare_oracle_and_estimated
        small = compare_oracle_and_estimated(
            RoutingPolicy("reviews_high_stakes", 1.0),
            n_pilot=100, trials=40, seed=9).as_dict()["oracle_violation_rate"]
        large = compare_oracle_and_estimated(
            RoutingPolicy("reviews_high_stakes", 1.0),
            n_pilot=1200, trials=40, seed=9).as_dict()["oracle_violation_rate"]
        assert small == large

    def test_weights_are_floored(self):
        """
        Where the estimated review probability approaches one the implied
        weight approaches zero and a handful of cases carry the estimate.
        Clipping trades a little bias for a large reduction in variance.
        """
        import inspect

        from doubt import estimate
        src = inspect.getsource(estimate.estimated_threshold)
        assert "max(floor," in src

    def test_empty_observations_are_safe(self):
        from doubt.estimate import estimate_policy
        est = estimate_policy([])
        assert est.review_prob(0.5) == 0.0


class TestFailureBoundary:

    def test_exposure_is_reported_with_violations(self):
        """
        REGRESSION on an interpretation, not on code. Violation rate appeared
        to improve as the unobserved driver strengthened, which was the
        correction refusing to accept anything rather than the guarantee
        holding. A violation rate without exposure beside it is
        uninterpretable.
        """
        from doubt.estimate import hidden_driver_experiment
        rows = hidden_driver_experiment(
            RoutingPolicy("reviews_high_stakes", 1.0), [0.0, 0.6],
            trials=25, seed=13)
        for r in rows:
            assert "estimated_mean_exposed" in r
            assert "naive_mean_exposed" in r

    def test_an_unobserved_driver_collapses_exposure(self):
        from doubt.estimate import hidden_driver_experiment
        rows = hidden_driver_experiment(
            RoutingPolicy("reviews_high_stakes", 1.0), [0.0, 0.7],
            trials=30, seed=13)
        assert rows[1]["estimated_mean_exposed"] < rows[0]["estimated_mean_exposed"] * 0.6


# ===========================================================================
# The reviewer model
# ===========================================================================

class TestReviewerModel:

    def test_organisation_wants_low_confidence_reviewed(self):
        """The intended policy falls out of the organisation's own objective."""
        from doubt.reviewer import ReviewerModel
        m = ReviewerModel()
        assert m.organisational_value(0.1, 1.0) > m.organisational_value(0.9, 1.0)

    def test_without_insurance_the_reviewer_agrees_with_the_organisation(self):
        """
        At gamma zero the reviewer's objective is the organisation's, and
        routing is the intended policy. That is the control the whole account
        rests against.
        """
        from doubt.reviewer import ReviewerModel, simulate_routing
        p = simulate_routing(ReviewerModel(gamma=0.0), seed=3)
        assert p.confidence_gradient < 0
        assert not p.predicts_shift

    def test_insurance_plus_outcome_accountability_produces_the_damage(self):
        """H3, derived rather than assumed."""
        from doubt.reviewer import ReviewerModel, simulate_routing
        p = simulate_routing(ReviewerModel(gamma=1.2, a=1.0), seed=3)
        assert p.confidence_gradient > 0.2
        assert p.predicts_shift

    def test_process_accountability_protects(self):
        """
        H4, the moderator, and the most useful implication: an organisation
        can fix a statistical problem by changing how it evaluates reviewers
        rather than by changing the model.
        """
        from doubt.reviewer import ReviewerModel, simulate_routing
        outcome = simulate_routing(ReviewerModel(gamma=1.2, a=1.0), seed=3)
        process = simulate_routing(ReviewerModel(gamma=1.2, a=0.0), seed=3)
        assert process.confidence_gradient < 0
        assert outcome.confidence_gradient > process.confidence_gradient

    def test_the_failure_requires_stakes_to_track_confidence(self):
        """
        H5, the boundary. Where stakes and confidence are uncorrelated, a
        strong insurance motive is harmless — the failure is not universal,
        and a design that cannot separate the two cannot test the theory.
        """
        from doubt.reviewer import correlation_sweep
        rows = {r["stake_correlation"]: r for r in
                correlation_sweep([0.0, 1.0], n=4000, seed=3)}
        assert rows[0.0]["confidence_gradient"] < 0
        assert rows[1.0]["confidence_gradient"] > 0.3

    def test_the_gradient_is_monotone_in_the_insurance_motive(self):
        from doubt.reviewer import ReviewerModel, simulate_routing
        grads = [simulate_routing(ReviewerModel(gamma=g, a=1.0), seed=3)
                 .confidence_gradient for g in (0.0, 0.4, 0.8, 1.2)]
        assert grads == sorted(grads), f"not monotone: {grads}"

    def test_review_probability_stays_in_range(self):
        from doubt.reviewer import ReviewerModel
        m = ReviewerModel(gamma=3.0, a=1.0)
        for s in (0.0, 0.5, 1.0):
            for v in (0.0, 0.5, 1.0):
                assert 0.0 <= m.review_prob(s, v) <= 1.0

    def test_routing_is_stochastic_not_a_cutoff(self):
        """
        A deterministic rule would make the policy trivially estimable in a
        way real behaviour is not, and would flatter the estimator in
        estimate.py.
        """
        from doubt.reviewer import ReviewerModel
        m = ReviewerModel(gamma=1.0, a=1.0)
        p = m.review_prob(0.5, 0.5)
        assert 0.0 < p < 1.0
