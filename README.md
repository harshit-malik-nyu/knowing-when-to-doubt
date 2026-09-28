# Knowing when to doubt

**When reviewers decide what to check by looking at the model's confidence,
the guarantee calibrated on that confidence stops holding.**

A model scores each case and displays a confidence. A human decides what to
review. The cases that reach production untouched are therefore selected on
the same signal the guarantee was calibrated against — and the selection is
caused by the deployment itself.

---

## The result

Split-conformal risk control fitted before deployment, at a 5% target, then
deployed where reviewers route on the displayed confidence. 200 trials per
row.

| Routing intensity | Split conformal fails | Corrected fails | Realised risk |
|---:|---:|---:|---:|
| 0.0 (routes at random) | 9.5% | 9.5% | 0.035 |
| 0.2 | 17.5% | 10.0% | 0.039 |
| 0.4 | 31.5% | 10.0% | 0.045 |
| 0.6 | 53.0% | 12.5% | 0.053 |
| 0.8 | 78.0% | 14.0% | 0.065 |
| **1.0** | **90.0%** | **12.5%** | **0.084** |

A guarantee that holds in the lab fails in **nine deployments out of ten**, and
the realised error rate reaches 8.4% against a 5% target.

## The mechanism, and why direction matters

The failure is caused by one specific and entirely reasonable human behaviour:
**checking the cases the model is confident about**, because the case matters
regardless of what the model says.

Those reviews remove *correct* answers from the exposed pool. What passes
through untouched is the residue — enriched in errors relative to the
population the threshold was certified on.

The opposite policy does the opposite:

| Routing policy | Split conformal fails | Realised risk |
|---|---:|---:|
| Reviews **low** confidence (the intended policy) | 0.0% | 0.017 |
| Reviews the middle | 0.7% | 0.021 |
| Ignores the signal | 10.7% | 0.034 |
| Reviews **high** confidence | **83.3%** | **0.082** |

That asymmetry is the finding. It is not that human routing breaks guarantees
— reviewing what the model doubts makes deployment *safer* than calibrated.
It is that one plausible reviewer behaviour inverts them, and it is the
behaviour any organisation with high-stakes cases will exhibit.

## The correction

The exposed population is the calibration population reweighted by the
probability a reviewer declines to look: **1 − π(s)**. Weighting the risk
estimate by that factor restores coverage to roughly nominal.

Two details that decide whether it works:

**Effective sample size follows Kish**, (Σw)²/Σw², not the raw count. Using
the count claims precision the weighting does not deliver, and is what makes a
weighted estimator look better calibrated than it is.

**It is not free.** Certifying a harder population means accepting fewer cases
automatically: exposure falls from 456 to 176 cases per 700 as intensity
rises. The violation rate and the exposure cost belong in the same table.

---

## Relation to Feedback Covariate Shift

Feedback Covariate Shift is established. Fannjiang et al. (2022) introduced it
for design problems where predictions determine what data is collected;
Prinster et al. (2024) refined the theory and extended it to multistep
settings; Wang and Ning (NeurIPS 2025) apply feedback-based conformal
prediction to trajectory optimisation.

**In all of that work the loop runs through a machine** — an acquisition
function, a controller, an optimiser. The selection rule is chosen by the
system designer and is known exactly.

Here the loop runs through a person, and three things change:

| | Machine feedback | Human routing |
|---|---|---|
| The policy | designed, known exactly | unknown, must be estimated from behaviour |
| Stability | fixed | reviewers learn; the rule drifts, and the deployment caused it |
| Status | a nuisance to be corrected | the behavioural quantity of interest |

The third is the one that matters for the joint design below. In the machine
case you would remove the feedback if you could. Here how people route is the
thing being studied.

## The policy is unknown — does the correction survive estimating it?

The correction above uses the true routing probability. In the machine-feedback
literature that is available: an acquisition function is designed and its form
is known. Here nobody wrote the rule down.

`estimate.py` recovers π(s) by isotonic regression of the review indicator on
confidence, fitted in both directions so the intended policy is not assumed.
Three arms on identical data — uncorrected, corrected with the true policy,
corrected with a policy estimated from a pilot:

| Pilot decisions | Uncorrected | Oracle | Estimated | Gap | Policy error |
|---:|---:|---:|---:|---:|---:|
| 100 | 89.3% | 16.0% | 26.0% | +10.0% | 0.112 |
| 200 | 89.3% | 16.0% | 24.0% | +8.0% | 0.091 |
| 400 | 89.3% | 16.0% | 22.0% | +6.0% | 0.076 |
| **800** | 89.3% | 16.0% | **18.0%** | **+2.0%** | 0.060 |
| 1,600 | 89.3% | 16.0% | 14.0% | −2.0% | 0.053 |

**The gap closes monotonically and is gone by roughly 800 observed routing
decisions** — a pilot an organisation can actually run. The method does not
require knowing the rule, only observing it for a while.

The uncorrected and oracle arms are flat across pilot size because neither uses
the pilot. That flatness is a check, not a coincidence: an earlier version drew
the pilot from the same random stream as calibration, so a larger pilot shifted
every subsequent draw and the oracle appeared to move with a quantity it does
not depend on. The confound is invisible unless something varies that should
not.

## Where the correction genuinely fails

The estimator assumes routing depends on confidence alone. Real reviewers also
route on case value, client and workload. Where such a driver correlates with
correctness but is invisible to the estimator, the weights are wrong in a way
more data cannot fix — an omitted-variable problem, not a sample-size one.

Measured by introducing exactly that driver:

| Unobserved share of routing | Uncorrected fails | Corrected fails | Corrected exposure |
|---:|---:|---:|---:|
| 0% | 90.0% | 19.2% | 165 |
| 15% | 96.7% | 22.5% | 140 |
| 30% | 99.2% | 25.0% | 116 |
| 50% | 100.0% | 18.3% | 83 |
| 70% | 100.0% | **11.7%** | **49** |

**Read the last two columns together.** The violation rate appears to improve
past 30%, which is not the correction working — it is the correction refusing
to auto-accept anything. Exposure falls from 165 cases to 49, a 70% collapse,
and the violation rate is being computed on what little remains.

A threshold that accepts almost nothing has an excellent violation rate and no
value. That failure mode appeared once already in this project, as a threshold
search that returned "accept nothing" and reported perfect coverage; it
reappears here disguised as a success. Exposure is now reported beside every
violation rate for that reason.

**So the honest limit:** the correction holds while routing is substantially
driven by the confidence signal, and degrades into uselessness — not into
visible failure — once an unobserved driver dominates. Detecting that in
deployment requires monitoring exposure, not coverage.

## Why a reviewer would behave that way

The routing policies above are stipulated. `reviews_high_stakes` breaks the
guarantee, but nothing so far explains why anyone would route that way.
`src/doubt/reviewer.py` derives it.

**The organisation's objective wants low-confidence cases reviewed**: expected
value of review is `v · P(error|s) · q`, which falls in confidence.

**The reviewer faces a second term.** On a high-stakes case, having reviewed is
protective whether or not an error was present, because the question afterwards
is "did you check" rather than "was checking warranted":

    V_rev(s, v) = β · v · P(error|s) · q  +  γ · v · a

The insurance term depends on stakes alone, not on P(error | s). As it grows,
routing tracks stakes rather than confidence — and because **stakes and
confidence are positively correlated** in document work (large contracts are
more boilerplate, not less), routing on stakes becomes routing on confidence.

| Insurance weight | Accountability | Confidence gradient | Breaks? |
|---:|---:|---:|:---:|
| 0.0 | any | −1.6% | no |
| 0.6 | 1.0 | +19.5% | yes |
| 1.2 | **0.0** | **−1.6%** | **no** |
| 1.2 | 1.0 | **+51.8%** | yes |

Two predictions follow that the bare hypothesis does not make:

**Process-based accountability protects.** At `a = 0` the gradient stays
negative however strong the insurance motive. That is surprising and
actionable — it implies an organisation can fix a statistical problem by
changing how it evaluates reviewers rather than by changing the model.

**The failure has a boundary.** Where stakes and confidence are uncorrelated
the gradient is −12.7% and the guarantee is safe. The failure is not universal,
and a study that cannot separate the two cases cannot test the account.

Both moderators exist as natural variation across teams and workflows, so
neither needs manipulating — which is what makes them testable in a field
setting rather than only in a lab.

## What an accountability regime is worth

The two halves have run separately to here. `bridge.py` joins them: reviewers
are simulated from the decision model, their routing is fed into the risk-control
machinery, and the deployed outcome is measured under each regime.

Per million decisions, with the model, the cases and reviewer competence held
fixed — only the evaluation scheme differs:

| Arrangement | Guarantee fails | Error rate | Automated | Errors reaching production | Manual reviews |
|---|---:|---:|---:|---:|---:|
| Process-based | **6%** | 0.034 | **89%** | 30,146 | 111,914 |
| Outcome-based | 84% | 0.087 | 17% | 14,543 | **832,843** |
| Outcome-based + correction | 21% | 0.034 | 16% | **5,317** | — |

**Reporting any single column recommends the wrong thing.** Total errors alone
picks outcome-based — the regime that breaks its guarantee. Violation rate
alone picks process-based — the regime that automates most and therefore lets
more absolute errors through. Both readings are true and neither is sufficient.

The structure underneath: **outcome-based accountability does not merely break
the guarantee, it destroys the automation case.** 832,843 manual reviews per
million decisions means reviewers are hand-checking 83% of the work. The
statistical correction restores the error rate and cannot restore throughput,
because reviewer behaviour is what consumed it.

That is a managerial result and it exists only because both halves sit in one
model. The methods half has no theory of where routing comes from; the
behavioural half has no machinery for turning routing into risk. Two papers
citing each other would not produce this table.

Costs are reported in counts rather than currency throughout. What a wrong
decision costs varies by orders of magnitude across the settings this could
apply to and would be the weakest number in the analysis; the count is
defensible and the valuation belongs to whoever deploys.

## What is and is not established

**Established by simulation**, which is the appropriate use of simulation for
a claim about a statistical procedure: coverage can only be checked against a
known ground truth. Split conformal loses coverage under confidence-dependent
routing; the loss is monotone in routing intensity; a weighted correction
restores it at a measurable cost in exposure.

**Not established.** That real reviewers route this way. The policies here are
stipulated, not observed. Whether the `reviews_high_stakes` pattern occurs in
practice — and how strongly — is an empirical question about human behaviour
that this repository cannot answer.

That question is the other half of the project, and it needs an organisation.
[`docs/preregistration.md`](docs/preregistration.md) specifies the design
before any data exists, because a shift-robust procedure discovered after
seeing deployment data is not a method contribution.

## Drift: the behavioural prediction creates a methods requirement

Every procedure above assumes the routing policy is fixed. The behavioural half
says it is not — reviewers who see a confidence display learn from it, and the
insurance motive driving the damaging pattern weakens as they come to trust the
signal. Simulated from the reviewer model:

| Week | Confidence gradient |
|---:|---:|
| 1 | **+53.0%** |
| 4 | +43.3% |
| 8 | +19.0% |
| 12 | +2.3% |
| 16 | **−1.5%** |

**A procedure calibrated in week one is solving week one's problem.** Four
procedures over sixteen weeks, with outcomes arriving through a 15% audit
sample rather than an oracle:

| Procedure | Weeks failing | Mean risk | Exposed |
|---|---:|---:|---:|
| Fixed | 26.7% | 0.043 | 392 |
| Periodic refit | 15.2% | 0.022 | 383 |
| Adaptive (ACI-style) | **35.5%** | 0.047 | 394 |
| **Guarded** | **4.8%** | 0.005 | 363 |

**Unguarded online adaptation loses to doing nothing.** At realistic audit
rates the feedback is a handful of errors in a few dozen sampled cases, and a
proportional update chases that noise. Sweeping the audit rate confirms the
diagnosis — 39.6%, 37.3%, 33.5%, 28.5% at 5%, 15%, 40% and 100% audit — and
shows that even with full outcome feedback it only ties the fixed threshold.

**The confidence guard is what matters, not the adaptation frequency.**
Periodic and guarded both move only when a Clopper-Pearson bound clears the
target; adaptive moves on every observation. Adapting weekly *with* a guard
beats both refitting quarterly and adapting without one.

### The accept-nothing failure, third appearance

The first guarded update raised the threshold quickly and lowered it only when
the bound fell below α/2. It ratcheted monotonically and finished the
deployment auto-accepting **14 cases out of 600** — a 4.8% violation rate
achieved by refusing to do anything.

It survived two tests written about exactly that failure mode, because both
were scoped to other modules. The update is now symmetric in the bound, and
exposure is reported beside every violation rate in this repository for the
same reason.

## The empirical half

[`docs/preregistration.md`](docs/preregistration.md) — the design, fixed before
any data exists, because a shift-robust procedure discovered after seeing
deployment data is a description of one dataset rather than a method.

[`docs/theory.md`](docs/theory.md) — what is proved, what is conjectured, and
what is assumed. Proposition 2 is Tibshirani et al. (2019) with our weights
substituted and is marked as such; Proposition 3, the estimated-policy case, is
conjectured and is where the human setting departs from the machine one.

**The power calculation changed the design.** An earlier draft asserted 40
reviewers and 12 weeks. Computed, that gives **11% power** — because the
hypothesis is an interaction, which costs four times the sample of a main
effect, and because clustering at the reviewer is severe.

The structural fact: effective sample tends to **reviewers ÷ ICC** and stops.
Two million decisions across forty reviewers carry the information of eight
hundred. **The binding resource is reviewers, not decisions**, so a firm with
enormous case volume and a small review team cannot buy power by running
longer.

Revised: 60+ reviewers for a fifteen-point effect, and the study should not be
run below 26 under any assumption tested. The theory predicts a gradient swing
above fifty points, so powering for fifteen is conservative rather than
optimistic.

## Reproducing

```bash
pip install -e ".[dev]"
pytest -q
python -c "
from doubt.shift import RoutingPolicy, run_experiment
print(run_experiment(RoutingPolicy('reviews_high_stakes', 1.0)).as_dict())"
```

No dependencies. 27 tests, 98% coverage.

## License

MIT.
