"""Original synthetic tensor tests only; no source data, parser, or empirical fit."""

import inspect
import math
import unittest

import torch

from research.observed_sequence.models import (
    ARM_PARAMETER_COUNTS,
    ConstantPrior,
    LatestState,
    ModelInputError,
    ShuffledGRU,
    counts_to_soft_targets,
    make_model,
    parameter_count,
    per_record_soft_target_ce,
    prefix_length_features,
    record_equal_smoothed_prior,
    record_equal_soft_target_ce,
    shuffle_prefix,
    soft_target_cross_entropy,
)


def synthetic_prefix(units=7, seed=151):
    generator = torch.Generator(device="cpu").manual_seed(seed)
    values = torch.randn(units, 68, 4, generator=generator)
    values[:, :, 1] = torch.randint(0, 2, (units, 68), generator=generator)
    values[:, :, 3] = torch.randint(0, 2, (units, 68), generator=generator)
    values[:, :, 0] *= values[:, :, 1]
    values[:, :, 2] *= values[:, :, 3]
    return values.reshape(units, 272), prefix_length_features(units, 11 * units + 4)


def one_hot(index):
    return torch.nn.functional.one_hot(torch.tensor(index), 14).to(torch.float64)


def predict(model, prefix, lengths, seed=23):
    if isinstance(model, ShuffledGRU):
        return model(prefix, lengths, shuffle_seed=seed)
    return model(prefix, lengths)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_exact_frozen_parameter_counts_and_output_shapes(self):
        prefix, lengths = synthetic_prefix()
        expected = {"mask_length_mlp": 6134, "pooled_raw_mlp": 4638,
                    "deepsets": 5966, "gru": 6266, "shuffled_gru": 6266}
        self.assertEqual(ARM_PARAMETER_COUNTS, expected)
        for arm, count in expected.items():
            with self.subTest(arm=arm):
                model = make_model(arm, seed=1729)
                self.assertEqual(parameter_count(model), count)
                output = predict(model, prefix, lengths)
                self.assertEqual(output.shape, (14,))
                self.assertTrue(torch.isfinite(output).all().item())
                self.assertAlmostEqual(output.softmax(-1).sum().item(), 1.0, places=6)

    def test_factory_is_seeded_independent_and_does_not_change_global_rng(self):
        state = torch.random.get_rng_state().clone()
        for arm in ARM_PARAMETER_COUNTS:
            first = make_model(arm, seed=2718)
            second = make_model(arm, seed=2718)
            different = make_model(arm, seed=3141)
            for left, right in zip(first.parameters(), second.parameters()):
                self.assertNotEqual(left.data_ptr(), right.data_ptr())
                torch.testing.assert_close(left, right, rtol=0, atol=0)
            self.assertTrue(any(not torch.equal(a, b)
                                for a, b in zip(first.parameters(), different.parameters())))
        torch.testing.assert_close(torch.random.get_rng_state(), state, rtol=0, atol=0)

    def test_deepsets_and_pooled_controls_are_permutation_invariant(self):
        prefix, lengths = synthetic_prefix()
        order = torch.tensor([6, 2, 4, 0, 3, 1, 5])
        for arm in ("deepsets", "pooled_raw_mlp", "mask_length_mlp"):
            with self.subTest(arm=arm):
                model = make_model(arm, seed=1729)
                torch.testing.assert_close(model(prefix, lengths), model(prefix[order], lengths),
                                           rtol=1e-5, atol=1e-7)

    def test_deepsets_maps_nonlinearly_before_pooling(self):
        prefix, lengths = synthetic_prefix()
        model = make_model("deepsets", seed=1729)
        expected = model.head(torch.cat((model.unit_map(prefix).mean(0), lengths)))
        wrong_order = model.head(torch.cat((model.unit_map(prefix.mean(0)), lengths)))
        torch.testing.assert_close(model(prefix, lengths), expected, rtol=0, atol=0)
        self.assertGreater((expected - wrong_order).abs().max().item(), 1e-5)

    def test_gru_detects_order_and_resets_hidden_state(self):
        prefix, lengths = synthetic_prefix()
        model = make_model("gru", seed=1729)
        forward = model(prefix, lengths)
        backward = model(prefix.flip(0), lengths)
        self.assertGreater((forward - backward).abs().max().item(), 1e-5)
        torch.testing.assert_close(model(prefix, lengths), forward, rtol=0, atol=0)

    def test_shuffle_is_seeded_exact_same_gru_architecture_and_no_global_rng(self):
        prefix, lengths = synthetic_prefix()
        before = prefix.clone()
        state = torch.random.get_rng_state().clone()
        regular = make_model("gru", seed=2718)
        shuffled = make_model("shuffled_gru", seed=2718)
        for name, parameter in regular.state_dict().items():
            torch.testing.assert_close(parameter, shuffled.state_dict()[name], rtol=0, atol=0)
        actual = shuffled(prefix, lengths, shuffle_seed=71)
        expected = regular(shuffle_prefix(prefix, shuffle_seed=71), lengths)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        torch.testing.assert_close(shuffled(prefix, lengths, shuffle_seed=71), actual, rtol=0, atol=0)
        self.assertFalse(torch.equal(shuffle_prefix(prefix, shuffle_seed=71),
                                     shuffle_prefix(prefix, shuffle_seed=72)))
        torch.testing.assert_close(prefix, before, rtol=0, atol=0)
        torch.testing.assert_close(torch.random.get_rng_state(), state, rtol=0, atol=0)
        with self.assertRaises(TypeError):
            shuffled(prefix, lengths)

    def test_prefix_only_api_cannot_receive_future_metadata(self):
        for arm in ARM_PARAMETER_COUNTS:
            names = tuple(inspect.signature(make_model(arm, seed=1729).forward).parameters)
            expected = ("prefix", "prefix_length_features")
            if arm == "shuffled_gru":
                expected += ("shuffle_seed",)
            self.assertEqual(names, expected)

    def test_replaced_and_appended_suffix_never_changes_visible_prediction(self):
        # This checks the tensor-only API boundary. Source segmentation/caching
        # suffix-invariance is a separate parent-adapter contract, not proved here.
        prefix, lengths = synthetic_prefix()
        suffix, _ = synthetic_prefix(units=5, seed=902)
        changed, _ = synthetic_prefix(units=13, seed=777)
        records = (torch.cat((prefix, suffix)), torch.cat((prefix, changed)),
                   torch.cat((prefix, suffix, changed)))
        for arm in ARM_PARAMETER_COUNTS:
            model = make_model(arm, seed=1729)
            expected = predict(model, prefix, lengths)
            for record in records:
                torch.testing.assert_close(predict(model, record[:len(prefix)], lengths),
                                           expected, rtol=0, atol=0)

    def test_mask_control_ignores_value_and_opportunity_magnitude(self):
        prefix, lengths = synthetic_prefix()
        changed = prefix.clone().reshape(-1, 68, 4)
        changed[:, :, 0] += 31
        changed[:, :, 2] -= 18
        model = make_model("mask_length_mlp", seed=1729)
        torch.testing.assert_close(model(prefix, lengths), model(changed.reshape(-1, 272), lengths),
                                   rtol=0, atol=0)

    def test_all_trainable_arms_have_finite_nonzero_gradients_and_take_one_step(self):
        first, first_lengths = synthetic_prefix(units=7, seed=31)
        second, second_lengths = synthetic_prefix(units=5, seed=32)
        targets = torch.stack((one_hot(2), (one_hot(1) + one_hot(8)) / 2))
        for arm in ARM_PARAMETER_COUNTS:
            with self.subTest(arm=arm):
                model = make_model(arm, seed=1729)
                before = [parameter.detach().clone() for parameter in model.parameters()]
                optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
                logits = torch.stack((predict(model, first, first_lengths, seed=17),
                                      predict(model, second, second_lengths, seed=18)))
                loss = record_equal_soft_target_ce(logits, targets, torch.tensor([0, 1]))
                optimizer.zero_grad()
                loss.backward()
                for name, parameter in model.named_parameters():
                    self.assertIsNotNone(parameter.grad, name)
                    self.assertTrue(torch.isfinite(parameter.grad).all().item(), name)
                    self.assertGreater(parameter.grad.abs().sum().item(), 0, name)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                self.assertTrue(all(not torch.equal(old, new)
                                    for old, new in zip(before, model.parameters())))

    def test_length_features_only_encode_observed_prefix_and_reject_total_units(self):
        prefix, lengths = synthetic_prefix()
        torch.testing.assert_close(lengths, torch.tensor([math.log1p(7), math.log1p(81)]))
        model = make_model("gru", seed=1729)
        with self.assertRaisesRegex(ModelInputError, "this prefix only"):
            model(prefix, prefix_length_features(99, 800))
        for counts in ((0, 10), (True, 3), (3, 2), (3, -1), (3, 4.5)):
            with self.assertRaises(ModelInputError):
                prefix_length_features(*counts)

    def test_invalid_inputs_fail_closed_without_imputation(self):
        prefix, lengths = synthetic_prefix()
        model = make_model("deepsets", seed=1729)
        broken = prefix.clone()
        broken[0, 0] = float("nan")
        with self.assertRaisesRegex(ModelInputError, "finite"):
            model(broken, lengths)
        broken = prefix.clone()
        broken[0, 1] = 0.5
        with self.assertRaisesRegex(ModelInputError, "binary"):
            model(broken, lengths)
        for bad in (prefix[:, :-1], prefix.unsqueeze(0), prefix[:0]):
            with self.assertRaises(ModelInputError):
                model(bad, lengths)
        with self.assertRaises(ModelInputError):
            model(prefix, lengths.double())
        with self.assertRaises(ModelInputError):
            make_model("not_an_arm", seed=17)
        for seed in (-1, 2**63, 0.5, True):
            with self.assertRaises(ModelInputError):
                make_model("gru", seed=seed)


class LossAndBaselineTests(unittest.TestCase):
    def test_integer_counts_normalize_without_target_length_weighting(self):
        counts = torch.tensor([3, 1] + [0] * 12)
        first = counts_to_soft_targets(counts)
        second = counts_to_soft_targets(100 * counts)
        torch.testing.assert_close(first, second, rtol=0, atol=0)
        self.assertEqual(first[:2].tolist(), [0.75, 0.25])
        logits = torch.linspace(-1, 1, 14)
        torch.testing.assert_close(soft_target_cross_entropy(logits, first),
                                   soft_target_cross_entropy(logits, second), rtol=0, atol=0)

    def test_target_failures_are_rejected_not_renormalized_or_imputed(self):
        for counts in (torch.zeros(14, dtype=torch.int64), torch.tensor([-1] + [1] * 13),
                       torch.ones(14), torch.ones(13, dtype=torch.int64),
                       torch.empty(0, 14, dtype=torch.int64)):
            with self.assertRaises(ModelInputError):
                counts_to_soft_targets(counts)
        logits = torch.zeros(14)
        for targets in (torch.zeros(14), torch.ones(14), torch.full((14,), float("nan")),
                        torch.tensor([-0.1, 1.1] + [0.] * 12), torch.ones(13) / 13):
            with self.assertRaises(ModelInputError):
                soft_target_cross_entropy(logits, targets)
        with self.assertRaises(ModelInputError):
            soft_target_cross_entropy(torch.full((14,), float("inf")), one_hot(1))
        extreme = torch.zeros(14)
        extreme[0], extreme[1] = -3e38, 3e38
        with self.assertRaisesRegex(ModelInputError, "nonfinite loss"):
            soft_target_cross_entropy(extreme, one_hot(1))

    def test_soft_ce_matches_manual_formula_and_has_no_target_gradient(self):
        logits = torch.linspace(-1, 2, 14, dtype=torch.float64, requires_grad=True)
        targets = ((one_hot(3) + one_hot(8)) / 2).requires_grad_(True)
        expected = -0.5 * (logits.log_softmax(-1)[3] + logits.log_softmax(-1)[8])
        loss = soft_target_cross_entropy(logits, targets)
        torch.testing.assert_close(loss, expected, rtol=0, atol=0)
        loss.backward()
        self.assertIsNone(targets.grad)
        self.assertTrue(torch.isfinite(logits.grad).all().item())

    def test_record_equal_loss_and_gradients_not_target_equal(self):
        logits = torch.stack((torch.zeros(14), torch.arange(14.), torch.arange(14.) / 3))
        logits.requires_grad_(True)
        targets = torch.stack((one_hot(0), one_hot(13), one_hot(5)))
        grouping = torch.tensor([8, 2, 2])
        target_losses = soft_target_cross_entropy(logits, targets)
        expected = (target_losses[0] + target_losses[1:].mean()) / 2
        actual = record_equal_soft_target_ce(logits, targets, grouping)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        self.assertGreater(abs(actual.item() - target_losses.mean().item()), 0.01)
        ids, record_losses = per_record_soft_target_ce(logits, targets, grouping)
        self.assertEqual(ids.tolist(), [2, 8])
        torch.testing.assert_close(record_losses, torch.stack((target_losses[1:].mean(), target_losses[0])))
        actual.backward()
        weights = torch.tensor([0.5, 0.25, 0.25]).unsqueeze(-1)
        torch.testing.assert_close(logits.grad, weights * (logits.softmax(-1) - targets.float()))

    def test_duplicate_targets_within_one_record_do_not_change_its_weight(self):
        logits = torch.stack((torch.zeros(14), torch.arange(14.)))
        targets = torch.stack((one_hot(0), one_hot(13)))
        baseline = record_equal_soft_target_ce(logits, targets, torch.tensor([0, 1]))
        indices = torch.tensor([0, 1, 1, 1, 1, 1])
        duplicated = record_equal_soft_target_ce(logits[indices], targets[indices], indices)
        torch.testing.assert_close(duplicated, baseline, rtol=1e-7, atol=1e-7)

    def test_invalid_record_groups_rejected(self):
        logits, targets = torch.zeros(2, 14), torch.stack((one_hot(0), one_hot(1)))
        for ids in (torch.tensor([0]), torch.tensor([0., 1.]), torch.tensor([-1, 1]),
                    torch.tensor([[0, 1]])):
            with self.assertRaises(ModelInputError):
                record_equal_soft_target_ce(logits, targets, ids)
        with self.assertRaises(ModelInputError):
            record_equal_soft_target_ce(torch.empty(0, 14), torch.empty(0, 14),
                                       torch.empty(0, dtype=torch.int64))

    def test_prior_is_record_equal_and_exact_positive_total_one_smoothing(self):
        first = torch.stack((one_hot(0), one_hot(1)))
        second = one_hot(2).repeat(9, 1)
        prior = record_equal_smoothed_prior((first, second))
        expected = ((one_hot(0) + one_hot(1)) / 2 + one_hot(2) + 1 / 14) / 3
        torch.testing.assert_close(prior, expected, rtol=0, atol=0)
        self.assertTrue((prior > 0).all().item())
        self.assertAlmostEqual(prior.sum().item(), 1.0)
        torch.testing.assert_close(record_equal_smoothed_prior((first, second[:1])),
                                   prior, rtol=0, atol=0)
        baseline = ConstantPrior(prior)
        self.assertEqual(parameter_count(baseline), 0)
        torch.testing.assert_close(baseline().softmax(-1), prior)

    def test_prior_rejects_missing_empty_and_unsmoothed_inputs(self):
        for records in ((), (torch.empty(0, 14),), (torch.zeros(1, 14),), (one_hot(0),)):
            with self.assertRaises(ModelInputError):
                record_equal_smoothed_prior(records)
        with self.assertRaisesRegex(ModelInputError, "strictly positive"):
            ConstantPrior(one_hot(0))

    def test_latest_uses_last_valid_visible_unit_and_falls_back_to_prior(self):
        prior = record_equal_smoothed_prior((one_hot(4).unsqueeze(0),))
        model = LatestState(prior)
        self.assertEqual(parameter_count(model), 0)
        for visible in ([], [None], [None, None]):
            torch.testing.assert_close(model(visible).softmax(-1), prior)
        actual = model([one_hot(0), None, one_hot(7), None]).softmax(-1)
        expected = 0.9 * one_hot(7) + 0.1 * prior
        torch.testing.assert_close(actual, expected)
        self.assertTrue((actual > 0).all().item())
        with self.assertRaises(ModelInputError):
            model([one_hot(0), torch.zeros(14)])


if __name__ == "__main__":
    unittest.main()
