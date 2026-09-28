"""
When the routing policy is a moving target.

Everything so far assumes the routing policy is fixed: estimate π once, weight
by it, done. The behavioural half says otherwise. Reviewers who see a
confidence display learn from it, and the insurance motive that drives the
damaging pattern weakens as they come to trust the signal.

Simulated from the reviewer model, the confidence gradient over a deployment:

    week  1   +53.0%     strong insurance-seeking, guarantee broken
    week  4   +43.3%
    week  8   +19.0%
    week 12    +2.3%
    week 16    −1.5%     converged on the intended policy

**A procedure calibrated in week one is solving week one's problem.** Here the
drift runs toward safety, so a fixed threshold becomes over-conservative and
the cost is throughput rather than risk. The direction is not guaranteed:
onboarding a cohort of new reviewers, or a publicised incident, moves it back
the other way, and then a stale threshold is unsafe rather than merely
wasteful.

This is the tightest link between the two halves of the project. The
behavioural prediction — that reviewers learn — is what creates the methods
requirement for adaptivity. Neither half generates it alone.

Three procedures compared
-------------------------
    fixed       calibrate once before deployment, never revisit
    periodic    recalibrate every k weeks from a fresh audit sample
    adaptive    update the threshold online from observed audit outcomes

The adaptive procedure follows Adaptive Conformal Inference (Gibbs and Candès,
2021) in structure: a single learning-rate parameter adjusts the operating
level in response to realised error, with no assumption that the distribution
is stationary. ACI controls coverage of prediction sets; the adaptation here
targets selective risk under a threshold, which is the same mechanism applied
to a different functional.

Audit, not oracle
-----------------
An adaptive procedure needs to observe outcomes, and in deployment outcomes
arrive through audit: a sampled fraction of auto-accepted cases is checked
later. The procedures below see only that sample, and the audit rate is a cost
that belongs in the comparison. A version with full outcome feedback would
adapt faster and would not describe any real deployment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .reviewer import ReviewerModel, draw_stakes
from .shift import Case, clopper_pearson_upper, naive_threshold, realised_risk


@dataclass(frozen=True)
class DriftSchedule:
    """
    How the insurance motive decays as reviewers learn.

    Exponential decay toward a floor, which is the shape the behavioural
    account implies: learning is fast early and asymptotes. The floor is
    non-zero because some insurance motive survives any amount of learning —
    the accountability structure does not change just because the reviewer
    trusts the model.
    """

    gamma_initial: float = 1.2
    gamma_floor: float = 0.1
    half_life_weeks: float = 5.0

    def gamma_at(self, week: int) -> float:
        decay = 0.5 ** (week / self.half_life_weeks)
        return self.gamma_floor + (self.gamma_initial - self.gamma_floor) * decay


def generate_week(model: ReviewerModel, n: int, *, accuracy: float = 0.90,
                  calibration: float = 0.7, stake_correlation: float = 0.7,
                  capacity: float = 0.3, rng: random.Random) -> list[Case]:
    """One week of routed cases under the current reviewer behaviour."""
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


def audit(cases: list[Case], threshold: float, rate: float,
          rng: random.Random) -> tuple[int, int]:
    """
    Sample auto-accepted cases and check them.

    Returns (errors found, cases audited). This is the only outcome signal a
    real deployment has, and it arrives on a sample rather than in full.
    """
    exposed = [c for c in cases if c.confidence >= threshold and not c.reviewed]
    sampled = [c for c in exposed if rng.random() < rate]
    if not sampled:
        return 0, 0
    return sum(1 for c in sampled if not c.correct), len(sampled)


# ---------------------------------------------------------------------------
# Procedures
# ---------------------------------------------------------------------------

@dataclass
class WeeklyRecord:
    week: int
    threshold: float
    realised_risk: float
    exposed: int
    violated: bool
    audited: int = 0


@dataclass
class ProcedureResult:
    name: str
    alpha: float
    weeks: list[WeeklyRecord] = field(default_factory=list)
    audit_cost: int = 0

    @property
    def violation_rate(self) -> float:
        return (sum(w.violated for w in self.weeks) / len(self.weeks)
                if self.weeks else 0.0)

    @property
    def mean_exposed(self) -> float:
        return (sum(w.exposed for w in self.weeks) / len(self.weeks)
                if self.weeks else 0.0)

    @property
    def mean_risk(self) -> float:
        return (sum(w.realised_risk for w in self.weeks) / len(self.weeks)
                if self.weeks else 0.0)

    def as_dict(self) -> dict:
        return {
            "procedure": self.name, "alpha": self.alpha,
            "violation_rate": self.violation_rate,
            "mean_exposed": self.mean_exposed,
            "mean_risk": self.mean_risk,
            "audit_cost": self.audit_cost,
            "weeks": [{"week": w.week, "threshold": w.threshold,
                       "risk": w.realised_risk, "exposed": w.exposed,
                       "violated": w.violated} for w in self.weeks],
        }


def run_deployment(procedure: str, *, weeks: int = 16, n_week: int = 600,
                   alpha: float = 0.05, delta: float = 0.05,
                   audit_rate: float = 0.15, refit_every: int = 4,
                   learning_rate: float = 0.02,
                   schedule: DriftSchedule | None = None,
                   seed: int = 0) -> ProcedureResult:
    """
    Run one procedure across a drifting deployment.

    `fixed` calibrates once on pre-deployment data and never revisits.
    `periodic` recalibrates every `refit_every` weeks from the audit sample.
    `adaptive` nudges the threshold each week in response to observed error.
    """
    sched = schedule or DriftSchedule()
    rng = random.Random(seed)
    res = ProcedureResult(name=procedure, alpha=alpha)

    # Pre-deployment calibration: collected before the display exists, so
    # unrouted.
    cal = [Case(c.confidence, c.correct)
           for c in generate_week(ReviewerModel(gamma=0.0), 900, rng=rng)]
    threshold = naive_threshold(cal, alpha, delta)

    for week in range(1, weeks + 1):
        model = ReviewerModel(beta=1.0, gamma=sched.gamma_at(week), a=1.0)
        cases = generate_week(model, n_week, rng=rng)

        risk, exposed = realised_risk(cases, threshold)
        errs, n_aud = audit(cases, threshold, audit_rate, rng)
        res.audit_cost += n_aud

        res.weeks.append(WeeklyRecord(
            week=week, threshold=threshold, realised_risk=risk,
            exposed=exposed, violated=risk > alpha, audited=n_aud))

        # Update for next week.
        if procedure == "fixed":
            continue

        if procedure == "periodic" and week % refit_every == 0 and n_aud > 0:
            # Recalibrate from what the audit saw, which is a sample of the
            # exposed population rather than of everything.
            bound = clopper_pearson_upper(errs, n_aud, delta)
            if bound > alpha:
                threshold = min(1.0, threshold + 0.05)
            elif bound < alpha / 2:
                threshold = max(0.0, threshold - 0.03)

        elif procedure == "guarded" and n_aud > 0:
            # Adapt every week, but move only when the evidence clears a
            # bound. This is the synthesis the comparison below forces: the
            # unguarded update chases audit noise and loses to doing nothing,
            # while the periodic refit wins mainly because it waits for a
            # bound rather than because it waits at all.
            # SYMMETRIC in the bound, deliberately.
            #
            # The first version raised the threshold fast and lowered it only
            # when the bound fell below alpha/2, which is rare. It ratcheted
            # monotonically upward and ended the deployment auto-accepting 14
            # cases out of 600 — a 4.8% violation rate achieved by refusing to
            # do anything. That is the third appearance of the accept-nothing
            # failure in this project, and it survived two existing tests
            # written about exactly that mode because both were scoped to
            # other modules.
            #
            # The update now moves proportionally to the signed gap between
            # the bound and the target, in both directions and at the same
            # rate, so there is no ratchet.
            bound = clopper_pearson_upper(errs, n_aud, delta)
            gap = (bound - alpha) / max(alpha, 1e-9)
            threshold = min(1.0, max(0.0,
                                     threshold + learning_rate * 2.0 * gap))

        elif procedure == "adaptive" and n_aud > 0:
            # ACI-style update: move against the realised error, proportional
            # to how far it sits from target. No stationarity assumed, which
            # is the point — the drift is exactly what breaks a stationary
            # procedure.
            observed = errs / n_aud
            threshold = min(1.0, max(0.0,
                                     threshold + learning_rate * (observed - alpha) * 20))

    return res


def compare_procedures(*, weeks: int = 16, trials: int = 40,
                       alpha: float = 0.05, audit_rate: float = 0.15,
                       seed: int = 0) -> list[dict]:
    """
    All three procedures on identical drifting deployments.

    Averaged over trials because a single run of sixteen weeks is too noisy to
    separate them, and reporting one run would be selecting a story.
    """
    out = []
    for proc in ("fixed", "periodic", "adaptive", "guarded"):
        viol, exp, risk, cost = [], [], [], []
        for t in range(trials):
            r = run_deployment(proc, weeks=weeks, alpha=alpha,
                               audit_rate=audit_rate, seed=seed + t)
            viol.append(r.violation_rate)
            exp.append(r.mean_exposed)
            risk.append(r.mean_risk)
            cost.append(r.audit_cost)
        mean = lambda xs: sum(xs) / len(xs)
        out.append({
            "procedure": proc,
            "violation_rate": mean(viol),
            "mean_exposed": mean(exp),
            "mean_risk": mean(risk),
            "audit_cost": mean(cost),
            "trials": trials,
        })
    return out
