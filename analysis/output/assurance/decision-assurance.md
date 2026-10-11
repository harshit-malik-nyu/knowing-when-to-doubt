# Decision assurance: knowing-when-to-doubt

Freeze the routing policy and certify on the corresponding exposed population before reducing review coverage. Keep shift monitoring in the operating cost.

**Evidence:** Historical weighted Kish pseudo-count bounds are heuristic. The newer known-policy certification uses retained Bernoulli observations and simultaneous bounds under explicit routing assumptions.

**Uncertainty:** Simulation validates conditional mechanics, not deployment exchangeability or reviewer behavior.

## Robustness of the assumed business case

| Alternative | Feasible grid cases / 27 | Worst regret when feasible | Maximum volume at fixed review capacity |
|---|---:|---:|---:|
| Uniform 30% specialist review | 6 | $9,750.00 | 26666 |
| Frozen calibrated routing plus drift audit | 6 | $7,125.00 | 29999 |
| Confidence routing without recalibration | 0 | No feasible case | 79999 |

**Robust minimax choice:** None. No option is feasible across the entire stress grid.

Finite assumed grid, not a probability distribution or protection outside the grid. Conditional regret never overrides feasibility. Null robust option means no unconditional recommendation. Cost regret is relative to the cheapest feasible option in that same scenario. Failure counts can overlap.

## Missing-outcome sensitivity

| Outcomes masked per arm | Primary effect bounds | Incident effect bounds | Every completion clears margins? |
|---|---:|---:|---|
| 0% | [1.7%, 1.7%] | [1.3%, 1.3%] | False |
| 5% | [-3.4%, 6.6%] | [-3.7%, 6.3%] | False |
| 10% | [-8.0%, 12.0%] | [-8.8%, 11.2%] | False |
| 20% | [-18.7%, 21.3%] | [-19.0%, 21.0%] | False |

These are identification bounds on deliberately masked synthetic outcomes, not confidence intervals or measured missingness. Failures and non-starters remain in the assigned denominator. Passing this sensitivity check would still require statistical and domain-quality gates.

## Domain measurement contract

**Decision:** Route uncertain cases while preserving a defensible error guarantee for the deployed policy.

**Primary outcome:** Accepted-decision error risk under the frozen routing policy, jointly reported with acceptance coverage and review burden.

**Denominator:** All eligible routed cases for coverage; accepted cases with the required valid labels for risk certification.

**Independent unit:** Independent source case; repeated observations and shared-source cases require dependence-aware design.

**Quality guardrail:** Known routing/retention mechanism, adequate calibration support and simultaneous threshold control.

**Minimum required data:** Case IDs, fixed routing policy, inclusion/retention probabilities, retained Bernoulli outcomes, labels, thresholds and calibration split.

**Missingness and failure handling:** Unknown or outcome-dependent retention invalidates the claimed guarantee. Do not substitute weighted pseudo-counts for actual retained trials.

**Release rule:** Use certification only under the stated known-policy assumptions. Weighted Kish bounds remain heuristic; otherwise return inconclusive.

**Reversal trigger:** Routing changes, probabilities become unknown, or shifted cases lack calibration support.

## Interview defense

**Why not use effective sample size as a certificate?**

A Kish effective size summarizes weighting. By itself it does not make weighted outcomes an exact binomial experiment.

**What changes the operating decision?**

A risk bound can rule out automation even when average accuracy looks good, sending those cases to review.

## Implementation handoff

1. Freeze the eligible population, denominator, outcome horizon and proposed decision owner before comparison.
2. Reconcile assignment and outcome records at the independence unit; classify missingness without deleting cases.
3. Estimate the domain outcome and its uncertainty separately from activation. Apply risk and capacity vetoes before comparing costs.
4. Record approve, hold, or reverse with the evidence version and violated gate. An unmeasured required domain gate means HOLD.

The supplied cluster-budget grid is a planning sensitivity check with assumed ICC. It is not an estimate from real clusters and does not guarantee joint power. No stakeholder approval or real experiment is asserted.
