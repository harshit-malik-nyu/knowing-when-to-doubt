"""
Why a reviewer would check the cases the model is confident about.

The routing policies in `shift.py` are stipulated. `reviews_high_stakes` breaks
the guarantee, and the simulation shows how badly, but nothing explains why a
reviewer would behave that way. A hypothesis without a mechanism is a guess
with a p-value attached, and a committee is right to press on it.

This module derives the behaviour from a decision problem the reviewer is
actually facing.

The organisation's problem
--------------------------
An organisation wanting to minimise expected loss reviews where review has the
highest expected value:

    V_org(s, v) = v · P(error | s) · q

where `s` is the displayed confidence, `v` the stakes on the case, `q` the
probability a reviewer catches an error given they look. Since P(error | s)
falls in s, V_org falls in s. **The organisation wants low-confidence cases
reviewed.** That is the intended policy and it is the one that makes deployment
safer than calibrated.

The reviewer's problem
----------------------
The reviewer is not minimising organisational loss. They face blame, and blame
has a structure the organisation's loss does not:

    V_rev(s, v) = β · v · P(error | s) · q  +  γ · v · a

The first term is the organisation's objective, weighted by how much the
reviewer internalises it. The second is **insurance**: on a high-stakes case,
having reviewed is protective whether or not an error was present, because the
question asked afterwards is "did you check" rather than "was checking
warranted". `a` is the accountability regime — high where reviewers are judged
on outcomes, low where they are judged on process.

The insurance term does not depend on P(error | s). It depends on stakes alone.

The prediction
--------------
As `γ·a` grows relative to `β`, routing is driven by stakes rather than by
confidence. That alone would make routing independent of the signal, which is
harmless for the guarantee.

The damage comes from the empirical regularity that **stakes and confidence are
positively correlated**. High-value cases in most document workflows are
standard-form, well-represented in training data, and cleanly drafted — a
large contract is more boilerplate than a small one, not less. Where that
holds, routing on stakes is routing on confidence, and the reviewer checks
exactly the cases the model was most likely to get right.

That is H3, derived rather than assumed, and it comes with two further
predictions the hypothesis alone does not make:

    MODERATOR   The effect strengthens under outcome-based accountability and
                weakens under process-based accountability. That is testable
                and it is the kind of variation firms already have across
                teams.

    BOUNDARY    Where stakes and confidence are uncorrelated or negatively
                correlated, routing is harmless to the guarantee even under
                strong insurance motives. The failure is not universal, and a
                design that cannot distinguish the two cases cannot test the
                theory.

Sensitivity to the correlation assumption is measured below rather than
asserted, because it is the assumption the whole account rests on.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewerModel:
    """
    A reviewer choosing what to check, under blame.

    beta   how much the reviewer internalises the organisation's loss
    gamma  weight on insurance — the protective value of having looked
    a      accountability regime: 1 outcome-based, 0 process-based
    q      probability of catching an error given review
    """

    beta: float = 1.0
    gamma: float = 0.0
    a: float = 1.0
    q: float = 0.8

    def organisational_value(self, confidence: float, stakes: float) -> float:
        """What review is worth to the organisation."""
        return stakes * (1.0 - confidence) * self.q

    def reviewer_value(self, confidence: float, stakes: float) -> float:
        """What review is worth to the reviewer."""
        return (self.beta * self.organisational_value(confidence, stakes)
                + self.gamma * stakes * self.a)

    def review_prob(self, confidence: float, stakes: float,
                    capacity: float = 0.3, sharpness: float = 6.0) -> float:
        """
        Probability this case is reviewed, given limited capacity.

        A softmax over value rather than a hard rule: reviewers are not
        optimisers, and a deterministic cutoff would make the routing policy
        trivially estimable in a way real behaviour is not.
        """
        v = self.reviewer_value(confidence, stakes)
        # centred so that capacity is the review rate at average value
        z = sharpness * (v - 0.5) + math.log(capacity / (1 - capacity))
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def draw_stakes(confidence: float, correlation: float,
                rng: random.Random) -> float:
    """
    Stakes on a case, correlated with the model's confidence.

    `correlation` at 0 makes stakes independent of confidence — the boundary
    condition where routing on stakes is harmless. At 1 they move together,
    which is the regularity the theory relies on: large contracts are more
    standard-form than small ones, so the model is more confident about
    exactly the cases that matter most.
    """
    noise = rng.random()
    return min(1.0, max(0.0, correlation * confidence + (1 - correlation) * noise))


@dataclass
class RoutingPattern:
    """What the model implies about observable routing."""

    gamma: float
    accountability: float
    stake_correlation: float

    review_rate_low_conf: float
    review_rate_high_conf: float
    n: int

    @property
    def confidence_gradient(self) -> float:
        """
        Positive means reviewers check confident cases — the pattern that
        breaks the guarantee. Negative is the intended policy.
        """
        return self.review_rate_high_conf - self.review_rate_low_conf

    @property
    def predicts_shift(self) -> bool:
        return self.confidence_gradient > 0.02

    def as_dict(self) -> dict:
        return {
            "gamma": self.gamma, "accountability": self.accountability,
            "stake_correlation": self.stake_correlation,
            "review_rate_low_confidence": self.review_rate_low_conf,
            "review_rate_high_confidence": self.review_rate_high_conf,
            "confidence_gradient": self.confidence_gradient,
            "predicts_shift": self.predicts_shift,
            "n": self.n,
        }


def simulate_routing(model: ReviewerModel, *, stake_correlation: float = 0.7,
                     n: int = 6000, capacity: float = 0.3,
                     seed: int = 0) -> RoutingPattern:
    """
    What routing pattern does this reviewer produce?

    Reports review rates in the bottom and top confidence terciles, which is
    the comparison the empirical design can actually make — a reviewer-level
    gradient estimated from observed decisions, not a latent parameter.
    """
    rng = random.Random(seed)
    low, high = [], []
    for _ in range(n):
        conf = rng.random()
        stakes = draw_stakes(conf, stake_correlation, rng)
        reviewed = rng.random() < model.review_prob(conf, stakes, capacity)
        if conf < 1 / 3:
            low.append(reviewed)
        elif conf > 2 / 3:
            high.append(reviewed)

    rate = lambda xs: sum(xs) / len(xs) if xs else 0.0
    return RoutingPattern(
        gamma=model.gamma, accountability=model.a,
        stake_correlation=stake_correlation,
        review_rate_low_conf=rate(low), review_rate_high_conf=rate(high),
        n=n,
    )


def accountability_sweep(gammas: list[float], accountabilities: list[float],
                         *, stake_correlation: float = 0.7,
                         n: int = 6000, seed: int = 0) -> list[dict]:
    """
    The moderator prediction: does outcome-based accountability produce the
    damaging routing pattern, and process-based accountability avoid it?
    """
    rows = []
    for g in gammas:
        for a in accountabilities:
            p = simulate_routing(ReviewerModel(beta=1.0, gamma=g, a=a),
                                 stake_correlation=stake_correlation,
                                 n=n, seed=seed)
            rows.append(p.as_dict())
    return rows


def correlation_sweep(correlations: list[float], *, gamma: float = 1.2,
                      n: int = 6000, seed: int = 0) -> list[dict]:
    """
    The boundary prediction: the failure requires stakes and confidence to
    move together. Where they do not, strong insurance motives are harmless
    to the guarantee.

    This is the assumption the whole account rests on, so it is swept rather
    than stated.
    """
    return [simulate_routing(ReviewerModel(beta=1.0, gamma=gamma, a=1.0),
                             stake_correlation=c, n=n, seed=seed).as_dict()
            for c in correlations]
