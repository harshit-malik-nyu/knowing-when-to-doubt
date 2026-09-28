# Pre-registration: does calibration change what reviewers do?

**Status: written before any data exists, and before any partner is engaged.**

This document exists because the methods half of the project is unpublishable
otherwise. A shift-robust procedure discovered after seeing deployment data is
not a method contribution — it is a description of one dataset. Fixing the
analysis in advance is what separates the two.

It is also the document a partner organisation has to agree to before rollout,
because the rollout structure is what determines whether anything can be
identified at all. That conversation has to happen roughly a year before the
data exists.

---

## 1. The question

Reviewers working alongside a model see a confidence score. Does the **quality**
of that score change how they rely on the model — and does that change decision
outcomes?

The distinction from existing work matters. Algorithm-aversion research
measures **whether** people use algorithmic advice. Dietvorst et al. showed
people abandon algorithms after seeing them err. What has not been measured is
whether people override the **right** predictions.

A well-calibrated signal should produce *selective* reliance: defer when the
model is confident, intervene when it is not. A poorly calibrated signal should
produce blanket trust or blanket rejection, because there is nothing to
discriminate on.

## 2. Where the hypotheses come from

A hypothesis without a mechanism is a guess with a p-value attached. The
predictions below are derived from a decision problem the reviewer is actually
facing, implemented in `src/doubt/reviewer.py`.

**The organisation wants low-confidence cases reviewed.** Expected value of
review is `v · P(error | s) · q`, which falls in confidence. That is the
intended policy and it makes deployment safer than calibrated.

**The reviewer faces something else.** Their value has a second term:

    V_rev(s, v) = β · v · P(error|s) · q  +  γ · v · a

The second term is **insurance**. On a high-stakes case, having reviewed is
protective whether or not an error was present, because the question asked
afterwards is "did you check" rather than "was checking warranted". `a` is the
accountability regime — high where reviewers are judged on outcomes, low where
judged on process.

**The insurance term does not depend on P(error | s).** It depends on stakes
alone. As `γ·a` grows, routing is driven by stakes rather than confidence.

That alone would make routing independent of the signal, which is harmless. The
damage comes from an empirical regularity: **stakes and confidence are
positively correlated**, because high-value documents in most workflows are
standard-form and well-represented in training data. A large contract is more
boilerplate than a small one, not less. Where that holds, routing on stakes is
routing on confidence, and the reviewer checks exactly the cases the model was
most likely to get right.

Simulated from the model, the confidence gradient in review rates:

| Insurance weight γ | Accountability | Gradient | Breaks the guarantee? |
|---:|---:|---:|:---:|
| 0.0 | any | −1.6% | no |
| 0.6 | 0.5 | +2.9% | yes |
| 0.6 | 1.0 | +19.5% | yes |
| 1.2 | 0.0 | −1.6% | **no** |
| 1.2 | 1.0 | **+51.8%** | yes |

And the boundary, sweeping how strongly stakes track confidence:

| Stakes–confidence correlation | Gradient | Breaks? |
|---:|---:|:---:|
| 0.00 | −12.7% | no |
| 0.25 | +3.2% | yes |
| 0.50 | +28.0% | yes |
| 1.00 | +77.2% | yes |

## 2b. Hypotheses

Stated in the direction predicted, with the null that would falsify each.

**H1 (selective reliance).** Reviewers shown a well-calibrated confidence
signal will override low-confidence predictions at a higher rate than
high-confidence ones, relative to reviewers shown a poorly calibrated signal.
*Null: the interaction between confidence and display condition is zero.*

**H2 (outcome quality).** Overrides under a calibrated signal will more often
be *correct* overrides — changing a wrong prediction rather than a right one.
*Null: override correctness does not differ by condition.*

**H3 (the routing prediction, from the methods half).** Reviewers will route
disproportionately toward **high-confidence** cases when case stakes are high,
independent of the confidence signal.
*Null: routing is independent of stakes conditional on confidence.*

**H4 (the moderator).** The confidence gradient in routing will be more
positive in teams under outcome-based accountability than under process-based
accountability. *Null: accountability regime does not moderate the gradient.*

**H5 (the boundary).** The confidence gradient will be more positive in
workflows where case stakes and model confidence are positively correlated.
*Null: the stakes–confidence correlation does not moderate the gradient.*

H4 and H5 are what make the theory falsifiable rather than merely consistent.
H3 alone could be produced by many mechanisms — salience, laziness, distrust.
The insurance account uniquely predicts that **process-based accountability
protects the guarantee**, which is both surprising and actionable: it implies
an organisation can fix a statistical problem by changing how it evaluates
reviewers rather than by changing the model.

Both moderators exist as natural variation across teams and workflows in most
firms, so neither requires manipulation.

H3 is the one that connects the halves. The simulation in `src/doubt/shift.py`
shows that if H3 holds, deployed risk exceeds its calibrated target. If H3 is
false, the methods contribution describes a failure mode that does not occur,
and that is worth knowing and worth reporting.

## 3. Design

**Staggered rollout of a confidence display across review teams.** The
underlying model is identical throughout; only the uncertainty signal changes.
This isolates the calibration channel from the capability channel, which is the
confound that has left the existing literature inconclusive.

Three arms:

| Arm | What reviewers see |
|---|---|
| Control | model prediction, no confidence |
| Raw | prediction plus the model's raw confidence score |
| Calibrated | prediction plus a conformally calibrated risk band |

**Unit of analysis:** the individual decision.
**Clustering:** at the reviewer. Reviewers see many cases and their
idiosyncrasies are not independent across them.
**Assignment:** at the team-week level, by the partner, on a schedule fixed in
advance.

## 4. What must be true for identification, and what breaks it

**Rollout order must be as-good-as-random with respect to reviewer skill and
case difficulty.** If the partner deploys to their strongest team first —
which is the natural instinct — identification is gone and no analysis
recovers it.

This is the single most likely point of failure and it is organisational, not
statistical. The partner agreement must specify the order before anyone writes
code.

**Pre-period data is required.** At least eight weeks of decisions before any
team sees a confidence display, to establish baseline override rates and to
test parallel trends.

**Contamination must be monitored.** Reviewers talk. If treated and untreated
teams share a floor, the control arm is not clean, and that has to be measured
rather than assumed away.

## 5. Analysis, fixed in advance

Two-way fixed effects with reviewer and week effects, standard errors clustered
at the reviewer.

The primary specification is the interaction between model confidence and
treatment arm on override probability. The secondary is the same interaction on
override *correctness*, which requires ground truth and is therefore restricted
to cases with an adjudicated outcome.

**Deviations that would be tempting and are ruled out here:** dropping the
first treated week, excluding reviewers below a volume threshold, winsorising
override rates, and analysing only cases where the model and human disagreed.
Each is defensible in isolation and each is a degree of freedom. If any is
taken it will be reported as a deviation with the pre-specified result shown
alongside.

## 6. Power — computed, and it changed the design

An earlier draft of this document said "roughly 40 reviewers and 12 weeks".
That number was asserted. Computing it (`src/doubt/power.py`) shows it gives
**11% power**, not 80%, and the correction changes what the study should be.

### Why it is so much worse than it looks

Two multiplicative problems.

**The hypothesis is an interaction.** Whether the confidence gradient differs
by arm is a difference of differences, and its standard error is roughly twice
that of a main effect — a factor of four in sample. At 40 reviewers and a
five-point effect, power is 33% if this were a main effect and **11%** for the
interaction actually being tested. Computing power for a main effect and then
testing an interaction is the most common way this class of study produces an
uninformative null.

**Observations cluster at the reviewer, who sees hundreds of cases.** The
design effect is 1 + (m−1)·ICC and it scales with cluster size, so 19,200
decisions carry the information of **770**.

### The structural fact that decides the study

As decisions per reviewer grows, effective sample tends to **reviewers ÷ ICC**
and stops:

| Decisions per reviewer | Total decisions | Effective n |
|---:|---:|---:|
| 50 | 2,000 | 580 |
| 400 | 16,000 | 764 |
| 5,000 | 200,000 | 797 |
| 50,000 | 2,000,000 | **800** |

Two million decisions and forty reviewers yield eight hundred
independent-equivalent observations. **The binding resource is reviewers, not
decisions**, and a firm with enormous case volume and a small review team
cannot buy its way to power by running longer. A design that plans to extend
the study period is solving the wrong constraint.

### Reviewers required, twelve weeks

| Effect | ICC 0.02 | ICC 0.05 | ICC 0.10 |
|---:|---:|---:|---:|
| 5 points | 233 | 549 | 1,075 |
| 8 points | 91 | 215 | 420 |
| 10 points | 59 | 138 | 269 |
| **15 points** | **26** | **61** | **120** |
| 20 points | 15 | 35 | 68 |

### What this means, and why the study is still worth running

**It cannot detect small effects.** A five-point interaction needs a reviewer
pool most firms do not have, and a null result at that magnitude would be
uninformative rather than evidence of absence. The pre-registration says so
now rather than discovering it in the discussion section.

**The theory predicts a large effect.** The reviewer model puts the confidence
gradient at −1.6% under process-based accountability and +51.8% under
outcome-based — a swing of more than fifty points. Powering for fifteen points
is therefore powering for roughly a third of the predicted effect, which is
appropriately conservative rather than optimistic.

**Revised requirement: 60+ reviewers at ICC 0.05, or 26 if the ICC proves
low.** The ICC should be estimated from pre-period data before the partner
commits, because it moves the requirement by a factor of four and is never
known in advance.

**Below 26 reviewers the study should not be run** under any assumption in the
table above. That is the gate, and it is stricter than the number this document
originally carried.

## 7. What the partner must provide, and what they get

**Required:** rollout order fixed in advance; eight weeks of pre-period data;
per-decision logs including model output, displayed confidence, reviewer
action, and adjudicated outcome where available.

**Offered:** the calibrated risk band itself, which is useful to them
independent of the study; a measured answer to whether their reviewers rely on
the model selectively; and the shift-corrected threshold, which on the
simulation results is worth a large reduction in deployed error rate if their
reviewers route on stakes.

**Not offered:** any claim about individual reviewer performance. The analysis
is at the population level and the agreement should say so, because a study
that can be read as monitoring will change the behaviour it measures.

## 8. What would make us abandon it

- No partner with 26+ reviewers (60+ unless the ICC proves low) and
  adjudicated outcomes within nine months
- A partner unwilling to fix rollout order in advance
- Pre-period data showing override rates already trending differentially
- H3 clearly false in the pre-period, which would mean the methods half
  addresses a failure mode that does not occur

The last one is worth stating plainly: the behavioural result could invalidate
the premise of the methods result. Both authors have agreed in advance to
report that outcome rather than reframe it.
