"""Harmless subprocess tests for the stdlib resource watchdog."""
import contextlib,importlib.util,io,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bounded_profile_under_test',ROOT/'bounded_profile.py');watchdog=importlib.util.module_from_spec(spec);spec.loader.exec_module(watchdog)

class WatchdogTests(unittest.TestCase):
    def test_process_tree_counts_cpu_child(self):
        code="import subprocess,sys;p=subprocess.Popen([sys.executable,'-c','import time;end=time.monotonic()+0.5\\nwhile time.monotonic()<end:pass']);print(p.pid,flush=True);p.wait()"
        p=subprocess.Popen([sys.executable,'-u','-c',code],stdout=subprocess.PIPE,text=True)
        try:
            int(p.stdout.readline());time.sleep(.15);rss,cpu=watchdog.process_tree(p.pid)
            self.assertGreater(rss,5*1024**2);self.assertGreater(cpu,.03)
        finally:p.wait();p.stdout.close()
    def _stops(self,rss,cpu,expected):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'metrics.json'
            args=['bounded_profile.py','--metrics',str(path),'--',sys.executable,'-c','import time;time.sleep(5)']
            with patch.object(sys,'argv',args),patch.object(watchdog,'process_tree',return_value=(rss,cpu)),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:watchdog.main()
            self.assertNotEqual(raised.exception.code,0);self.assertEqual(json.loads(path.read_text())['stopped_reason'],expected)
    def test_rss_limit_terminates_owned_subprocess(self):self._stops(3*1024**3,0,'2GiB_process_tree_RSS')
    def test_cpu_limit_terminates_owned_subprocess(self):self._stops(0,1201,'20minute_aggregate_CPU')

if __name__=='__main__':unittest.main(verbosity=2)
