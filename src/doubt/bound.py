"""
A bound for the estimated-policy case, and a check that it holds.

`docs/theory.md` states Proposition 3 as conjectured: with weights estimated to
accuracy ε and floored at η, the coverage gap should be of order ε/η. That was
asserted from the shape of standard inverse-probability-weighting sensitivity
arguments, without a derivation and without a check.

This module does two things a conjecture cannot do on its own. It states the
bound explicitly enough to be wrong, and it measures whether the realised gap
respects it.

The derivation
--------------
The weighted selective risk estimate at threshold λ is a ratio

    R̂_w(λ) = Σ w_i e_i / Σ w_i        over accepted i, with e_i = 1{error}

With true weights w and estimated ŵ satisfying |ŵ_i − w_i| ≤ ε and ŵ_i ≥ η,
write N̂ = Σ ŵ_i e_i, D̂ = Σ ŵ_i, and similarly N, D for the true weights.
Then |N̂ − N| ≤ ε·n_acc and |D̂ − D| ≤ ε·n_acc, and D ≥ η·n_acc, so

    |R̂_w − R_w| = |N̂/D̂ − N/D|
                 = |N̂·D − N·D̂| / (D̂·D)
                 ≤ (|N̂ − N|·D + N·|D − D̂|) / (D̂·D)
                 ≤ ε·n_acc·(D + N) / (D̂·D)
                 ≤ ε·(1 + R_w) / η                     [dividing through]

Since R_w ≤ 1, a conservative form is

    |R̂_w − R_w| ≤ 2ε/η

**This is elementary and it is stated to be checked, not admired.** The step
worth scrutiny is the last: bounding (D + N)/(D̂·D/n_acc) by (1 + R_w)/η uses
D̂ ≥ η·n_acc and D ≥ η·n_acc, and is loose. A tighter constant is available;
the shape is what matters for the claim that estimation error is tolerable at
order ε/η.

What this does NOT establish
----------------------------
The bound is on the RISK ESTIMATE, not on coverage. Translating it into a
coverage statement requires composing it with the concentration bound that
turns an estimate into a threshold, and those interact — the same sample drives
both. That composition is the technical work `docs/theory.md` says is missing,
and it remains missing.

So: the estimate is provably close, and the coverage consequence is measured
rather than proved. That is a smaller claim than "Proposition 3 proved" and it
is the one the work supports.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .estimate import estimate_policy
from .shift import Case, RoutingPolicy, draw_cases, route


def theoretical_bound(epsilon: float, eta: float) -> float:
    """
    The sup-norm form: 2ε/η.

    Correct in shape and VACUOUS in practice. Measured against the estimator
    in this repository it evaluates to 1.0 in every configuration tried, while
    the realised gap is 0.02 to 0.06 — a bound of one on a probability holds
    trivially and says nothing.

    The reason is that ε is a supremum, attained at the edges of the
    confidence range where the pilot has least data and the isotonic fit is
    worst. The realised error depends on the weights where the accepted mass
    actually sits, which is nowhere near those edges.

    Kept because a vacuous bound that is stated and shown to be vacuous is
    more useful than one quietly dropped; `mass_weighted_bound` below is the
    version that carries information.
    """
    if eta <= 0:
        return 1.0
    return min(1.0, 2.0 * epsilon / eta)


def mass_weighted_bound(cases, threshold: float, policy, estimated,
                        eta: float) -> float:
    """
    The same argument with the error measured where the accepted mass is.

    Replacing the supremum with the mean absolute weight error over the
    accepted population gives

        |R̂_w − R_w| ≤ 2·ε̄ / η̄        with  ε̄ = mean|ŵ − w|,  η̄ = mean ŵ

    which is the same derivation carried through without discarding the
    distribution. Using the mean estimated weight rather than the floor in the
    denominator is the step that recovers information: η is a worst-case
    guarantee on a single weight, η̄ is what the estimate actually divides by.
    """
    acc = [c for c in cases if c.confidence >= threshold]
    if not acc:
        return 1.0
    errs, ws = [], []
    for c in acc:
        w_true = max(eta, 1.0 - policy.review_prob(c.confidence))
        w_est = max(eta, 1.0 - estimated.review_prob(c.confidence))
        errs.append(abs(w_est - w_true))
        ws.append(w_est)
    eps_bar = sum(errs) / len(errs)
    eta_bar = sum(ws) / len(ws)
    if eta_bar <= 0:
        return 1.0
    return min(1.0, 2.0 * eps_bar / eta_bar)


def weighted_risk(cases: list[Case], threshold: float,
                  weight_fn, floor: float = 0.0) -> float:
    """Weighted selective risk among accepted cases."""
    acc = [c for c in cases if c.confidence >= threshold]
    if not acc:
        return 0.0
    ws = [max(floor, weight_fn(c.confidence)) for c in acc]
    total = sum(ws)
    if total <= 0:
        return 0.0
    return sum(w for w, c in zip(ws, acc) if not c.correct) / total


@dataclass
class BoundCheck:
    n_pilot: int
    eta: float
    epsilon: float
    bound: float
    realised_gap: float
    trials: int
    mass_bound: float = 1.0

    @property
    def holds(self) -> bool:
        return self.realised_gap <= self.bound + 1e-12

    @property
    def slack(self) -> float:
        """How loose the bound is. Large slack means a tighter one exists."""
        return self.bound - self.realised_gap

    def as_dict(self) -> dict:
        return {
            "n_pilot": self.n_pilot, "eta": self.eta,
            "epsilon_measured": self.epsilon,
            "bound_sup_norm": self.bound,
            "bound_mass_weighted": self.mass_bound,
            "realised_gap": self.realised_gap,
            "holds": self.holds,
            "mass_bound_holds": self.realised_gap <= self.mass_bound + 1e-12,
            "sup_bound_informative": self.bound < 0.999,
            "mass_bound_informative": self.mass_bound < 0.999,
            "trials": self.trials,
        }


def check_bound(policy: RoutingPolicy, *, n_pilot: int = 400,
                eta: float = 0.02, threshold: float = 0.3,
                n_eval: int = 800, trials: int = 60,
                seed: int = 0) -> BoundCheck:
    """
    Measure ε from the estimator, compute 2ε/η, and compare against the
    largest realised gap between the true-weight and estimated-weight risk.

    The WORST gap across trials is reported, not the mean. A bound that holds
    on average is not a bound, and reporting the mean would hide exactly the
    violations this exists to detect.
    """
    rng_pilot = random.Random(seed * 7919 + 1)
    rng_eval = random.Random(seed)

    grid = [i / 50 for i in range(51)]
    worst_gap = 0.0
    worst_eps = 0.0
    worst_mass_bound = 0.0

    for _ in range(trials):
        pilot = route(draw_cases(n_pilot, rng=rng_pilot), policy, rng_pilot)
        est = estimate_policy(pilot)

        eps = max(abs(est.review_prob(s) - policy.review_prob(s)) for s in grid)
        worst_eps = max(worst_eps, eps)

        cases = draw_cases(n_eval, rng=rng_eval)
        true_r = weighted_risk(cases, threshold,
                               lambda s: 1.0 - policy.review_prob(s), eta)
        est_r = weighted_risk(cases, threshold,
                              lambda s: 1.0 - est.review_prob(s), eta)
        worst_gap = max(worst_gap, abs(true_r - est_r))
        worst_mass_bound = max(worst_mass_bound,
                               mass_weighted_bound(cases, threshold, policy,
                                                   est, eta))

    return BoundCheck(
        n_pilot=n_pilot, eta=eta, epsilon=worst_eps,
        bound=theoretical_bound(worst_eps, eta),
        mass_bound=worst_mass_bound,
        realised_gap=worst_gap, trials=trials,
    )


def sweep_bound(policy: RoutingPolicy, *, pilots: list[int],
                etas: list[float], trials: int = 40,
                seed: int = 0) -> list[dict]:
    """
    Check the bound across pilot sizes and clipping floors.

    A bound that holds only at one configuration is a coincidence. The floor
    matters most: as η shrinks the bound grows without limit, and the point of
    the sweep is to see whether the realised gap tracks that or whether the
    bound is simply loose everywhere.
    """
    return [check_bound(policy, n_pilot=n, eta=e, trials=trials,
                        seed=seed).as_dict()
            for n in pilots for e in etas]
