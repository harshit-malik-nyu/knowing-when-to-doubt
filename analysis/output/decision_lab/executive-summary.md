# Recalibrate routing before reallocating scarce specialist review

Freeze the routing policy and certify on the corresponding exposed population before reducing review coverage. Keep shift monitoring in the operating cost.

**Observed evidence:** Historical weighted Kish pseudo-count bounds are heuristic. The newer known-policy certification uses retained Bernoulli observations and simultaneous bounds under explicit routing assumptions.

**Decision owner:** Quality operations manager (proposed role, not a client).

**Base planning case:** Frozen calibrated routing plus drift audit. This is conditional on the assumptions, not deployment approval.

| Alternative | Economic cost | Cash outlay | Reviewer hours | Passes risk and capacity |
|---|---:|---:|---:|---|
| Uniform 30% specialist review | $142,500 | $0 | 1,500.0 | True |
| Frozen calibrated routing plus drift audit | $139,417 | $14,000 | 1,333.3 | True |
| Confidence routing without recalibration | $134,000 | $4,000 | 500.0 | False |

Economic cost includes valued staff capacity and scenario incident losses. Cash outlay excludes salaried capacity and contingent losses. These are not realized savings.

**Sensitivity across 27 equally enumerated scenarios:** Uniform 30% specialist review: 4, NO FEASIBLE OPTION: 21, Frozen calibrated routing plus drift audit: 2. Grid counts are not probabilities.

**Synthetic product experiment:** HOLD. Primary effect 1.7%; 95% interval [-2.1%, 5.6%]. Guardrail effect 1.3%; interval [0.7%, 2.2%]. These numbers test the decision logic, not product performance.

**Priority order:**

1. Separate policy development, calibration and exposed-risk evaluation.
2. Reserve reviewer capacity for drift audits, not just the routed queue.
3. Recalibrate after a routing change instead of reusing a historical certificate.

**What would reverse the recommendation:** If shift increases exposed incident risk beyond the gate, restore review coverage or stop automation even if aggregate accuracy stays constant.

**Remaining uncertainty:** Simulation validates conditional mechanics, not deployment exchangeability or reviewer behavior.
