# Independent audit of the fixed-cohort PHD stability study

Status: passed, 2026-10-02. No discrepancy requiring a result correction was found.
This is an aggregate-only audit note. Detailed local evidence was read but is
neither copied here nor included in the accompanying aggregate audit JSON.

## Findings independently reproduced

- All 32 original pairs, 128 text-condition cells, and 20 declared seeds are
  present. The 102 distinct clouds and 26 identical-window reuses are correctly
  counted. The reused reports are identical, rather than treated as new estimates.
- Matched-window dimension gap: mean 1.065777, across-seed SD 0.553076, full range
  [-0.560405, 1.707519], with 1 of 20 cohort means negative and 18 of 32 individual
  pair signs varying. The matched-window slope gap remains positive across all
  20 schedules, ranging from 0.014529 to 0.026442.
- Original-window dimension gap: mean 1.587709, seed SD 0.357748, full range
  [0.990200, 2.168167]. All 20 cohort means are positive.
- All 2,560 final estimates are finite; none has mean slope outside [0,1),
  negative dimension, or dimension below 2. All 22 final dimensions above 18 are
  retained. Of 7,680 individual rerun slopes, 20 exceed 1 and have negative
  individual reciprocal transforms. Counting unique clouds once yields 12 of
  6,120 such rerun slopes and 13 of 2,040 final dimensions above 18.
- Matched-window dimension cohort MC variance is 0.305893 with covariance, versus
  0.202106 under the hypothetical independent-pair calculation. Ignoring the
  observed cross-pair covariance would understate this variance; the ratio is
  1.513526. Original-window values are 0.127983 and 0.091188, ratio 1.403509.
- The independently rebuilt 10,000-by-20 matched-dimension composition table
  yields variance fractions of 31.2267% pair composition, 42.3869% seed, and
  26.3864% interaction. The fractions and their exact sum-to-total identity
  reproduce the report. All 12 condition/metric/domain decompositions and
  empirical ranges also reproduce.

## Checks performed

The replay uses saved numeric evidence without importing the author's analysis
or runner. It does not load the encoder, read source texts, compute MSTs, acquire
new data, launch new measurements, or write to any remote destination.

It checks all saved median-energy and slope arithmetic, individual and final
reciprocal transforms, every per-text distribution and CSV copy, delta-method
diagnostics, length-bin statistics and correlations, pair contrasts, seed means,
full cross-pair covariance effects, finite-MC heterogeneity corrections, and
composition/seed/interaction variance components. Maximum centered-versus-saved
slope discrepancy is approximately 1.28e-12.

It independently reconstructs all 1,060 distinct N-by-seed subset-plan hashes
using the declared NumPy child-seed procedure. Equal-N clouds have identical
index schedules at a given seed. This induces shared computational randomness;
it does not align token meanings. The aggregate analysis retains observed
cross-pair covariance. Bootstrap compositions retain each complete seed vector
and preserve the 16-pair composition within each domain.

The protocol and two frozen source hashes agree with the run manifest. All 47
baseline non-runtime pilot files are unchanged, including prior results; model
asset hashes and the pinned revision match. All 128 stored cloud hashes and
lengths agree with the pilot. The study reports completion within its declared
resource limits, and its retained counters are consistent with those limits.

All 11 files named by the aggregate-release allowlist are present, with matching
manifest hashes where supplied. The released JSON equals the audited aggregate
projection and contains no document identifiers or per-document numeric rows.
The independent audit did not modify the original study or its release bundle.

## Interpretation and boundaries

The central conclusion is supported: the reciprocal transform substantially
amplifies computational variability and the matched-window cohort dimension gap
is not sign-stable over the declared schedules, while the cohort slope gap is
positive on every observed schedule. Below the pole, the transform preserves an
individual pair's sign; averaging transformed pair values can change the cohort
sign because nonlinear magnification differs by pair. Mean transformed values
and the transform of a mean slope are correctly kept distinct.

The retained report appropriately avoids treating these descriptive seed ranges
or empirical pair-composition ranges as population confidence intervals. One
negative result among 20 is an observed count, not a calibrated 5% reversal risk.
The fixed 32 pairs were already exposed; this provides neither fresh held-out
validation nor a detector benchmark. Twenty schedules do not establish rare-tail
behavior or finite-moment convergence. Matched re-encoding changes context as
well as N, so finite-N bias and causal effects of length are not identified.
Encoder, generator, source-corpus and domain shifts remain unmeasured.

Cloud verification here means correspondence of saved hashes plus inspection of
the runner's enforced re-encoding checks; the audit did not recreate cloud bytes.
Content hashes establish current identity, not independent proof of chronology
or absence of unrecorded prior runs. Historical runtime and network claims rely
on retained execution records and code, rather than external telemetry. The
aggregate-only release cannot independently reconstruct withheld per-text data.

## Local replay artifacts

- `independent_phd_stability_audit.py`: standalone saved-evidence replay
- `independent-phd-stability-audit.json`: aggregate-only verification results

Run the replay with the pilot's existing Python runtime and installed NumPy/SciPy.
The script takes optional `--study` and `--output` paths. It writes only its new
aggregate audit output and leaves all input artifacts unchanged.
