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

## 2. Hypotheses

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

## 6. Power

Detecting a five percentage point change in override rate, at 80% power and
conventional significance, with clustering at the reviewer and an assumed
intra-reviewer correlation of 0.05, requires roughly **40 reviewers and 12
weeks**. Below about 25 reviewers the design cannot support the interaction
test and should not be run.

That number is the gate on whether a partner is viable, and it should be
checked before the conversation goes further than a first meeting.

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

- No partner with 25+ reviewers and adjudicated outcomes within nine months
- A partner unwilling to fix rollout order in advance
- Pre-period data showing override rates already trending differentially
- H3 clearly false in the pre-period, which would mean the methods half
  addresses a failure mode that does not occur

The last one is worth stating plainly: the behavioural result could invalidate
the premise of the methods result. Both authors have agreed in advance to
report that outcome rather than reframe it.
