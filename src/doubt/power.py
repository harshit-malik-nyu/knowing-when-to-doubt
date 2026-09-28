"""
Power for the field study, computed rather than asserted.

The pre-registration originally said "roughly 40 reviewers and 12 weeks". That
number was stated, not derived, and it is exactly the claim a committee checks
first. This module computes it.

What makes this design's power unusual
--------------------------------------
The hypothesis is an **interaction**, not a main effect: whether the gradient
of override rate in model confidence differs by treatment arm. Interactions
need roughly four times the sample of a main effect of the same size, which is
the single most common reason field experiments in this area are underpowered.

Observations are also **clustered at the reviewer**, who sees many cases. The
design effect is 1 + (m − 1)·ICC with m the decisions per reviewer, and because
m is large — hundreds of cases — even a small intra-reviewer correlation
destroys most of the nominal sample. With m = 400 and ICC = 0.05, the design
effect is about 21: four hundred decisions carry the information of nineteen.

That is why the binding constraint is the **number of reviewers**, not the
number of decisions, and why a firm with millions of cases and twelve reviewers
cannot run this study.

What is not modelled
--------------------
Attrition, non-compliance, and spillover between teams sharing a floor. Each
reduces power further, and each is an argument for treating the numbers here
as a ceiling rather than a target.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Two-sided test at 5%, conventional power.
Z_ALPHA_2 = 1.959963984540054
Z_POWER_80 = 0.8416212335729143
Z_POWER_90 = 1.2815515655446004


def design_effect(decisions_per_reviewer: int, icc: float) -> float:
    """
    Kish design effect for clustering.

    Scales with CLUSTER SIZE, which is why a reviewer seeing hundreds of cases
    makes even a small correlation expensive. This is the same arithmetic that
    governs benchmark items grouped by subject.
    """
    return 1.0 + (decisions_per_reviewer - 1) * icc


def effective_n(reviewers: int, decisions_per_reviewer: int,
                icc: float) -> float:
    """Independent-equivalent observations."""
    total = reviewers * decisions_per_reviewer
    return total / design_effect(decisions_per_reviewer, icc)


@dataclass
class PowerResult:
    reviewers: int
    weeks: int
    decisions_per_reviewer: int
    icc: float
    effect_size: float
    power: float
    effective_n: float
    design_effect: float
    detectable_effect: float

    @property
    def adequate(self) -> bool:
        return self.power >= 0.80

    def as_dict(self) -> dict:
        return {
            "reviewers": self.reviewers, "weeks": self.weeks,
            "decisions_per_reviewer": self.decisions_per_reviewer,
            "icc": self.icc, "effect_size": self.effect_size,
            "power": self.power, "effective_n": self.effective_n,
            "design_effect": self.design_effect,
            "minimum_detectable_effect": self.detectable_effect,
            "adequate": self.adequate,
        }


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def power_for(*, reviewers: int, weeks: int, decisions_per_week: int = 40,
              icc: float = 0.05, effect_size: float = 0.05,
              baseline_rate: float = 0.30,
              interaction: bool = True) -> PowerResult:
    """
    Power to detect a change in override rate, or in the confidence gradient
    of override rate.

    `interaction=True` is the real design. The variance of an interaction
    contrast is roughly four times that of a main effect, because it is a
    difference of differences and each difference carries its own variance.
    Treating the interaction as a main effect is the error that makes
    underpowered studies look adequate on paper.
    """
    m = decisions_per_week * weeks
    deff = design_effect(m, icc)
    n_eff = effective_n(reviewers, m, icc)

    p = baseline_rate
    var_unit = p * (1 - p)

    # Two arms, so each contributes half the effective sample.
    se = math.sqrt(4.0 * var_unit / n_eff) if n_eff > 0 else float("inf")
    if interaction:
        se *= 2.0          # difference of differences

    if se == 0 or math.isinf(se):
        power = 0.0
        mde = float("inf")
    else:
        z = effect_size / se - Z_ALPHA_2
        power = _normal_cdf(z)
        mde = (Z_ALPHA_2 + Z_POWER_80) * se

    return PowerResult(
        reviewers=reviewers, weeks=weeks, decisions_per_reviewer=m,
        icc=icc, effect_size=effect_size, power=power,
        effective_n=n_eff, design_effect=deff, detectable_effect=mde,
    )


def reviewers_required(*, weeks: int = 12, decisions_per_week: int = 40,
                       icc: float = 0.05, effect_size: float = 0.05,
                       baseline_rate: float = 0.30, target_power: float = 0.80,
                       interaction: bool = True, cap: int = 5000) -> int:
    """
    Smallest reviewer count reaching the target power.

    Returns `cap` when the target is unreachable within it, which is an honest
    answer rather than an extrapolation — and for tight effects under heavy
    clustering it is the answer.
    """
    for n in range(4, cap + 1):
        r = power_for(reviewers=n, weeks=weeks,
                      decisions_per_week=decisions_per_week, icc=icc,
                      effect_size=effect_size, baseline_rate=baseline_rate,
                      interaction=interaction)
        if r.power >= target_power:
            return n
    return cap


def information_ceiling(reviewers: int, icc: float) -> float:
    """
    The most effective observations this reviewer pool can ever provide.

    As decisions per reviewer grows, effective n tends to reviewers/ICC and
    stops. With 40 reviewers at ICC 0.05 the ceiling is 800 independent-
    equivalent observations however many millions of decisions are collected.

    This is the structural fact that decides the study. The binding resource
    is REVIEWERS, not decisions, and a firm with enormous case volume and a
    small review team cannot buy its way to power. A design that plans to run
    longer is solving the wrong constraint.
    """
    return reviewers / icc if icc > 0 else float("inf")


def reviewers_for_ceiling(target_effective_n: float, icc: float) -> int:
    """How many reviewers are needed for a given information ceiling."""
    return math.ceil(target_effective_n * icc)


def sensitivity(*, iccs: list[float], effects: list[float],
                weeks: int = 12, decisions_per_week: int = 40) -> list[dict]:
    """
    Reviewers required across the assumptions that are actually uncertain.

    The ICC is never known in advance and is the parameter the design is most
    sensitive to. Presenting a single number for it, as the first draft of the
    pre-registration did, hides that sensitivity behind a guess.
    """
    rows = []
    for icc in iccs:
        for eff in effects:
            n = reviewers_required(weeks=weeks,
                                   decisions_per_week=decisions_per_week,
                                   icc=icc, effect_size=eff)
            rows.append({
                "icc": icc, "effect_size": eff, "weeks": weeks,
                "reviewers_required": n,
                "feasible": n <= 200,
            })
    return rows


def interaction_penalty(*, reviewers: int = 40, weeks: int = 12,
                        icc: float = 0.05, effect_size: float = 0.05) -> dict:
    """
    What testing an interaction rather than a main effect costs.

    Included because it is the most common way this class of study is
    mis-planned: power is computed for a main effect, the paper tests an
    interaction, and the result is a null that means nothing.
    """
    main = power_for(reviewers=reviewers, weeks=weeks, icc=icc,
                     effect_size=effect_size, interaction=False)
    inter = power_for(reviewers=reviewers, weeks=weeks, icc=icc,
                      effect_size=effect_size, interaction=True)
    return {
        "reviewers": reviewers, "weeks": weeks, "icc": icc,
        "effect_size": effect_size,
        "power_if_main_effect": main.power,
        "power_for_the_interaction": inter.power,
        "reviewers_for_main_effect":
            reviewers_required(weeks=weeks, icc=icc, effect_size=effect_size,
                               interaction=False),
        "reviewers_for_interaction":
            reviewers_required(weeks=weeks, icc=icc, effect_size=effect_size,
                               interaction=True),
    }
