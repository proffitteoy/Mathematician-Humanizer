"""Synthetic atomic-persistence failures; no natural input or model."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner as r
import test_independent_faults as independent


class AtomicRecoveryTests(unittest.TestCase):
    # Reuse fixtures only; do not duplicate the twelve independent test cases.
    setUp = independent.IndependentFaultTests.setUp
    run_fixture = independent.IndependentFaultTests.run_fixture
    rows = independent.IndependentFaultTests.rows
    def test_one_time_cleanup_failure_retains_terminal_status(self):
        original=Path.unlink; failed=False
        def injected(path,*args,**kwargs):
            nonlocal failed
            if path.name.startswith('result-000000.private.json.tmp-') and not failed:
                failed=True;raise OSError('synthetic cleanup failure')
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',new=injected):report=self.run_fixture()
        self.assertTrue(failed)
        self.assertEqual(report['stop_reason'],'output_temp_cleanup_failure')
        self.assertEqual([x['status'] for x in self.rows()],['failed','not_run','not_run'])
        self.assertEqual(report['dimension_conditional_on_numerical_success']['n'],0)
        self.assertTrue((self.out/'run-finished.private.json').exists())
        self.assertTrue(list(self.out.glob('result-*.tmp-*')))

    def test_persistent_ledger_replace_failure_has_no_terminal_receipt(self):
        original=r.os.replace; activated=False
        def injected(src,dst):
            nonlocal activated
            if Path(dst).name=='ledger.private.json':
                value=json.loads(Path(src).read_text())
                if value['records'][0]['status']=='ok':activated=True
                if activated:raise OSError('synthetic persistent disk failure')
            return original(src,dst)
        with patch.object(r.os,'replace',side_effect=injected):
            with self.assertRaisesRegex(r.FatalRunError,'output_io_failure'):self.run_fixture()
        self.assertFalse((self.out/'run-finished.private.json').exists())
        self.assertFalse((self.out/'aggregate.public.json').exists())
        self.assertEqual(list(self.out.glob('*.tmp-*')),[])

    def test_primary_failure_not_masked_by_cleanup_failure(self):
        original_link=r.os.link;original_unlink=Path.unlink
        def injected_link(src,dst):
            if Path(dst).name=='result-000000.private.json':raise OSError('primary write failure')
            return original_link(src,dst)
        def injected_unlink(path,*args,**kwargs):
            if path.name.startswith('result-000000.private.json.tmp-'):raise OSError('secondary cleanup failure')
            return original_unlink(path,*args,**kwargs)
        with patch.object(r.os,'link',side_effect=injected_link),patch.object(Path,'unlink',new=injected_unlink):
            report=self.run_fixture()
        self.assertEqual(report['stop_reason'],'output_io_failure')
        self.assertTrue((self.out/'run-finished.private.json').exists())
        self.assertEqual(report['dimension_conditional_on_numerical_success']['n'],0)

    def test_one_time_directory_sync_failure_is_recoverable_stop(self):
        original=r.os.fsync;failed=False
        def injected(fd):
            nonlocal failed
            import stat,os
            if stat.S_ISDIR(os.fstat(fd).st_mode) and (self.out/'result-000000.private.json').exists() and not failed:
                failed=True;raise OSError('synthetic directory sync failure')
            return original(fd)
        with patch.object(r.os,'fsync',side_effect=injected):report=self.run_fixture()
        self.assertTrue(failed)
        self.assertEqual(report['stop_reason'],'output_directory_sync_failure')
        self.assertEqual(report['dimension_conditional_on_numerical_success']['n'],0)
        self.assertTrue((self.out/'run-finished.private.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
