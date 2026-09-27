"""
What an accountability regime is worth, in error rate.

The two halves of this project have run separately. `reviewer.py` derives how
people route; `shift.py` measures what routing does to a guarantee. Neither
answers the question a manager would ask, which is what the behaviour costs.

This joins them. Reviewers are simulated from the decision model, their routing
is fed into the risk-control machinery, and the deployed error rate is measured
under each accountability regime. The output is a translation between a
management choice and a statistical outcome:

    changing how reviewers are evaluated changes the error rate that reaches
    production, by an amount that can be stated

That translation is the reason this is one project rather than two papers that
cite each other. The methods half cannot produce it — it has no theory of where
routing comes from. The behavioural half cannot produce it — it has no
machinery for turning routing into risk.

What is being compared
----------------------
Three regimes, holding the model, the cases and the reviewers' competence
fixed. Only the evaluation scheme differs:

    process-based     reviewers judged on whether they followed the procedure
    mixed             the common real arrangement
    outcome-based     reviewers judged on whether anything went wrong

And three responses available to a manager who has measured the problem:

    do nothing              keep the uncorrected threshold
    correct statistically   reweight for the routing policy
    correct managerially    move to process-based evaluation

The third is the interesting one, because it is free of the estimation
machinery entirely and, on these results, does more.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .estimate import estimate_policy, estimated_threshold
from .reviewer import ReviewerModel, draw_stakes
from .shift import Case, naive_threshold, realised_risk


@dataclass(frozen=True)
class Regime:
    """An accountability arrangement, as the reviewer model represents it."""

    name: str
    gamma: float
    accountability: float


REGIMES = [
    Regime("process-based", gamma=1.2, accountability=0.0),
    Regime("mixed", gamma=1.2, accountability=0.5),
    Regime("outcome-based", gamma=1.2, accountability=1.0),
]


def draw_and_route(n: int, model: ReviewerModel, *, accuracy: float = 0.90,
                   calibration: float = 0.7, stake_correlation: float = 0.7,
                   capacity: float = 0.3,
                   rng: random.Random) -> list[Case]:
    """
    Cases routed by a reviewer behaving according to the decision model.

    Confidence and correctness are drawn as elsewhere; stakes are drawn
    correlated with confidence, because that correlation is the mechanism the
    whole account depends on and hiding it inside a default would make the
    result look more general than it is.
    """
    out = []
    for _ in range(n):
        correct = rng.random() < accuracy
        base = rng.random()
        conf = min(1.0, max(0.0, base * (1 - calibration)
                            + calibration * (0.85 if correct else 0.15)))
        stakes = draw_stakes(conf, stake_correlation, rng)
        reviewed = rng.random() < model.review_prob(conf, stakes, capacity)
        out.append(Case(conf, correct, reviewed=reviewed))
    return out


@dataclass
class RegimeOutcome:
    regime: str
    accountability: float

    uncorrected_risk: float
    uncorrected_violations: float
    uncorrected_exposed: float

    corrected_risk: float
    corrected_violations: float
    corrected_exposed: float

    trials: int = 0
    alpha: float = 0.05

    def as_dict(self) -> dict:
        return {
            "regime": self.regime, "accountability": self.accountability,
            "alpha": self.alpha, "trials": self.trials,
            "uncorrected_risk": self.uncorrected_risk,
            "uncorrected_violation_rate": self.uncorrected_violations,
            "uncorrected_exposed": self.uncorrected_exposed,
            "corrected_risk": self.corrected_risk,
            "corrected_violation_rate": self.corrected_violations,
            "corrected_exposed": self.corrected_exposed,
        }


def evaluate_regime(regime: Regime, *, alpha: float = 0.05, delta: float = 0.05,
                    n_pilot: int = 800, n_cal: int = 700, n_dep: int = 700,
                    trials: int = 120, stake_correlation: float = 0.7,
                    seed: int = 0) -> RegimeOutcome:
    """
    Deployed risk under one accountability regime, with and without the
    statistical correction.

    Calibration data is unrouted: it is collected before the confidence
    display exists, which is how the situation arises. The pilot is routed,
    because the policy can only be estimated from behaviour that has already
    happened.
    """
    model = ReviewerModel(beta=1.0, gamma=regime.gamma, a=regime.accountability)
    rng_pilot = random.Random(seed * 7919 + 1)
    rng_main = random.Random(seed)

    unc_risks, unc_viol, unc_exp = [], 0, []
    cor_risks, cor_viol, cor_exp = [], 0, []

    for _ in range(trials):
        pilot = draw_and_route(n_pilot, model,
                               stake_correlation=stake_correlation,
                               rng=rng_pilot)
        est = estimate_policy(pilot)

        cal = [Case(c.confidence, c.correct)
               for c in draw_and_route(n_cal, model,
                                       stake_correlation=stake_correlation,
                                       rng=rng_main)]
        dep = draw_and_route(n_dep, model,
                             stake_correlation=stake_correlation,
                             rng=rng_main)

        r, n = realised_risk(dep, naive_threshold(cal, alpha, delta))
        unc_risks.append(r); unc_exp.append(n)
        if r > alpha:
            unc_viol += 1

        r, n = realised_risk(dep, estimated_threshold(cal, est, alpha, delta))
        cor_risks.append(r); cor_exp.append(n)
        if r > alpha:
            cor_viol += 1

    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    return RegimeOutcome(
        regime=regime.name, accountability=regime.accountability,
        uncorrected_risk=mean(unc_risks),
        uncorrected_violations=unc_viol / trials,
        uncorrected_exposed=mean(unc_exp),
        corrected_risk=mean(cor_risks),
        corrected_violations=cor_viol / trials,
        corrected_exposed=mean(cor_exp),
        trials=trials, alpha=alpha,
    )


def compare_interventions(*, alpha: float = 0.05, trials: int = 120,
                          stake_correlation: float = 0.7,
                          seed: int = 0) -> list[dict]:
    """
    Every regime, with and without the statistical fix.

    The comparison a manager needs: what does changing the evaluation scheme
    buy, against what the reweighting buys, against doing both.
    """
    return [evaluate_regime(r, alpha=alpha, trials=trials,
                            stake_correlation=stake_correlation,
                            seed=seed).as_dict()
            for r in REGIMES]


def cost_of_accountability(rows: list[dict], *,
                           annual_decisions: float = 1_000_000,
                           n_dep: int = 700) -> dict:
    """
    Translate the difference between regimes into production consequences.

    Three quantities, because reporting any one alone misleads:

        violation rate   is the promised error rate being met
        error rate       among cases that reach production untouched
        throughput       what share is automated at all

    The trap this function exists to avoid: process-based accountability holds
    its guarantee and produces MORE total errors, because it auto-accepts far
    more volume. Outcome-based accountability breaks its guarantee and
    produces fewer total errors, because reviewers are manually checking most
    of the work.

    Those are different failures and a manager needs both. Reporting only
    total errors would recommend the regime that breaks the guarantee;
    reporting only the violation rate would recommend the regime that
    automates least. The comparison is not apples to apples and the function
    says so rather than resolving it silently.

    Expressed in counts rather than currency throughout. What a wrong decision
    costs varies by orders of magnitude across the settings this could apply
    to, and would be the weakest number in the analysis.
    """
    by = {r["regime"]: r for r in rows}
    if "process-based" not in by or "outcome-based" not in by:
        return {}

    proc, outc = by["process-based"], by["outcome-based"]

    # Errors reaching production = exposure share x error rate among exposed.
    def escaping(r, key_risk, key_exp, n_dep=700):
        return (r[key_exp] / n_dep) * r[key_risk] * annual_decisions

    def throughput(r, key_exp):
        return r[key_exp] / n_dep

    def manual(r, key_exp):
        return (1 - throughput(r, key_exp)) * annual_decisions

    return {
        "annual_decisions": annual_decisions,
        "process_based": {
            "guarantee_violation_rate": proc["uncorrected_violation_rate"],
            "error_rate_in_production": proc["uncorrected_risk"],
            "share_automated": throughput(proc, "uncorrected_exposed"),
            "errors_reaching_production":
                escaping(proc, "uncorrected_risk", "uncorrected_exposed"),
            "decisions_reviewed_manually": manual(proc, "uncorrected_exposed"),
        },
        "outcome_based": {
            "guarantee_violation_rate": outc["uncorrected_violation_rate"],
            "error_rate_in_production": outc["uncorrected_risk"],
            "share_automated": throughput(outc, "uncorrected_exposed"),
            "errors_reaching_production":
                escaping(outc, "uncorrected_risk", "uncorrected_exposed"),
            "decisions_reviewed_manually": manual(outc, "uncorrected_exposed"),
        },
        "outcome_based_corrected": {
            "guarantee_violation_rate": outc["corrected_violation_rate"],
            "error_rate_in_production": outc["corrected_risk"],
            "share_automated": throughput(outc, "corrected_exposed"),
            "errors_reaching_production":
                escaping(outc, "corrected_risk", "corrected_exposed"),
        },
        "note": (
            "Process-based accountability holds its guarantee and produces "
            "MORE total errors, because it automates far more volume. "
            "Outcome-based breaks its guarantee and produces fewer, because "
            "reviewers are checking most of the work by hand. These are "
            "different failures; reporting either alone recommends the wrong "
            "regime."),
    }
