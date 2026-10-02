#!/usr/bin/env python3
"""Synthetic identification/capacity checks. No text, downloads, or style claims.

Run: python synthetic_identifiability_tests.py --output results.json
Requires numpy, scipy, scikit-learn already installed in the execution environment.
"""
import argparse
import itertools
import json
import math
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import linprog, minimize_scalar
from sklearn.linear_model import LogisticRegression

RESULTS = {}


def design(cells):
    """Binary-factor additive design, with intercept."""
    return np.column_stack([np.ones(len(cells)), np.asarray(cells, float)])


def pair_connected(cells, i, j):
    edges = [(('l', c[i]), ('r', c[j])) for c in cells]
    vertices = set(sum(([u, v] for u, v in edges), []))
    seen = {next(iter(vertices))}
    while True:
        old = len(seen)
        for u, v in edges:
            if u in seen or v in seen:
                seen.update([u, v])
        if old == len(seen):
            return seen == vertices


def log_count_probability(n, k, p):
    """Log P(sum X = k) for stationary symmetric binary Markov chain."""
    dp = np.zeros((k + 1, 2))
    dp[0, 0], dp[1, 1] = .5, .5
    for _ in range(1, n):
        nxt = np.zeros_like(dp)
        nxt[:, 0] += p * dp[:, 0] + (1 - p) * dp[:, 1]
        nxt[1:, 1] += p * dp[:-1, 1] + (1 - p) * dp[:-1, 0]
        dp = nxt
    return math.log(dp[k].sum())


def log_conditional_order(sequences, p):
    n = sequences.shape[1]
    same = (sequences[:, 1:] == sequences[:, :-1]).sum(axis=1)
    return (math.log(.5) + same * math.log(p)
            + (n - 1 - same) * math.log1p(-p)
            - log_count_probability(n, n // 2, p))


def fit_stay(sequences):
    fit = minimize_scalar(lambda p: -log_conditional_order(sequences, p).sum(),
                          bounds=(.02, .98), method='bounded',
                          options={'xatol': 1e-8})
    assert fit.success
    return float(fit.x)


def balanced_markov(rng, p, count, n=32):
    """Exact rejection sampling from a Markov chain conditional on its bag."""
    rows = []
    while len(rows) < count:
        batch = max(64, (count - len(rows)) * 12)
        x = np.empty((batch, n), dtype=np.int8)
        x[:, 0] = rng.integers(0, 2, batch)
        for t in range(1, n):
            flip = rng.random(batch) > p
            x[:, t] = x[:, t - 1] ^ flip
        rows.extend(x[x.sum(axis=1) == n // 2])
    return np.asarray(rows[:count])


class IdentificationTests(unittest.TestCase):
    def test_01_exact_confounding_observational_equivalence(self):
        a = np.array([-1., -1., 1., 1.])
        s = a.copy()
        X = np.column_stack([np.ones(4), a, s])
        author_world = np.array([0., 1., 0.])
        source_world = np.array([0., 0., 1.])
        self.assertTrue(np.array_equal(X @ author_world, X @ source_world))
        self.assertEqual(np.linalg.matrix_rank(X), 2)
        cross = np.array([[1., 1., -1.]])
        self.assertNotEqual(float((cross @ author_world)[0]),
                            float((cross @ source_world)[0]))
        RESULTS['exact_confounding'] = {
            'design_columns': 3, 'rank': 2,
            'observed_predictions_identical': True,
            'unseen_crossed_cell_author_world': 1,
            'unseen_crossed_cell_source_world': -1,
            'conclusion': 'Observations cannot choose author vs source explanation.'}

    def test_02_invariance_tradeoff_exact_lp(self):
        # Variables q_as = P(predicted author=1 | A=a, S=s).
        # Each S is balanced; enforce identical predicted-label distributions.
        records = []
        for eps in [0., .05, .1, .25, .5]:
            p = np.array([(1-eps)/2, eps/2, eps/2, (1-eps)/2])
            a = np.array([0, 0, 1, 1])
            # Accuracy = P(A=0) + sum p_as*(2a-1)*q_as.
            coef = p * (2*a - 1)
            equality = np.array([2*p[0], -2*p[1], 2*p[2], -2*p[3]])
            fit = linprog(-coef, A_eq=[equality], b_eq=[0],
                          bounds=[(0, 1)]*4, method='highs')
            self.assertTrue(fit.success)
            optimum = .5 - fit.fun
            self.assertAlmostEqual(optimum, .5 + eps, places=8)
            records.append({'author_source_disagreement': eps,
                            'best_source_invariant_author_accuracy': optimum,
                            'unrestricted_author_accuracy': 1.})
        RESULTS['invariance_tradeoff'] = records

    def test_03_crossing_identifies_only_the_declared_model(self):
        full = list(itertools.product([0, 1], repeat=2))
        D = design(full)
        beta = np.array([.3, 1.7, -.8])
        fitted = np.linalg.lstsq(D, D @ beta, rcond=None)[0]
        self.assertTrue(np.allclose(fitted, beta))
        tree = [(0, 0), (0, 1), (1, 1)]
        self.assertEqual(np.linalg.matrix_rank(design(tree)), 3)
        self.assertEqual(len(tree) - np.linalg.matrix_rank(design(tree)), 0)
        self.assertEqual(len(full) - np.linalg.matrix_rank(D), 1)
        # All pairwise incidence graphs are connected, yet a 3-way design fails.
        cells = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        self.assertTrue(all(pair_connected(cells, i, j)
                            for i, j in itertools.combinations(range(3), 2)))
        self.assertEqual(np.linalg.matrix_rank(design(cells)), 3)
        self.assertTrue(np.allclose(design(cells) @ [-1, 1, 1, 1], 0))
        RESULTS['sampling_design'] = {
            'crossed_2x2_additive_rank': int(np.linalg.matrix_rank(D)),
            'crossed_2x2_recovered_coefficients': fitted.tolist(),
            'connected_tree_interaction_check_degrees_of_freedom': 0,
            'crossed_cycle_interaction_check_degrees_of_freedom': 1,
            'all_pairwise_connected_3factor_counterexample_cells': cells,
            'counterexample_rank': 3, 'counterexample_columns': 4,
            'counterexample_null_direction': [-1, 1, 1, 1]}

    def test_04_author_positive_source_shortcut(self):
        # Observed A=S: an author code and a source code have identical geometry.
        a = np.repeat(np.arange(3), 6)
        s = a.copy()
        za, zs = np.eye(3)[a], np.eye(3)[s]
        self.assertTrue(np.array_equal(za @ za.T, zs @ zs.T))
        train = LogisticRegression(C=1e3).fit(zs, a)
        observed = float(train.score(zs, a))
        # Hypothetical crossed test; NOT real corpus evidence.
        shifted_sources = (a + 1) % 3
        crossed = float(train.score(np.eye(3)[shifted_sources], a))
        self.assertEqual(observed, 1.)
        self.assertEqual(crossed, 0.)
        RESULTS['contrastive_shortcut'] = {
            'all_observed_pairwise_similarities_identical': True,
            'source_only_observed_author_accuracy': observed,
            'source_only_counterfactual_crossed_accuracy': crossed,
            'conclusion': 'Any objective using these labels and similarities cannot prefer author geometry.'}

    def test_05_shared_parser_views_do_not_add_independent_latents(self):
        rng = np.random.default_rng(17)
        latent = rng.normal(size=(500, 3))
        mixing = rng.normal(size=(3, 71))
        views = latent @ mixing
        self.assertEqual(np.linalg.matrix_rank(views), 3)
        RESULTS['correlated_observables'] = {
            'observed_channels': 71, 'synthetic_signal_rank': 3,
            'conclusion': 'Channel count alone neither identifies latent dimension nor independent evidence.'}

    def test_06_transition_learning_beats_exact_same_bag(self):
        rng = np.random.default_rng(20261002)
        per_class_train, per_class_test = 240, 160
        tr = [balanced_markov(rng, p, per_class_train) for p in [.8, .2]]
        te = [balanced_markov(rng, p, per_class_test) for p in [.8, .2]]
        train, test = np.vstack(tr), np.vstack(te)
        ytr = np.repeat([0, 1], per_class_train)
        yte = np.repeat([0, 1], per_class_test)
        # Explicitly crossed provenance/topic metadata, excluded from model inputs.
        tr_source = np.tile(np.arange(per_class_train) % 2, 2)
        te_source = np.full(2*per_class_test, 2)  # new source
        tr_topic = np.tile(np.arange(per_class_train) % 3, 2)
        te_topic = np.full(2*per_class_test, 3)  # new topic
        for labels in [tr_source, tr_topic]:
            for v in np.unique(labels):
                self.assertEqual(np.mean(ytr[labels == v]), .5)
        self.assertTrue(set(tr_source).isdisjoint(te_source))
        self.assertTrue(set(tr_topic).isdisjoint(te_topic))
        bag_train = np.column_stack([train.mean(1), train.var(1)])
        bag_test = np.column_stack([test.mean(1), test.var(1)])
        self.assertEqual(np.unique(bag_train, axis=0).shape[0], 1)
        bag = LogisticRegression().fit(bag_train, ytr)
        bag_accuracy = float(bag.score(bag_test, yte))
        ps = [fit_stay(x) for x in tr]
        scores = np.column_stack([log_conditional_order(test, p) for p in ps])
        accuracy = float(np.mean(scores.argmax(1) == yte))
        true_score = scores[np.arange(len(yte)), yte]
        shared_p = fit_stay(train)
        shared_score = log_conditional_order(test, shared_p)
        uniform_score = -math.log(math.comb(test.shape[1], test.shape[1] // 2))
        bits_per_transition = float(np.mean(true_score-shared_score)
                                    / ((test.shape[1]-1)*math.log(2)))
        # Same multiset, same permutations paired across labels -> exact chance.
        common = np.vstack([rng.permutation(test[0]) for _ in range(per_class_test)])
        shuffled = np.vstack([common, common])
        shuffled_scores = np.column_stack([log_conditional_order(shuffled, p) for p in ps])
        shuffled_accuracy = float(np.mean(shuffled_scores.argmax(1) == yte))
        # Exchangeable negative control: fit both classes to independently uniform bags.
        ctrl = [np.vstack([rng.permutation(train[0]) for _ in range(per_class_train)])
                for _ in range(2)]
        ctrl_p = [fit_stay(x) for x in ctrl]
        ctrl_shared = fit_stay(np.vstack(ctrl))
        ctrl_scores = np.column_stack([log_conditional_order(shuffled, p) for p in ctrl_p])
        ctrl_gain = float(np.mean(ctrl_scores[np.arange(len(yte)), yte]
                                 - log_conditional_order(shuffled, ctrl_shared))
                          / ((test.shape[1]-1)*math.log(2)))
        self.assertEqual(bag_accuracy, .5)
        self.assertGreater(accuracy, .95)
        self.assertGreater(bits_per_transition, .15)
        self.assertEqual(shuffled_accuracy, .5)
        self.assertLess(ctrl_gain, .01)
        RESULTS['conditional_dynamics'] = {
            'seed': 20261002, 'train_documents': len(train), 'test_documents': len(test),
            'sequence_length': test.shape[1], 'ones_in_every_document': 16,
            'generating_stay_probabilities': [.8, .2], 'fitted_stay_probabilities': ps,
            'fitted_shared_stay_probability': shared_p,
            'exact_same_bag_accuracy': bag_accuracy,
            'conditional_markov_accuracy': accuracy,
            'paired_order_destroyed_accuracy': shuffled_accuracy,
            'conditional_vs_shared_loglik_gain_bits_per_transition': bits_per_transition,
            'conditional_vs_uniform_loglik_gain_bits_per_transition': float(
                np.mean(true_score-uniform_score)/((test.shape[1]-1)*math.log(2))),
            'exchangeable_negative_control_gain_bits_per_transition': ctrl_gain,
            'train_source_levels': [0, 1], 'test_source_levels': [2],
            'train_topic_levels': [0, 1, 2], 'test_topic_levels': [3],
            'limitation': 'Metadata are balanced placeholders, not realistic source perturbations. Known synthetic classes only; no unseen-author or natural-text conclusion.'}

    def test_07_graph_order_view_is_not_rewrite_identification(self):
        # Same degree sequence: one 6-cycle versus two disjoint triangles.
        C = np.zeros((6, 6))
        T = np.zeros((6, 6))
        for i in range(6):
            C[i, (i+1)%6] = C[(i+1)%6, i] = 1
        for group in [[0, 1, 2], [3, 4, 5]]:
            for i, j in itertools.combinations(group, 2):
                T[i, j] = T[j, i] = 1
        self.assertTrue(np.array_equal(C.sum(1), T.sum(1)))
        def components(A):
            L = np.diag(A.sum(1)) - A
            return int(np.count_nonzero(np.abs(np.linalg.eigvalsh(L)) < 1e-8))
        self.assertEqual(components(C), 1)
        self.assertEqual(components(T), 2)
        RESULTS['topology_ablation'] = {
            'nodes': 6, 'edges_in_each_graph': 6,
            'degree_multisets_identical': True,
            'connected_components_cycle': components(C),
            'connected_components_two_triangles': components(T),
            'conclusion': 'Topology can add information beyond local degree bags; this provides no causal effect of a text edit.'}

    def test_08_stable_context_decomposition_needs_a_gauge(self):
        stable = np.array([1., 3.])
        context = np.array([[2., -2.], [4., -4.]])
        observed = stable[:, None] + context
        shift = np.array([7., -5.])
        changed_stable = stable + shift
        changed_context = context - shift[:, None]
        self.assertTrue(np.array_equal(observed, changed_stable[:, None] + changed_context))
        self.assertTrue(np.allclose(observed.mean(1), stable))
        RESULTS['stable_context_gauge'] = {
            'observed_values_identical_after_author_specific_shift': True,
            'centering_under_declared_context_distribution_recovers_defined_mean': True,
            'conclusion': 'Stable must be defined relative to a context reference distribution; unrestricted decomposition is nonunique.'}

    def test_09_sentence_rhythm_and_paragraph_order_are_distinct(self):
        short, long = [8, 10, 12], [18, 20, 22]
        block = np.array([short, short, long, long])
        alternate = np.array([short, long, short, long])
        self.assertTrue(np.array_equal(np.sort(block.ravel()), np.sort(alternate.ravel())))
        self.assertTrue(np.array_equal(np.sort(block.mean(1)), np.sort(alternate.mean(1))))
        block_jump = float(np.abs(np.diff(block.mean(1))).mean())
        alternate_jump = float(np.abs(np.diff(alternate.mean(1))).mean())
        self.assertNotEqual(block_jump, alternate_jump)
        # Within-paragraph permutations change sentence rhythm without changing
        # paragraph means or paragraph-level trajectory.
        reordered = block[:, [0, 2, 1]]
        self.assertTrue(np.array_equal(reordered.mean(1), block.mean(1)))
        rhythm_a = float(np.abs(np.diff(block, axis=1)).mean())
        rhythm_b = float(np.abs(np.diff(reordered, axis=1)).mean())
        self.assertNotEqual(rhythm_a, rhythm_b)
        RESULTS['multiscale_order'] = {
            'identical_sentence_length_bags': True,
            'identical_paragraph_mean_bags': True,
            'block_paragraph_mean_absolute_jump': block_jump,
            'alternating_paragraph_mean_absolute_jump': alternate_jump,
            'original_within_paragraph_mean_absolute_jump': rhythm_a,
            'reordered_within_paragraph_mean_absolute_jump': rhythm_b,
            'paragraph_means_unchanged_by_within_paragraph_permutation': True,
            'conclusion': 'Within-paragraph rhythm and between-paragraph ordering need separate views; global histograms identify neither.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results.json')
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IdentificationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    RESULTS['test_summary'] = {'run': result.testsRun, 'failures': len(result.failures),
                               'errors': len(result.errors),
                               'scope': 'Mathematical counterexamples and synthetic estimator checks only.'}
    Path(args.output).write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
