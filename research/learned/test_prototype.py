"""Synthetic mechanics tests only: no corpus, model download, or fitted artifact."""
from dataclasses import replace
import unittest
import torch
from research.learned.contracts import (
    ContractError, Measurement, Observation, GraphSnapshot, Node, Edge, Episode,
    SupportRef, NextActionTarget, prefix_view)
from research.learned.fixtures import toy_document, toy_episode, measure
from research.learned.model import (Config, MultiViewDynamics, BinaryGroupGates, BoundedLinear,
                                    measurement_tensor, multilabel_next_action_loss)
from research.learned.topology_adapter import from_phd_report


def changed_suffix(document, cutoff):
    rows = tuple(row if row.step <= cutoff else replace(row, features=measure([99, -71, 53, 22]))
                 for row in document.observations)
    # Existing prefix snapshots are unchanged; later exact-prefix graphs may change arbitrarily.
    graphs = tuple(g if g.prefix_end <= cutoff else
                   replace(g, nodes=tuple(replace(n, features=measure([23, 45, -10, 67]))
                                          for n in g.nodes), edges=tuple(reversed(g.edges)))
                   for g in document.graph_snapshots)
    return replace(document, observations=rows, graph_snapshots=graphs)


class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        torch.manual_seed(928)
        self.model = MultiViewDynamics(reference_contexts=[[0, 0], [1, -1]],
                                      reference_weights=[1, 3])
        self.episode, self.target = toy_episode()

    def assertContract(self, code, callback):
        with self.assertRaisesRegex(ContractError, code):
            callback()

    def test_shapes_and_multilabel_loss(self):
        output = self.model(self.episode)
        self.assertEqual(tuple(output['action_logits'].shape), (4,))
        self.assertEqual(tuple(output['z_stable'].shape), (16,))
        self.assertEqual(tuple(output['z_context'].shape), (16,))
        loss, info = multilabel_next_action_loss(output, self.target)
        self.assertTrue(torch.isfinite(loss))
        self.assertEqual(info['observed_actions'], 3)
        self.assertEqual(self.target.actions[:2], (1.0, 1.0))
        self.assertIn('typed_graph_structure', output['remaining_information_paths'])

    def test_32_dimension_candidate(self):
        model = MultiViewDynamics(Config(latent=32))
        self.assertEqual(tuple(model(self.episode)['z_stable'].shape), (32,))

    def test_genuine_gradients_all_active_branches(self):
        episode, target = toy_episode(with_topology=True)
        output = self.model(episode)
        loss, _ = multilabel_next_action_loss(output, target)
        loss.backward()
        for name in ('global_branch', 'sequence_branch', 'graph_branch', 'topology_branch',
                     'fusion', 'stable_head', 'context_head', 'residual_head', 'action_head', 'gates'):
            module = getattr(self.model, name)
            total = sum(p.grad.abs().sum().item() for p in module.parameters() if p.grad is not None)
            self.assertGreater(total, 0, name)
            for parameter in module.parameters():
                if parameter.grad is not None:
                    self.assertTrue(torch.isfinite(parameter.grad).all(), name)
        for relation in self.model.graph_branch.relations:
            self.assertGreater(relation.weight.grad.abs().sum().item(), 0)

    def test_one_synthetic_optimizer_step_changes_parameters(self):
        before = self.model.action_head.weight.detach().clone()
        optimizer = torch.optim.SGD(self.model.parameters(), lr=0.01)
        out = self.model(self.episode)
        loss, _ = multilabel_next_action_loss(out, self.target)
        (loss + 0.001 * out['gate_surrogate']).backward()
        optimizer.step()
        self.assertFalse(torch.equal(before, self.model.action_head.weight))
        self.assertTrue(torch.isfinite(self.model(self.episode)['action_logits']).all())

    def test_future_suffix_does_not_change_any_prediction(self):
        before = self.model(self.episode)
        query = changed_suffix(self.episode.query, self.episode.cutoff)
        after = self.model(replace(self.episode, query=query))
        for key in ('action_logits', 'z_stable', 'z_context', 'h_prefix'):
            torch.testing.assert_close(before[key], after[key], rtol=0, atol=0)
        for key in before['query_branches']:
            torch.testing.assert_close(before['query_branches'][key],
                                       after['query_branches'][key], rtol=0, atol=0)

    def test_appended_future_length_does_not_leak(self):
        query = self.episode.query
        new_rows = tuple(Observation(t, t, measure([200, 100, -50, 19])) for t in (6, 7, 8))
        extended = replace(query, observations=query.observations + new_rows)
        before, after = self.model(self.episode), self.model(replace(self.episode, query=extended))
        torch.testing.assert_close(before['action_logits'], after['action_logits'], rtol=0, atol=0)

    def test_transformer_internal_causal_mask(self):
        rows = measurement_tensor([r.features for r in self.episode.query.observations], 4, 'cpu')
        gates = self.model.gates()[:-1]
        original = self.model.sequence_branch(rows, gates)
        changed = rows.clone()
        changed[3:, 0, :] = 20
        changed_result = self.model.sequence_branch(changed, gates)
        prefix_result = self.model.sequence_branch(rows[:3], gates)
        torch.testing.assert_close(original[:3], changed_result[:3], rtol=0, atol=0)
        torch.testing.assert_close(original[:3], prefix_result, rtol=1e-6, atol=1e-6)

    def test_only_future_graph_cannot_substitute_for_exact_prefix(self):
        query = replace(self.episode.query, graph_snapshots=(self.episode.query.graph_snapshots[-1],))
        self.assertContract('exact_prefix_graph_required',
                            lambda: self.model(replace(self.episode, query=query)))

    def test_retrospective_graph_rejected(self):
        graphs = list(self.episode.query.graph_snapshots)
        graphs[2] = replace(graphs[2], provenance='full_document_then_sliced')
        query = replace(self.episode.query, graph_snapshots=tuple(graphs))
        self.assertContract('retrospective_graph_forbidden',
                            lambda: self.model(replace(self.episode, query=query)))

    def test_future_node_and_edge_rejected(self):
        graph = self.episode.query.graph_snapshots[2]
        for invalid, code in ((replace(graph, nodes=graph.nodes +
                                (Node(3, 0, 4, measure([1, 2, 3, 4])),)), 'future_node'),
                              (replace(graph, edges=graph.edges + (Edge(0, 2, 0, 4),)),
                               'future_or_premature_edge')):
            graphs = tuple(invalid if g.prefix_end == 3 else g
                           for g in self.episode.query.graph_snapshots)
            query = replace(self.episode.query, graph_snapshots=graphs)
            self.assertContract(code, lambda: self.model(replace(self.episode, query=query)))

    def test_future_resolved_local_measurement_rejected(self):
        rows = list(self.episode.query.observations)
        rows[0] = replace(rows[0], source_prefix_end=5)
        query = replace(self.episode.query, observations=tuple(rows))
        self.assertContract('nonlocal_or_noncontiguous_observation',
                            lambda: self.model(replace(self.episode, query=query)))

    def test_stable_output_reads_support_not_query_or_query_context(self):
        original = self.model(self.episode)
        altered_query = toy_document('query', topic='topic_B', released_at=30, phase=2.0)
        changed = self.model(replace(self.episode, query=altered_query, context=(20, -30)))
        torch.testing.assert_close(original['z_stable'], changed['z_stable'], rtol=0, atol=0)
        self.assertFalse(torch.allclose(original['z_context'], changed['z_context']))
        support = tuple(SupportRef(replace(s.document, observations=tuple(
            replace(row, features=measure([1, 2, -3, 4])) for row in s.document.observations)),
            s.cutoff) for s in self.episode.support)
        new = self.model(replace(self.episode, support=support))
        self.assertFalse(torch.allclose(original['z_stable'], new['z_stable']))

    def test_support_permutation_invariant(self):
        a = self.model(self.episode)
        b = self.model(replace(self.episode, support=tuple(reversed(self.episode.support))))
        torch.testing.assert_close(a['z_stable'], b['z_stable'], rtol=0, atol=0)

    def test_no_support_is_explicit_prior_not_author_profile(self):
        output = self.model(replace(self.episode, support=()))
        self.assertEqual(output['stable_source'], 'population_prior_unfitted')
        torch.testing.assert_close(output['z_stable'], torch.zeros(16))

    def test_support_query_leakage_groups_rejected(self):
        ref = self.episode.support[0]
        for field, value, code in (
            ('work_id', self.episode.query.work_id, 'support_query_work_overlap'),
            ('lineage_id', self.episode.query.lineage_id, 'support_query_lineage_overlap'),
            ('content_family', self.episode.query.content_family, 'support_query_content_overlap'),
            ('partition', 'synthetic_test', 'cross_partition_episode'),
            ('released_at', 41, 'future_support'),
            ('author_key', 'other', 'support_author_mismatch'),
            ('topic', self.episode.query.topic, 'cross_topic_support_required')):
            with self.subTest(field=field):
                bad = replace(ref, document=replace(ref.document, **{field: value}))
                self.assertContract(code, lambda: self.model(replace(self.episode, support=(bad,))))

    def test_duplicate_support_rejected(self):
        ref = self.episode.support[0]
        self.assertContract('support_query_work_overlap',
                            lambda: self.model(replace(self.episode, support=(ref, ref))))

    def test_empirical_personal_and_multiauthor_inputs_rejected(self):
        for fields, code in (({'synthetic': False}, 'empirical_and_personal'),
                             ({'personal': True}, 'empirical_and_personal'),
                             ({'attribution_role': 'discussion_multiple_speakers'},
                              'single_producer_role_required')):
            query = replace(self.episode.query, **fields)
            self.assertContract(code, lambda: self.model(replace(self.episode, query=query)))

    def test_missing_is_distinct_from_observed_zero(self):
        zero = Measurement((0.,) * 4, (1.,) * 4, (None,) * 4)
        missing = Measurement((None,) * 4, (None,) * 4, ('parse_failed',) * 4)
        z = measurement_tensor([zero], 4, 'cpu')
        m = measurement_tensor([missing], 4, 'cpu')
        self.assertFalse(torch.equal(z, m))
        self.assertEqual(float(z[0, 1].sum()), 4)
        self.assertEqual(float(m[0, 1].sum()), 0)

    def test_measurement_failures(self):
        cases = (
            (Measurement((None,) * 4, (None,) * 4, (None,) * 4), 'missing_reason_required'),
            (Measurement((float('nan'),) * 4, (1.,) * 4, (None,) * 4), 'nonfinite_measurement'),
            (Measurement((0.,) * 4, (0.,) * 4, (None,) * 4), 'observed_without_opportunity'),
            (Measurement((None,) * 4, (1.,) * 4, ('zero_denominator',) * 4),
             'zero_denominator_mismatch'))
        for measurement, code in cases:
            self.assertContract(code, lambda: measurement.validate(4))

    def test_binary_gates_and_fixed_mask_no_soft_rescaling(self):
        gate = BinaryGroupGates(3)
        with torch.no_grad():
            gate.logits.copy_(torch.tensor([-10., 0.2, 10.]))
        torch.testing.assert_close(gate(), torch.tensor([0., 1., 1.]), rtol=0, atol=0)
        gate().sum().backward()
        self.assertTrue((gate.logits.grad > 0).all())
        gate.freeze([0, 1, 0])
        with torch.no_grad():
            gate.logits.fill_(100.)
        torch.testing.assert_close(gate(), torch.tensor([0., 1., 0.]), rtol=0, atol=0)
        self.assertContract('binary_gate_mask_required', lambda: gate.freeze([0.01, 1, 0]))

    def test_closed_channel_cannot_bypass_via_sequence_graph_or_presence(self):
        self.model.gates.freeze([0, 1, 1, 1, 0])
        original = self.model(self.episode)
        def change(measurement):
            return Measurement((None,) + measurement.values[1:],
                               (None,) + measurement.opportunities[1:],
                               ('parse_failed',) + measurement.missing_reasons[1:])
        def change_doc(document):
            return replace(document, observations=tuple(replace(r, features=change(r.features))
                for r in document.observations), graph_snapshots=tuple(replace(g,
                nodes=tuple(replace(n, features=change(n.features)) for n in g.nodes))
                for g in document.graph_snapshots))
        episode = replace(self.episode, query=change_doc(self.episode.query), support=tuple(
            SupportRef(change_doc(ref.document), ref.cutoff) for ref in self.episode.support))
        changed = self.model(episode)
        torch.testing.assert_close(original['action_logits'], changed['action_logits'], rtol=0, atol=0)
        for key in original['query_branches']:
            torch.testing.assert_close(original['query_branches'][key],
                                       changed['query_branches'][key], rtol=0, atol=0)

    def test_entry_weight_cap_holds_under_scaling_attack(self):
        layer = BoundedLinear(4, 8, bound=0.5)
        with torch.no_grad():
            layer.weight.mul_(1e6)
        self.assertTrue((layer.effective_weight().norm(dim=0) <= 0.500001).all())

    def test_context_adaptation_centered_on_explicit_reference(self):
        adapts = self.model.centered_context(self.model.reference_contexts)
        weighted = (adapts * self.model.reference_weights[:, None]).sum(dim=0)
        torch.testing.assert_close(weighted, torch.zeros(16), rtol=0, atol=2e-7)

    def test_large_finite_reference_weights_normalize_without_overflow(self):
        model = MultiViewDynamics(reference_contexts=[[0., 0.], [1., -1.]],
                                  reference_weights=[3e38, 3e38])
        torch.testing.assert_close(model.reference_weights, torch.tensor([0.5, 0.5]))
        centered = model.centered_context(model.reference_contexts)
        torch.testing.assert_close(centered.mean(dim=0), torch.zeros(16), rtol=0, atol=2e-7)
        self.assertTrue(torch.isfinite(model(self.episode)['action_logits']).all())

    def test_extreme_reference_context_rejected_before_forward(self):
        self.assertContract('reference_contexts', lambda: MultiViewDynamics(
            reference_contexts=[[3e38, 3e38], [3e38, -3e38]], reference_weights=[1., 1.]))

    def test_reference_weight_float32_underflow_rejected(self):
        self.assertContract('normalized_reference_weights', lambda: MultiViewDynamics(
            reference_contexts=[[0., 0.], [1., -1.]], reference_weights=[1e-300, 1e300]))

    def test_unknown_labels_have_zero_gradient(self):
        output = self.model(self.episode)
        output['action_logits'].retain_grad()
        loss, _ = multilabel_next_action_loss(output, self.target)
        loss.backward()
        self.assertEqual(float(output['action_logits'].grad[3]), 0.)
        self.assertNotEqual(float(output['action_logits'].grad[0]), 0.)

    def test_target_identity_missing_and_censoring_guards(self):
        output = self.model(self.episode)
        for target, code in (
            (replace(self.target, step=5), 'target_identity_or_horizon'),
            (replace(self.target, work_id='different'), 'target_identity_or_horizon'),
            (replace(self.target, actions=(None,) * 4), 'no_observed_target'),
            (replace(self.target, contiguous=False), 'censored_or_noncontiguous_target'),
            (replace(self.target, synthetic=False), 'empirical_target_not_admitted'),
            (replace(self.target, actions=(0.2, 0., 1., 0.)), 'nonbinary_action_target')):
            self.assertContract(code, lambda: multilabel_next_action_loss(output, target))

    def test_actual_phd_report_connected_and_ablated(self):
        episode, _ = toy_episode(with_topology=True)
        snapshot = episode.query.topology_snapshots[0]
        self.assertEqual(snapshot.status, 'ok')
        with_topo = self.model(episode)
        self.assertGreater(float(with_topo['query_branches']['topology'].abs().sum().detach()), 0)
        self.model.gates.freeze([1, 1, 1, 1, 0])
        off = self.model(episode)
        torch.testing.assert_close(off['query_branches']['topology'], torch.zeros(16), rtol=0, atol=0)
        absent = self.model(replace(episode, query=replace(episode.query, topology_snapshots=())))
        torch.testing.assert_close(off['action_logits'], absent['action_logits'], rtol=0, atol=0)

    def test_topology_flag_is_true_ablation(self):
        model = MultiViewDynamics(Config(use_topology=False))
        episode, _ = toy_episode(with_topology=True)
        out = model(episode)
        missing = model(replace(episode, query=replace(episode.query, topology_snapshots=())))
        torch.testing.assert_close(out['action_logits'], missing['action_logits'], rtol=0, atol=0)
        self.assertEqual(float(out['gate_values'][-1].detach()), 0.)

    def test_future_topology_report_rejected(self):
        episode, _ = toy_episode(with_topology=True)
        snapshot = replace(episode.query.topology_snapshots[0], input_prefix_end=5)
        query = replace(episode.query, topology_snapshots=(snapshot,))
        self.assertContract('future_topology', lambda: self.model(replace(episode, query=query)))

    def test_unavailable_topology_preserves_reason(self):
        from research.topology.phd import estimate
        import numpy as np
        report = estimate(np.ones((60, 3)))
        snapshot = from_phd_report(report, prefix_end=3, input_prefix_end=3,
                                  representation_id='synthetic-constant')
        self.assertEqual(snapshot.status, 'unavailable')
        self.assertTrue(snapshot.reason)
        self.assertEqual(snapshot.features.values, (None,) * 5)

    def test_graph_relation_type_is_active(self):
        original = self.model(self.episode)
        graphs = tuple(replace(g, edges=tuple(replace(e, relation=1 - e.relation) for e in g.edges))
                       for g in self.episode.query.graph_snapshots)
        query = replace(self.episode.query, graph_snapshots=graphs)
        changed = self.model(replace(self.episode, query=query))
        self.assertFalse(torch.allclose(original['query_branches']['graph'],
                                       changed['query_branches']['graph']))

    def test_model_measurement_identity_guard(self):
        for fields in ({'measurement_profile': 'different'},
                       {'channel_ids': tuple(reversed(self.episode.query.channel_ids))}):
            query = replace(self.episode.query, **fields)
            self.assertContract('model_measurement_identity_mismatch',
                                lambda: self.model(replace(self.episode, query=query)))

    def test_shared_dependency_group_rejected(self):
        query = replace(self.episode.query, dependency_groups=('copied_prompt_family',))
        ref = self.episode.support[0]
        support = (replace(ref, document=replace(ref.document,
                   dependency_groups=('copied_prompt_family',))),)
        self.assertContract('dependency_group_overlap',
                            lambda: self.model(replace(self.episode, query=query, support=support)))

    def test_finite_but_overflowing_measurement_rejected(self):
        m = Measurement((1e300,) * 4, (1.,) * 4, (None,) * 4)
        self.assertContract('toy_value_out_of_range', lambda: m.validate(4))

    def test_topology_identity_pinned(self):
        episode, _ = toy_episode(with_topology=True)
        top = replace(episode.query.topology_snapshots[0], representation_id='another_encoder')
        query = replace(episode.query, topology_snapshots=(top,))
        self.assertContract('model_topology_identity_mismatch',
                            lambda: self.model(replace(episode, query=query)))

    def test_empty_and_unavailable_graph_are_distinct(self):
        empty = GraphSnapshot(3, 3, 'prefix_recomputed', (), ())
        missing = replace(empty, missing_reason='dependency_unavailable')
        gates = self.model.gates()[:-1]
        self.assertFalse(torch.equal(self.model.graph_branch(empty, gates),
                                     self.model.graph_branch(missing, gates)))

    def test_graph_local_node_permutation_invariant(self):
        graph = self.episode.query.graph_snapshots[2]
        mapping = {0: 2, 1: 0, 2: 1}
        nodes = tuple(sorted((replace(n, local_id=mapping[n.local_id]) for n in graph.nodes),
                             key=lambda n: n.local_id))
        edges = tuple(replace(e, source=mapping[e.source], target=mapping[e.target]) for e in graph.edges)
        remapped = replace(graph, nodes=nodes, edges=edges)
        remapped.validate(4, 2, 3)
        gates = self.model.gates()[:-1]
        a = self.model.graph_branch(graph, gates)
        b = self.model.graph_branch(remapped, gates)
        torch.testing.assert_close(a, b, rtol=1e-6, atol=1e-6)


if __name__ == '__main__':
    unittest.main()
