# Job and review contract

The prepare command emits the shell. Fill it without changing original. candidates contains objects with id, text, intent, review. claims contains id, commitment, source_evidence. Every source_evidence is an exact excerpt, not a paraphrase. candidate_evidence accepts one exact string or a nonempty list of exact strings when support crosses sentences. Optional protected strings must exist in original. length_ratio_bounds is an editorial constraint, not a quality threshold. selection_preference lists candidate IDs in editorial order; selection_rationale states why.

Each candidate review has:

    {
      "reviewer_type": "independent_language_model",
      "binding_sha256": "hash computed below AFTER review of these exact texts",
      "verdict": "pass",
      "claims": [
        {"id": "claim-id", "status": "preserved", "candidate_evidence": "exact excerpt", "explanation": "Why the original proposition, including scope, is retained"}
      ],
      "added_claims": [],
      "issues": []
    }

Allowed claim statuses are preserved, changed, uncertain; only preserved can pass. Never convert changed or uncertain to preserved merely to release a final answer. Record a failure as fail. The tool verifies all claim IDs and exact evidence spans. It cannot verify that the explanation is true or that the declared reviewer is independent.

After an actual review, bind it with:

    import sys
    sys.path.insert(0, "scripts")
    from workflow import binding
    candidate["review"]["binding_sha256"] = binding(job, candidate)

The hash includes the exact original, genre, complete claim ledger, protected spans and candidate text. Any edit requires a new review and hash. Do not populate hashes for review judgments copied from a different candidate. Root report preserves separate raw independent review files for the worked examples.

No review means abstention. Missing POS/dependency models do not prevent a surface-only provisional rewrite, but the report must show the missing analyzer. No facts should be invented to make all 71 values available. Cached measurement files must match exact text hashes.
