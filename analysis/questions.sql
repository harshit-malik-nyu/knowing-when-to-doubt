SELECT policy,intensity,trials,naive_violation,weighted_violation,weighted_violation-naive_violation violation_change FROM observations ORDER BY policy,intensity;
SELECT policy,MAX(naive_risk) worst_naive_risk,MAX(weighted_risk) worst_weighted_risk FROM observations GROUP BY policy ORDER BY policy;
