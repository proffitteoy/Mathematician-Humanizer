"""Original local control-flag tests. Never reads natural artifacts or fits."""
import json,pathlib,tempfile,threading,time,unittest
from research.observed_sequence.run_fit import FileControl
from research.observed_sequence.fit import FitStopped
class TestFileControl(unittest.TestCase):
 def test_run_initialization_and_heartbeat(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);c=FileControl(p/'control.json',p/'status.json',interval=0);c();self.assertEqual(json.loads((p/'status.json').read_text())['status'],'run')
 def test_existing_stop_is_never_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);f=p/'control.json';f.write_text('{"state":"stop"}');c=FileControl(f,p/'status.json',interval=0)
   with self.assertRaisesRegex(FitStopped,'external_stop'):c()
   self.assertEqual(json.loads(f.read_text())['state'],'stop')
 def test_pause_and_resume(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);f=p/'control.json';f.write_text('{"state":"pause"}');c=FileControl(f,p/'status.json',interval=0)
   def resume():
    time.sleep(.12);tmp=p/'new.json';tmp.write_text('{"state":"run"}');tmp.replace(f)
   t=threading.Thread(target=resume);t.start();start=time.monotonic();c();t.join();self.assertGreaterEqual(time.monotonic()-start,.1);self.assertEqual(c.state,'run')
 def test_invalid_or_deleted_control_fails_closed(self):
  for data in ('{}','garbage','{"state":"ignore"}'):
   with tempfile.TemporaryDirectory() as d:
    p=pathlib.Path(d);f=p/'control.json';f.write_text(data);c=FileControl(f,p/'status.json',interval=0)
    with self.assertRaisesRegex(FitStopped,'control_missing_or_invalid'):c()
if __name__=='__main__':unittest.main()
