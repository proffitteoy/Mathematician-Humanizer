"""One explicitly synthetic optimizer-step smoke check; writes no model weights."""
from dataclasses import asdict
import json
import platform
import torch
from .fixtures import toy_episode
from .model import MultiViewDynamics, multilabel_next_action_loss


def main():
    torch.set_num_threads(1)
    torch.manual_seed(20261001)
    episode, target = toy_episode(with_topology=True)
    model = MultiViewDynamics(reference_contexts=[[0, 0], [1, -1]], reference_weights=[1, 3])
    output = model(episode)
    loss, loss_info = multilabel_next_action_loss(output, target)
    # Demonstrate actual prediction gradients, before adding any gate penalty.
    loss.backward()
    names = ('global_branch', 'sequence_branch', 'graph_branch', 'topology_branch',
             'stable_head', 'context_head', 'residual_head', 'action_head', 'gates')
    gradients = {name: float(sum(p.grad.abs().sum().item() for p in getattr(model, name).parameters()
                                if p.grad is not None)) for name in names}
    before = model.action_head.weight.detach().clone()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    optimizer.step()
    changed = not torch.equal(before, model.action_head.weight.detach())
    after = model(episode)
    report = {
        'schema': 'learned-synthetic-smoke/0.1',
        'status': 'synthetic_gradient_and_one_step_smoke_only',
        'seed': 20261001, 'python': platform.python_version(), 'torch': torch.__version__,
        'device': 'cpu', 'config': asdict(model.cfg),
        'parameter_count': sum(p.numel() for p in model.parameters()),
        'synthetic_explicit_channels': list(episode.query.channel_ids),
        'new_operational_linguistic_features': 0,
        'empirical_documents_used': 0, 'personal_documents_used': 0,
        'empirical_models_fitted': 0, 'synthetic_optimizer_steps': 1,
        'model_weights_written': False, 'external_downloads': 0,
        'topology_input': 'actual PH0 numerical report on seeded synthetic cube, not text embeddings',
        'topology_report_status': episode.query.topology_snapshots[0].status,
        'prediction_loss_before_step': float(loss.detach()),
        'loss_metadata': loss_info, 'prediction_gradient_l1_by_branch': gradients,
        'action_head_parameters_changed': changed,
        'all_output_logits_finite_after_step': bool(torch.isfinite(after['action_logits']).all()),
        'claims_not_established': ['natural-language construct validity', 'stable/context identification',
            'cross-topic author generalization', 'selection stability', 'semantic edit preservation'],
    }
    if not changed or not all(value > 0 for value in gradients.values()) or not report[
            'all_output_logits_finite_after_step']:
        raise RuntimeError('synthetic_smoke_failed')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
