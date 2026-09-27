"""
Risk control when humans route on the model's own confidence.

The setting
-----------
A model scores each case and reports a confidence. A human decides which cases
to review and which to let through, and that decision uses the confidence. The
cases that reach production untouched are therefore **selected on the same
signal the guarantee is calibrated against**.

Standard split conformal assumes the calibration sample and the deployment
sample are exchangeable. Here they are not, and the violation is caused by the
system's own deployment: showing a confidence score changes which cases the
guarantee has to cover.

Relation to Feedback Covariate Shift
------------------------------------
Feedback Covariate Shift is established. Fannjiang et al. (2022) introduced it
for design problems where the model's predictions determine what data is
collected next; Prinster et al. (2024) refined the theory and extended it to
multistep settings; Wang and Ning (NeurIPS 2025) apply feedback-based conformal
prediction to trajectory optimisation.

In all of that work the feedback loop runs through a **machine**: an
acquisition function, a controller, an optimiser. The selection rule is chosen
by the system designer and is therefore known exactly.

This module treats a different loop. The selection is made by a **person**
choosing what to review, acting on their own workload, incentives and
scepticism. Three consequences follow, and they are what make the human case
distinct rather than a special case of the machine one:

    the policy is unknown      Nobody wrote it down. It has to be estimated
                               from observed routing behaviour.

    the policy is unstable     Reviewers learn. A routing rule estimated in
                               month one is wrong by month three, in a
                               direction the deployment itself caused.

    the policy is the target   In the machine case the acquisition rule is a
                               nuisance. Here how people route IS the
                               behavioural quantity of interest, so it cannot
                               be designed away.

What is proved here
-------------------
Nothing is proved here. This module implements and measures: it shows split
conformal losing coverage as routing intensity rises, implements a weighted
correction, and reports the coverage each achieves under repeated sampling.
The theoretical statement belongs in the paper; the claim in this repository
is empirical and is validated by simulation, which is the appropriate use of
simulation for a question about a statistical procedure.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Routing policies
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoutingPolicy:
    """
    How a reviewer decides what to look at, as a function of displayed
    confidence.

    `intensity` scales how strongly the decision depends on confidence:
    at 0 the reviewer ignores the signal and routing is exchangeable with
    calibration; at 1 they follow it closely. The parameter exists to sweep
    the violation from absent to severe, because the interesting question is
    where coverage starts to fail rather than whether it eventually does.
    """

    name: str
    intensity: float = 1.0
    base_rate: float = 0.30
    """Share of cases reviewed when confidence is ignored."""

    def review_prob(self, confidence: float) -> float:
        """Probability this case is sent to a human."""
        if self.name == "ignores_signal":
            return self.base_rate

        if self.name == "reviews_low_confidence":
            # The intended behaviour: look at what the model is unsure about.
            p = 1.0 - confidence
        elif self.name == "reviews_high_stakes":
            # Reviewers often check confident answers on important cases,
            # inverting the intended policy.
            p = confidence
        elif self.name == "reviews_the_middle":
            # Extremes feel settled; the middle feels worth a look.
            p = 1.0 - 2.0 * abs(confidence - 0.5)
        else:
            raise ValueError(f"unknown policy: {self.name}")

        blended = (1 - self.intensity) * self.base_rate + self.intensity * p
        return min(1.0, max(0.0, blended))


POLICIES = [
    RoutingPolicy("ignores_signal"),
    RoutingPolicy("reviews_low_confidence"),
    RoutingPolicy("reviews_high_stakes"),
    RoutingPolicy("reviews_the_middle"),
]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    confidence: float
    correct: bool
    reviewed: bool = False


def draw_cases(n: int, *, accuracy: float = 0.90, calibration: float = 0.7,
               rng: random.Random | None = None) -> list[Case]:
    """
    Cases with a confidence signal of controllable quality.

    `calibration` governs how well confidence ranks errors: at 0 it is noise,
    at 1 every error is ranked below every correct answer. The shift result
    should hold across that range, and reporting it at several values is how
    that is checked rather than assumed.
    """
    rng = rng or random.Random(0)
    out = []
    for _ in range(n):
        correct = rng.random() < accuracy
        base = rng.random()
        conf = base * (1 - calibration) + calibration * (0.85 if correct else 0.15)
        out.append(Case(confidence=min(1.0, max(0.0, conf)), correct=correct))
    return out


def route(cases: list[Case], policy: RoutingPolicy,
          rng: random.Random | None = None) -> list[Case]:
    """Apply a routing policy, marking which cases a human saw."""
    rng = rng or random.Random(0)
    return [Case(c.confidence, c.correct,
                 reviewed=rng.random() < policy.review_prob(c.confidence))
            for c in cases]


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

def _log_binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return float("-inf") if k < n else 0.0
    lp, lq = math.log(p), math.log1p(-p)
    total = float("-inf")
    for i in range(k + 1):
        term = (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                + i * lp + (n - i) * lq)
        if total == float("-inf"):
            total = term
        elif term > total:
            total = term + math.log1p(math.exp(total - term))
        else:
            total = total + math.log1p(math.exp(term - total))
    return total


def clopper_pearson_upper(k: int, n: int, delta: float = 0.05) -> float:
    """Exact upper bound on a binomial rate; valid at k=0 and small n."""
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    target = math.log(delta)
    lo, hi = k / n, 1.0
    for _ in range(120):
        mid = (lo + hi) / 2
        if _log_binom_cdf(k, n, mid) > target:
            lo = mid
        else:
            hi = mid
    return hi


def naive_threshold(calibration: list[Case], alpha: float = 0.05,
                    delta: float = 0.05, grid: int = 100) -> float:
    """
    Split-conformal risk control on the calibration sample, ignoring routing.

    The threshold grid is fixed in advance rather than read off observed
    confidences: a grid chosen after seeing the outcomes makes the selection
    order data-dependent and breaks fixed-sequence testing.
    """
    best = 1.0 + 1e-9
    for lam in sorted((i / grid for i in range(grid + 1)), reverse=True):
        accepted = [c for c in calibration if c.confidence >= lam]
        if not accepted:
            continue
        errs = sum(1 for c in accepted if not c.correct)
        if clopper_pearson_upper(errs, len(accepted), delta) <= alpha:
            best = lam
        elif best < 1.0:
            # Only stop once a feasible threshold has been found. Breaking on
            # the first failure returns "accept nothing", because at the
            # strictest thresholds the accepted sample is too small for any
            # bound to certify — the search fails before it can succeed.
            break
    return best


def weighted_threshold(calibration: list[Case], policy: RoutingPolicy,
                       alpha: float = 0.05, delta: float = 0.05,
                       grid: int = 100) -> float:
    """
    Threshold corrected for the routing policy.

    A case is only exposed in production if the reviewer declines to look at
    it, which happens with probability 1 − π(s). The deployment distribution
    over auto-accepted cases is therefore the calibration distribution
    reweighted by that factor, and the risk estimate has to be reweighted to
    match.

    Effective sample size follows Kish: (Σw)² / Σw². Using the raw count would
    claim precision the weighting does not deliver, and it is the failure mode
    that makes a weighted estimator look better calibrated than it is.
    """
    best = 1.0 + 1e-9
    for lam in sorted((i / grid for i in range(grid + 1)), reverse=True):
        accepted = [c for c in calibration if c.confidence >= lam]
        if not accepted:
            continue

        weights = [1.0 - policy.review_prob(c.confidence) for c in accepted]
        total_w = sum(weights)
        if total_w <= 0:
            continue
        n_eff = (total_w ** 2) / sum(w * w for w in weights)

        err_w = sum(w for w, c in zip(weights, accepted) if not c.correct)
        k_eff = int(round(err_w / total_w * n_eff))

        if clopper_pearson_upper(k_eff, max(1, int(round(n_eff))), delta) <= alpha:
            best = lam
        elif best < 1.0:
            break
    return best


# ---------------------------------------------------------------------------
# What actually happens in deployment
# ---------------------------------------------------------------------------

def realised_risk(deployment: list[Case], threshold: float) -> tuple[float, int]:
    """
    Error rate among cases that were auto-accepted AND not reviewed.

    Reviewed cases are assumed corrected, so they contribute no error. The
    exposure is entirely in what passed through untouched, which is the
    quantity the guarantee is about and the one that selection has distorted.
    """
    exposed = [c for c in deployment
               if c.confidence >= threshold and not c.reviewed]
    if not exposed:
        return 0.0, 0
    return sum(1 for c in exposed if not c.correct) / len(exposed), len(exposed)


@dataclass
class ShiftResult:
    policy: str
    intensity: float
    alpha: float
    trials: int

    naive_violations: int = 0
    weighted_violations: int = 0
    naive_risks: list[float] = field(default_factory=list)
    weighted_risks: list[float] = field(default_factory=list)
    naive_exposed: list[int] = field(default_factory=list)
    weighted_exposed: list[int] = field(default_factory=list)

    @property
    def naive_violation_rate(self) -> float:
        return self.naive_violations / self.trials if self.trials else 0.0

    @property
    def weighted_violation_rate(self) -> float:
        return self.weighted_violations / self.trials if self.trials else 0.0

    def _mean(self, xs):
        return sum(xs) / len(xs) if xs else 0.0

    def as_dict(self) -> dict:
        return {
            "policy": self.policy, "intensity": self.intensity,
            "alpha": self.alpha, "trials": self.trials,
            "naive_violation_rate": self.naive_violation_rate,
            "weighted_violation_rate": self.weighted_violation_rate,
            "naive_mean_risk": self._mean(self.naive_risks),
            "weighted_mean_risk": self._mean(self.weighted_risks),
            "naive_mean_exposed": self._mean(self.naive_exposed),
            "weighted_mean_exposed": self._mean(self.weighted_exposed),
        }


def run_experiment(policy: RoutingPolicy, *, alpha: float = 0.05,
                   delta: float = 0.05, n_cal: int = 800, n_dep: int = 800,
                   trials: int = 200, accuracy: float = 0.90,
                   calibration: float = 0.7, seed: int = 0) -> ShiftResult:
    """
    Fit a threshold on unrouted calibration data, deploy it where humans
    route, and measure the risk that actually lands.

    Calibration data is unrouted deliberately: it is collected before the
    confidence display exists, which is how the situation arises in practice.
    The shift is created by deployment, not present beforehand.
    """
    rng = random.Random(seed)
    res = ShiftResult(policy=policy.name, intensity=policy.intensity,
                      alpha=alpha, trials=trials)

    for _ in range(trials):
        cal = draw_cases(n_cal, accuracy=accuracy, calibration=calibration,
                         rng=rng)
        dep = route(draw_cases(n_dep, accuracy=accuracy,
                               calibration=calibration, rng=rng),
                    policy, rng)

        t_naive = naive_threshold(cal, alpha, delta)
        r_naive, n_naive = realised_risk(dep, t_naive)
        res.naive_risks.append(r_naive)
        res.naive_exposed.append(n_naive)
        if r_naive > alpha:
            res.naive_violations += 1

        t_w = weighted_threshold(cal, policy, alpha, delta)
        r_w, n_w = realised_risk(dep, t_w)
        res.weighted_risks.append(r_w)
        res.weighted_exposed.append(n_w)
        if r_w > alpha:
            res.weighted_violations += 1

    return res
