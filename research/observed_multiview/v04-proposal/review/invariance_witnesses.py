"""Original synthetic algebra witnesses only. No corpus, NLP, model fitting or imports."""
import json
import math


def loss(a, observed, corrupt):
    return math.log1p(math.exp((a + corrupt) - (a + observed)))


def unordered_graph_readout(units):
    """A two-round sum-aggregation toy graph; word names are opaque local IDs."""
    states = [value for value, words in units]
    for _ in range(2):
        word_states = {}
        for h, (_, words) in zip(states, units):
            for word in words:
                word_states[word] = word_states.get(word, 0) + h
        states = [h + sum(word_states[w] for w in words)
                  for h, (_, words) in zip(states, units)]
    return sum(states)


def recurrence_distance(units):
    positions = {}
    for i, (_, words) in enumerate(units):
        for word in words:
            positions.setdefault(word, []).append(i)
    return sum(b-a for p in positions.values() for a, b in zip(p, p[1:]))


checks = {}
# Binary-exact values make cancellation tests insensitive to decimal rounding.
values = [loss(a, 1.25, -0.75) for a in (0.0, 2.0, -4.0, 16.0)]
checks['additive_global_cancellation'] = len(set(values)) == 1
h = 0.125
checks['additive_global_finite_difference_zero'] = (loss(h, 1.25, -0.75)-loss(-h, 1.25, -0.75))/(2*h) == 0.0
x, y = (1, 2, 3, 4), (1, 3, 2, 4)
checks['bag_and_endpoints_invariant'] = sorted(x) == sorted(y) and (x[0], x[-1]) == (y[0], y[-1])
checks['order_summary_is_not_invariant'] = sum((b-a)**2 for a,b in zip(x,x[1:])) != sum((b-a)**2 for a,b in zip(y,y[1:]))
u = [(1, ('a',)), (2, ('b',)), (3, ('a',)), (4, ('c',))]
v = [u[0], u[2], u[1], u[3]]
checks['unordered_graph_pool_invariant'] = unordered_graph_readout(u) == unordered_graph_readout(v)
rename = {'a':'opaque_9', 'b':'opaque_2', 'c':'opaque_6'}
w = [(h, tuple(rename[t] for t in words)) for h, words in u]
checks['word_node_relabel_invariant'] = unordered_graph_readout(u) == unordered_graph_readout(w)
checks['candidate_distance_can_change'] = recurrence_distance(u) != recurrence_distance(v)
checks['candidate_score_presentation_antisymmetry'] = (1.25 - -0.75) == -(-0.75 - 1.25)
# Under a known representation alias, a deterministic shared scorer ties by definition.
visible_a, visible_b = (1, 0, 1, 0), (1, 0, 1, 0)
checks['representation_alias_must_tie'] = sum(visible_a) == sum(visible_b)
assert all(checks.values()), checks
print(json.dumps({'scope':'synthetic_algebra_only_not_production_or_model_validation',
                  'checks':checks, 'passed':sum(checks.values()), 'total':len(checks),
                  'corpus_body_reads':0,'nlp_parse_calls':0,'model_fit_calls':0,
                  'illustrative_zero_errors_sample_for_one_sided_95pct_upper_error_below_1pct':
                  math.ceil(math.log(0.05)/math.log(0.99))}, indent=2))
