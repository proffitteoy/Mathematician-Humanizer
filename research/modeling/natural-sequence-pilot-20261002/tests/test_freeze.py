"""Freeze must authenticate artifacts against successful fit decisions."""
import json,tempfile,unittest
from pathlib import Path
from experimental_natural.freeze import freeze_bundle,verify_frozen_bundle,sha256
from experimental_natural.plan import registered_run_grid
from experimental_natural.schema import CONTRACT_PATH

class FreezeTests(unittest.TestCase):
    def test_arbitrary_existing_checkpoint_is_not_accepted(self):
        grid=registered_run_grid()
        class Ledger:
            path=Path('/never_read_ledger')
            def assert_complete(self,expected):return True
            def events(self):return [{'event':'completed','run_id':r['id'],'checkpoint_sha256':'0'*64} for r in grid]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);checkpoint=root/'arbitrary.pt';checkpoint.write_bytes(b'arbitrary existing bytes')
            transforms={k:root/(k+'.json') for k in ('pooled','baike','web')}
            for p in transforms.values():p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'completed fit ledger'):
                freeze_bundle(root/'frozen.json',contract_path=CONTRACT_PATH,transform_paths=transforms,
                    checkpoint_paths={r['id']:checkpoint for r in grid},ledger=Ledger(),approved_panels=['seen_generator','generator_transfer'])
            self.assertFalse((root/'frozen.json').exists())
    def test_post_freeze_ledger_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ledger=root/'ledger.jsonl';ledger.write_text('completed original run\n')
            manifest={'contract_sha256':sha256(CONTRACT_PATH),'fit_ledger_path':str(ledger),'fit_ledger_sha256':sha256(ledger),
                'code_sha256':{},'transforms':{},'checkpoints':{}}
            path=root/'manifest.json';path.write_text(json.dumps(manifest))
            verify_frozen_bundle(path,CONTRACT_PATH)
            ledger.write_text('changed selected epoch\n')
            with self.assertRaisesRegex(ValueError,'Fit ledger changed'):verify_frozen_bundle(path,CONTRACT_PATH)
    def test_missing_completed_identity_cannot_hide_behind_ledger_helper(self):
        grid=registered_run_grid()
        class Ledger:
            def assert_complete(self,expected):return True
            def events(self):return []
        with self.assertRaisesRegex(ValueError,'Completed ledger identities'):
            freeze_bundle('/never_written',contract_path=CONTRACT_PATH,transform_paths={k:'/never_read' for k in ('pooled','baike','web')},
                checkpoint_paths={r['id']:'/never_read' for r in grid},ledger=Ledger(),approved_panels=['seen_generator','generator_transfer'])

if __name__=='__main__':unittest.main(verbosity=2)
