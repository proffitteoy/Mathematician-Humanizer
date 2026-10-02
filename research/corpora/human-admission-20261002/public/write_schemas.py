"""Generate versioned structural JSON schemas; semantic checks live in loader.py."""
import json
from pathlib import Path
from loader import RECORD_VERSION, REGISTRY_VERSION, read_jsonl


def schema_for(values):
    types = set('null' if x is None else 'boolean' if type(x) is bool else 'integer' if type(x) is int else 'number' if type(x) is float else 'string' if isinstance(x, str) else 'array' if isinstance(x, list) else 'object' for x in values)
    result = {'type': next(iter(types)) if len(types) == 1 else sorted(types)}
    objects = [x for x in values if isinstance(x, dict)]
    if objects:
        keys = sorted(set().union(*(set(x) for x in objects)))
        result.update(properties={k: schema_for([x[k] for x in objects if k in x]) for k in keys},
                      required=sorted(set.intersection(*(set(x) for x in objects))), additionalProperties=False)
    arrays = [x for x in values if isinstance(x, list)]
    if arrays:
        items = [x for a in arrays for x in a]
        result['items'] = schema_for(items) if items else {}
    return result


def main():
    root = Path(__file__).resolve().parent
    for stem, values, version in [('human-corpus-record', read_jsonl(root / 'ADMITTED_DOCUMENTS.jsonl'), RECORD_VERSION),
                                 ('human-corpus-registry', [json.loads((root / 'REGISTRY.json').read_text())], REGISTRY_VERSION)]:
        result = {'$schema': 'https://json-schema.org/draft/2020-12/schema', '$id': 'urn:style-compiler:' + version.replace('/', ':'),
                  'title': version, **schema_for(values)}
        result['properties']['schema_version'] = {'const': version}
        if stem == 'human-corpus-record':
            result['properties']['admission']['properties']['date_cutoff_required'] = {'const': False}
            result['properties']['admission']['properties']['historical_snapshot_required'] = {'const': False}
            # A future valid record may have unknown dates. Date values never gate intake.
            result['properties']['dates']['properties']['publication_date_claim'] = {'type': ['string', 'null']}
        (root / (stem + '.schema.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
