#!/usr/bin/env python3
"""Fresh synthetic-only replay receipt; no natural cache or raw text access."""
import json,sys,time,unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));torch.set_num_threads(2);start=time.monotonic()
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
receipt={'kind':'post_reset_reconstructed_synthetic_implementation_replay','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
    'success':result.wasSuccessful(),'natural_cache_bodies_read':0,'raw_test_bodies_read':0,'davinci_bodies_read':0,'empirical_optimizer_fits':0,
    'wall_seconds':time.monotonic()-start,'scope':'fixed candidate instrument prediction; no style, author or discourse model'}
(ROOT/'SYNTHETIC_CHECKS.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));sys.exit(not result.wasSuccessful())
