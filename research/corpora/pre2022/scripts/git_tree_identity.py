"""Reconstruct Git tree object identity from a complete recursive manifest."""
import collections,hashlib

def tree_root_sha1(manifest):
    if manifest.get('truncated'):raise ValueError('truncated_tree_manifest')
    children=collections.defaultdict(list);expected={}
    for row in manifest['tree']:
        parts=row['path'].rsplit('/',1);directory,name=parts if len(parts)==2 else ('',parts[0])
        children[directory].append((name,row))
        if row['type']=='tree':expected[row['path']]=row['sha']
    calculated={}
    for directory,rows in children.items():
        key=lambda x:(x[0]+('/' if x[1]['type']=='tree' else '')).encode('utf-8')
        payload=b''.join(str(int(r['mode'])).encode()+b' '+name.encode('utf-8')+b'\0'+bytes.fromhex(r['sha']) for name,r in sorted(rows,key=key))
        calculated[directory]=hashlib.sha1(b'tree '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
    if any(calculated.get(k)!=v for k,v in expected.items()):raise ValueError('subtree_object_hash_mismatch')
    return calculated['']
