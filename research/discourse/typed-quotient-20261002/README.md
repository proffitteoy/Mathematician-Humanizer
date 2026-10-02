# Typed discourse quotient and model-facing measurement contract

A retrospective research artifact on the same exposed GCDT calibration panel. It defines a narrow, typed quotient with proofs and counterexamples, tests it, and reports aggregate residual annotation sensitivity. It does not train a parser/model, infer coherence or human/AI effects, or claim fresh held-out validation.

Read in this order:

1. `THEORY_AND_MODEL.md`: the object, admissible equivalences, proof, prohibited simplifications, observables, and multi-view learning implications
2. `CALIBRATION_REPORT.md`: aggregate results and their limitations
3. `PROTOCOL.md`: definitions and transparent post-replay clarification log
4. `typed_quotient.py`: standard-library implementation and 13 explicit synthetic tests
5. `aggregate_results.json`: aggregate replay results only
6. `INDEPENDENT_REVIEW.md`, `independent_randomized_review.py`, and `independent_randomized_review_results.json`: separate 2,000-case synthetic implementation review

`PROTOCOL_PRE_REPLAY.md` preserves the initial protocol wording. Any independent synthetic stress-test files listed in the publication manifest provide additional verification, not a new empirical validation set.

Core result: ID/declaration invariance is unconditional; unary-span identity contraction requires an explicit convention. Preserving genuine hierarchy matters: nested multinuclear scope, relation direction/nuclearity, and source tag types must not be flattened away. Canonicalization removes specified encoding redundancy without establishing annotation agreement or a content-free style representation.

The private source cache is deliberately not included. Public artifacts contain theory, code, protocols, synthetic examples, and aggregates only. No document-score rows, source prose, sentence hashes, paragraph vectors, or full annotations are included. Original frozen results are preserved unchanged.
