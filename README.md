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
