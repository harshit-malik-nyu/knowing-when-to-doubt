# Theory

What is proved, what is conjectured, and what is assumed. The simulations in
this repository measure; this document states what they are measuring and
which parts follow from existing results rather than from new argument.

Nothing below is a complete proof. Each proposition carries a sketch and names
the result it reduces to. The distinction between "follows from Tibshirani et
al. with a substitution" and "requires new argument" is the honest content of
a theory section, and it is marked explicitly.

---

## 1. Setup

Cases arrive as $(X_i, Y_i)$ with $Y_i \in \{0,1\}$ indicating whether the
model's output is correct. A scoring function produces a confidence
$S_i = s(X_i) \in [0,1]$.

A threshold $\lambda$ partitions cases: those with $S_i \ge \lambda$ are
candidates for automatic acceptance, the rest go to review.

**Selective risk** is the error rate among cases that reach production
untouched:

$$R(\lambda) = \Pr\big(Y = 0 \mid S \ge \lambda,\ \text{not reviewed}\big)$$

The guarantee sought is $R(\hat\lambda) \le \alpha$ with probability at least
$1-\delta$ over the calibration draw.

**The routing policy** is $\pi(s) = \Pr(\text{reviewed} \mid S = s)$. In the
machine-feedback literature $\pi$ is designed and known. Here it is a
description of human behaviour.

---

## 2. Proposition 1 — split conformal loses coverage

**Statement.** Let $\hat\lambda$ be chosen by split conformal risk control on a
calibration sample drawn before deployment, so that $\Pr(Y=0 \mid S \ge
\hat\lambda) \le \alpha$ holds on that sample. If routing depends on the
score — $\pi$ non-constant — then in deployment

$$R(\hat\lambda) = \frac{\mathbb{E}\big[(1-\pi(S))\,\mathbf{1}\{S \ge \hat\lambda\}(1-Y)\big]}{\mathbb{E}\big[(1-\pi(S))\,\mathbf{1}\{S \ge \hat\lambda\}\big]}$$

and this exceeds $\alpha$ whenever $\pi$ is positively associated with $Y$
given $S \ge \hat\lambda$.

**Sketch.** A case reaches production iff it clears the threshold *and* the
reviewer declines it, which occurs with probability $1-\pi(S)$. The deployed
population is therefore the calibration population reweighted by that factor.
Writing the conditional error rate under the reweighted measure and comparing
to the unweighted version gives a difference with the sign of
$\operatorname{Cov}\big(1-\pi(S),\ 1-Y \mid S \ge \hat\lambda\big)$.

When reviewers preferentially check cases the model gets *right*, $\pi$ and
$1-Y$ are positively associated, the covariance is negative, and the exposed
residue is enriched in errors. **This is the mechanism, and it is elementary
once written down.** It is stated because it makes the sign prediction sharp:
the failure direction is determined by the association between routing and
correctness, not by routing intensity alone.

**What the simulation adds.** The magnitude. The expression above is exact but
uninformative without knowing $\pi$ and the joint distribution; the
measurements report what it comes to under plausible policies — up to 90%
violation rates at a 5% target.

---

## 3. Proposition 2 — weighting restores coverage when $\pi$ is known

**Statement.** Let $w(s) = 1 - \pi(s)$ and suppose $w(s) > 0$ for all $s$ in
the support. Then the weighted risk estimate

$$\hat R_w(\lambda) = \frac{\sum_i w(S_i)\,\mathbf{1}\{S_i \ge \lambda\}(1-Y_i)}{\sum_i w(S_i)\,\mathbf{1}\{S_i \ge \lambda\}}$$

is consistent for the deployed selective risk, and a threshold chosen by upper
confidence bound on $\hat R_w$ controls $R$ at level $\alpha$.

**Sketch.** This is **weighted conformal prediction under covariate shift**
(Tibshirani, Barber, Candès, Ramdas, 2019) with the likelihood ratio between
deployment and calibration measures equal to $w(s)/\mathbb{E}[w(S)]$. The
substitution is immediate because the shift here is exactly a known reweighting
of the covariate distribution.

**This proposition is not new.** It is their result with our weights
substituted in. Saying so is more useful than presenting it as a contribution,
and it locates precisely where the new work begins: everything above holds for
machine feedback too.

**Where it needs care.** The effective sample size is not $n$. Weighting
concentrates information in the region where $w$ is large, and the appropriate
count is Kish's

$$n_{\text{eff}} = \frac{\big(\sum_i w_i\big)^2}{\sum_i w_i^2}$$

Using $n$ in the concentration bound claims precision the weighting does not
deliver. The implementation uses $n_{\text{eff}}$; substituting $n$ produces a
threshold that looks calibrated and is not.

---

## 4. Proposition 3 — estimated policies, and where the new work is

**Statement (conjectured).** Let $\hat\pi$ be an estimate of $\pi$ with
$\|\hat\pi - \pi\|_\infty \le \varepsilon$ and let $\hat w = \max(\eta,
1-\hat\pi)$ for a clipping floor $\eta > 0$. Then the coverage gap is bounded
by a quantity of order $\varepsilon / \eta$, up to a constant depending on the
error rate.

**Status: conjectured, not proved.** The form follows from standard sensitivity
arguments for inverse-probability weighting, and the $\varepsilon/\eta$ shape is
what the clipping floor buys — bias in exchange for bounded variance. A proof
would need the estimation error to be handled jointly with the concentration
bound rather than sequentially, which is the technical work this document does
not do.

**What the measurements say.** The gap to the oracle closes monotonically in
pilot size — 10.0, 8.0, 6.0, 2.0, −2.0 percentage points at $n_{\text{pilot}}$
of 100 to 1,600 — and mean absolute policy error falls from 0.112 to 0.053 over
the same range. That is consistent with the conjectured rate and does not
establish it.

**This is where the human case departs from the machine case**, and it is the
only place it does:

| | Machine feedback | Human routing |
|---|---|---|
| $\pi$ | designed, known exactly, $\varepsilon = 0$ | estimated, $\varepsilon > 0$ |
| Stability | fixed by construction | drifts as reviewers learn |
| Status | nuisance | the behavioural object of interest |

Proposition 2 covers machine feedback completely. Proposition 3 is required for
human routing and is the contribution.

---

## 5. Assumption A — routing depends on the score alone

Everything above assumes $\pi(s) = \Pr(\text{reviewed} \mid S = s)$: that
routing is a function of the displayed confidence and nothing else.

**This is false in practice** and the failure is not gentle. Where reviewers
also route on an unobserved $Z$ correlated with $Y$, the weights are wrong by
a factor no sample size corrects — an omitted-variable problem, not an
estimation one.

Measured in `estimate.py`: as the unobserved share of routing rises to 70%, the
apparent violation rate *falls* to 11.7% while exposure collapses from 165
cases to 49. The correction does not visibly fail. It quietly stops accepting
anything.

**Detection therefore requires monitoring exposure rather than coverage**,
which is the operational recommendation that falls out of the theory rather
than out of intuition.

---

## 6. What a full paper would need

Stated plainly so the gap is legible:

1. **Proposition 3 proved**, with the estimation error and the concentration
   bound handled jointly.
2. **A minimax statement** on how much unobserved routing is tolerable before
   no procedure controls risk — Assumption A is currently binary, and the
   interesting version is quantitative.
3. **Drift, formally.** Reviewers learn, so $\pi$ is a moving target.
   `drift.py` measures four procedures under a drifting policy and finds that
   unguarded online adaptation loses to a fixed threshold, while the same
   update gated on a Clopper-Pearson bound beats both. What is missing is the
   statement: a regret or coverage bound for the guarded procedure under
   bounded drift rate. Adaptive Conformal Inference (Gibbs and Candès, 2021)
   provides the template, and the complication here is that feedback arrives
   on an audit sample rather than in full — so the bound must account for
   estimation noise in the signal driving adaptation, which is the same
   difficulty as Proposition 3 in sequential form.
4. **Real routing data.** Every $\pi$ in this repository is stipulated or
   recovered from stipulated behaviour. The pre-registration exists to obtain
   one that is not.
