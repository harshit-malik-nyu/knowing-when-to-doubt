"""
Correcting for a routing policy nobody wrote down.

`shift.py` corrects the risk estimate using the routing probability π(s). That
assumes π is known, which is true in the machine-feedback literature — an
acquisition function is designed and its form is available — and false here.
No reviewer has written down how they decide what to check.

This module estimates π from observed behaviour and asks the question that
decides whether the correction is usable in practice: **does it still work when
the weights are estimated rather than given?**

Why this is the load-bearing question
-------------------------------------
A correction that requires the true policy is a correction that requires the
thing the setting does not provide. If estimation error destroys coverage, the
method is a machine-feedback method wearing a human-feedback label. If coverage
survives estimation, the contribution is real.

The estimator is deliberately simple — isotonic regression of review indicator
on confidence, which imposes monotonicity where the policy is monotone and
nothing else. A flexible estimator would fit the sample better and generalise
worse, and the point is not to model reviewers well but to establish how much
estimation error the guarantee tolerates.

What breaks it, stated up front
-------------------------------
The estimator assumes routing depends on confidence alone. Real reviewers route
on case value, client, time of day and workload. Where routing depends on
something correlated with correctness but NOT captured by confidence, the
weights are wrong in a direction no amount of data fixes — an omitted-variable
problem, not a sample-size problem.

That limitation is measured below rather than asserted, by introducing a hidden
routing driver and watching coverage degrade.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .shift import (
    Case, RoutingPolicy, clopper_pearson_upper, draw_cases, realised_risk,
)


# ---------------------------------------------------------------------------
# Estimating the policy
# ---------------------------------------------------------------------------

def isotonic_fit(xs: list[float], ys: list[float]) -> list[tuple[float, float]]:
    """
    Pool-adjacent-violators, returning (x, fitted) pairs.

    Monotone regression is the right shape for a routing rule that is
    monotone, and it imposes nothing else. Fitting a logistic curve would
    assume a functional form the reviewer never agreed to.
    """
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    sx = [xs[i] for i in order]
    sy = [ys[i] for i in order]

    # blocks of (sum, count)
    blocks: list[list[float]] = []
    for v in sy:
        blocks.append([v, 1.0])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c

    fitted: list[float] = []
    for s, c in blocks:
        fitted.extend([s / c] * int(c))
    return list(zip(sx, fitted))


@dataclass
class EstimatedPolicy:
    """A routing rule recovered from what reviewers actually did."""

    knots: list[tuple[float, float]] = field(default_factory=list)
    n_observed: int = 0
    monotone_increasing: bool = True

    def review_prob(self, confidence: float) -> float:
        """Interpolate the fitted curve; clamp outside the observed range."""
        if not self.knots:
            return 0.0
        if confidence <= self.knots[0][0]:
            return self.knots[0][1]
        if confidence >= self.knots[-1][0]:
            return self.knots[-1][1]
        lo, hi = 0, len(self.knots) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self.knots[mid][0] <= confidence:
                lo = mid
            else:
                hi = mid
        x0, y0 = self.knots[lo]
        x1, y1 = self.knots[hi]
        if x1 == x0:
            return y0
        t = (confidence - x0) / (x1 - x0)
        return min(1.0, max(0.0, y0 + t * (y1 - y0)))


def estimate_policy(observed: list[Case], bins: int = 40) -> EstimatedPolicy:
    """
    Recover π(s) from cases where routing was observed.

    Fitted in both directions and the better-fitting one kept, because a
    reviewer may route toward low confidence or toward high confidence and
    assuming the intended direction would bake in the assumption the study
    exists to test.
    """
    if not observed:
        return EstimatedPolicy()

    # Bin first: isotonic on raw binary outcomes is a step function that
    # interpolates badly, and the binned version is what a practitioner would
    # compute anyway.
    buckets: dict[int, list[int]] = {}
    for c in observed:
        b = min(bins - 1, int(c.confidence * bins))
        buckets.setdefault(b, []).append(1 if c.reviewed else 0)

    xs = [(b + 0.5) / bins for b in sorted(buckets)]
    ys = [sum(v) / len(v) for _, v in sorted(buckets.items())]
    if len(xs) < 2:
        rate = ys[0] if ys else 0.0
        return EstimatedPolicy([(0.0, rate), (1.0, rate)], len(observed))

    up = isotonic_fit(xs, ys)
    down = [(x, y) for x, y in zip(xs, reversed([y for _, y in isotonic_fit(
        [1 - x for x in xs][::-1], ys[::-1])]))]

    def sse(fit):
        return sum((f - y) ** 2 for (_, f), y in zip(fit, ys))

    best = up if sse(up) <= sse(down) else down
    return EstimatedPolicy(knots=best, n_observed=len(observed),
                           monotone_increasing=(best is up))


# ---------------------------------------------------------------------------
# The correction, with estimated weights
# ---------------------------------------------------------------------------

def estimated_threshold(calibration: list[Case], policy: EstimatedPolicy,
                        alpha: float = 0.05, delta: float = 0.05,
                        grid: int = 100, floor: float = 0.02) -> float:
    """
    Risk-controlled threshold using estimated routing weights.

    `floor` bounds the weight away from zero. Where the estimated review
    probability approaches one, the implied weight approaches zero and a
    handful of cases carry the entire estimate — the classic instability of
    inverse-probability weighting. Clipping trades a little bias for a large
    reduction in variance, and without it a single extreme weight can flip the
    certified threshold.
    """
    best = 1.0 + 1e-9
    for lam in sorted((i / grid for i in range(grid + 1)), reverse=True):
        accepted = [c for c in calibration if c.confidence >= lam]
        if not accepted:
            continue

        weights = [max(floor, 1.0 - policy.review_prob(c.confidence))
                   for c in accepted]
        total = sum(weights)
        if total <= 0:
            continue
        n_eff = (total ** 2) / sum(w * w for w in weights)
        err_w = sum(w for w, c in zip(weights, accepted) if not c.correct)
        k_eff = int(round(err_w / total * n_eff))

        if clopper_pearson_upper(k_eff, max(1, int(round(n_eff))), delta) <= alpha:
            best = lam
        elif best < 1.0:
            break
    return best


# ---------------------------------------------------------------------------
# Does estimation cost coverage?
# ---------------------------------------------------------------------------

@dataclass
class EstimationResult:
    policy: str
    n_pilot: int
    trials: int
    alpha: float

    oracle_violations: int = 0
    estimated_violations: int = 0
    naive_violations: int = 0
    mean_policy_error: float = 0.0

    def rate(self, k: int) -> float:
        return k / self.trials if self.trials else 0.0

    def as_dict(self) -> dict:
        return {
            "policy": self.policy, "n_pilot": self.n_pilot,
            "trials": self.trials, "alpha": self.alpha,
            "naive_violation_rate": self.rate(self.naive_violations),
            "oracle_violation_rate": self.rate(self.oracle_violations),
            "estimated_violation_rate": self.rate(self.estimated_violations),
            "mean_absolute_policy_error": self.mean_policy_error,
        }


def compare_oracle_and_estimated(
    policy: RoutingPolicy, *, n_pilot: int = 400, alpha: float = 0.05,
    delta: float = 0.05, n_cal: int = 700, n_dep: int = 700,
    trials: int = 150, accuracy: float = 0.90, calibration: float = 0.7,
    seed: int = 0,
) -> EstimationResult:
    """
    Three thresholds on identical data: uncorrected, corrected with the true
    policy, corrected with a policy estimated from a pilot.

    The oracle arm is the ceiling. The gap between oracle and estimated is the
    price of not knowing the rule, and it is the number that decides whether
    this method survives contact with a real deployment.
    """
    from .shift import naive_threshold, route, weighted_threshold

    # Independent streams for the pilot and for calibration/deployment.
    #
    # A single stream made the oracle arm move with pilot size — 15%, 14%, 24%
    # across n=150, 400, 1000 — even though the oracle never sees the pilot.
    # Drawing a larger pilot consumes more of the stream and shifts every
    # subsequent draw, so the arms were not being compared on the same data.
    # The confound is invisible unless you notice a quantity varying with an
    # input it does not depend on.
    rng_pilot = random.Random(seed * 7919 + 1)
    rng_main = random.Random(seed)
    res = EstimationResult(policy=policy.name, n_pilot=n_pilot,
                           trials=trials, alpha=alpha)
    errors = []

    for _ in range(trials):
        pilot = route(draw_cases(n_pilot, accuracy=accuracy,
                                 calibration=calibration, rng=rng_pilot),
                      policy, rng_pilot)
        est = estimate_policy(pilot)

        grid = [i / 20 for i in range(21)]
        errors.append(sum(abs(est.review_prob(s) - policy.review_prob(s))
                          for s in grid) / len(grid))

        cal = draw_cases(n_cal, accuracy=accuracy, calibration=calibration,
                         rng=rng_main)
        dep = route(draw_cases(n_dep, accuracy=accuracy,
                               calibration=calibration, rng=rng_main),
                    policy, rng_main)

        for thr, bump in (
            (naive_threshold(cal, alpha, delta), "naive"),
            (weighted_threshold(cal, policy, alpha, delta), "oracle"),
            (estimated_threshold(cal, est, alpha, delta), "estimated"),
        ):
            risk, _ = realised_risk(dep, thr)
            if risk > alpha:
                if bump == "naive":
                    res.naive_violations += 1
                elif bump == "oracle":
                    res.oracle_violations += 1
                else:
                    res.estimated_violations += 1

    res.mean_policy_error = sum(errors) / len(errors) if errors else 0.0
    return res


# ---------------------------------------------------------------------------
# The limitation, measured
# ---------------------------------------------------------------------------

def route_with_hidden_driver(cases: list[Case], policy: RoutingPolicy,
                             hidden_strength: float,
                             rng: random.Random) -> list[Case]:
    """
    Routing that depends partly on something confidence does not capture.

    Real reviewers route on case value, client, and workload. Where that
    driver correlates with correctness but is invisible to the estimator, the
    weights are wrong in a way more data cannot fix. This is an
    omitted-variable problem, not a sample-size problem, and the experiment
    below measures how fast it bites.
    """
    out = []
    for c in cases:
        # The hidden driver is correlated with correctness, which is exactly
        # the case that breaks confidence-only weighting.
        hidden = 1.0 if c.correct else 0.0
        p = ((1 - hidden_strength) * policy.review_prob(c.confidence)
             + hidden_strength * hidden)
        out.append(Case(c.confidence, c.correct,
                        reviewed=rng.random() < min(1.0, max(0.0, p))))
    return out


def hidden_driver_experiment(policy: RoutingPolicy, strengths: list[float],
                             *, alpha: float = 0.05, delta: float = 0.05,
                             n_pilot: int = 400, n_cal: int = 700,
                             n_dep: int = 700, trials: int = 120,
                             seed: int = 0) -> list[dict]:
    """How quickly does an unobserved routing driver defeat the correction?"""
    from .shift import naive_threshold

    rng = random.Random(seed)
    rows = []
    for strength in strengths:
        naive_v = est_v = 0
        naive_exp, est_exp = [], []
        for _ in range(trials):
            pilot = route_with_hidden_driver(
                draw_cases(n_pilot, rng=rng), policy, strength, rng)
            est = estimate_policy(pilot)

            cal = draw_cases(n_cal, rng=rng)
            dep = route_with_hidden_driver(
                draw_cases(n_dep, rng=rng), policy, strength, rng)

            rn, nn = realised_risk(dep, naive_threshold(cal, alpha, delta))
            naive_exp.append(nn)
            if rn > alpha:
                naive_v += 1

            re_, ne = realised_risk(dep, estimated_threshold(cal, est, alpha, delta))
            est_exp.append(ne)
            if re_ > alpha:
                est_v += 1

        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        rows.append({
            "hidden_strength": strength,
            "naive_violation_rate": naive_v / trials,
            "estimated_violation_rate": est_v / trials,
            # Exposure is reported alongside, because a violation rate read
            # without it is uninterpretable: a threshold that auto-accepts
            # almost nothing has an excellent violation rate and no value.
            # That failure mode already appeared once in this project and it
            # reappears here disguised as the correction improving.
            "naive_mean_exposed": mean(naive_exp),
            "estimated_mean_exposed": mean(est_exp),
        })
    return rows
