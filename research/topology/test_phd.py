import unittest
from dataclasses import replace
import numpy as np
from scipy.spatial.distance import cdist
from phd import Config, mst_edges, sample_sizes, make_plan, estimate


def kruskal(d):
    n=len(d); parents=list(range(n))
    def root(a):
        while parents[a] != a:
            parents[a]=parents[parents[a]]; a=parents[a]
        return a
    result=[]
    for w,i,j in sorted((d[i,j],i,j) for i in range(n) for j in range(i)):
        a,b=root(i),root(j)
        if a!=b:
            parents[a]=b; result.append(float(w))
    return np.asarray(result)


class MSTTests(unittest.TestCase):
    def test_singleton(self): self.assertEqual(len(mst_edges([[0]])),0)
    def test_line(self): np.testing.assert_allclose(sorted(mst_edges(cdist([[0],[2],[3],[7]],[[0],[2],[3],[7]]))),[1,2,4])
    def test_duplicates_and_ties(self):
        x=np.array([[0,0],[0,0],[1,0],[0,1],[1,1]])
        np.testing.assert_allclose(sorted(mst_edges(cdist(x,x))),[0,1,1,1])
    def test_kruskal_reference(self):
        rng=np.random.default_rng(23)
        for n in range(2,25):
            x=rng.integers(-3,4,size=(n,3));d=cdist(x,x)
            np.testing.assert_allclose(sorted(mst_edges(d)),sorted(kruskal(d)))
    def test_permutation(self):
        x=np.random.default_rng(3).normal(size=(20,4));d=cdist(x,x);p=np.arange(20)[::-1]
        np.testing.assert_allclose(sorted(mst_edges(d)),sorted(mst_edges(d[np.ix_(p,p)])))
    def test_invalid(self):
        for d in [[],[[0,1]],[[0,-1],[-1,0]],[[0,1],[2,0]],[[0,np.nan],[np.nan,0]]]:
            with self.assertRaises(ValueError):mst_edges(d)


class PHDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x=np.random.default_rng(8).normal(size=(100,3))
        cls.c=Config(seed=12,reruns=2)
        cls.plan=make_plan(100,sample_sizes(100,cls.c.protocol),cls.c)
    def test_seed_reproducibility(self): self.assertEqual(estimate(self.x,self.c),estimate(self.x,self.c))
    def test_known_plan(self):
        a=estimate(self.x,self.c);b=estimate(self.x,self.c,self.plan)
        self.assertEqual(a['runs'],b['runs']);self.assertEqual(a['status'],'ok')
    def test_rescaling_and_rigid_motion(self):
        a=estimate(self.x,self.c,self.plan)
        rot=np.linalg.qr(np.random.default_rng(2).normal(size=(3,3)))[0]
        b=estimate(7*self.x@rot+np.array([8,3,-5]),self.c,self.plan)
        self.assertAlmostEqual(a['dimension'],b['dimension'],places=10)
        for ar,br in zip(a['runs'],b['runs']):
            np.testing.assert_allclose(np.array(ar['median_energies'])*7,br['median_energies'])
    def test_matched_permutation_plan(self):
        perm=np.random.default_rng(11).permutation(100);inverse=np.argsort(perm)
        transformed=[[[[int(inverse[i]) for i in subset] for subset in level] for level in run] for run in self.plan]
        a=estimate(self.x,self.c,self.plan);b=estimate(self.x[perm],self.c,transformed)
        self.assertAlmostEqual(a['dimension'],b['dimension'],places=12)
    def test_aggregation_is_mean_slope(self):
        r=estimate(self.x,self.c)
        self.assertAlmostEqual(r['dimension'],1/(1-np.mean([x['slope'] for x in r['runs']])))
    def test_constant_cloud(self): self.assertEqual(estimate(np.zeros((100,2)))['reason'],'zero_or_nonfinite_mst_energy')
    def test_two_atoms_abstain(self):
        x=np.concatenate([np.zeros((50,2)),np.ones((50,2))])
        self.assertEqual(estimate(x)['reason'],'insufficient_distinct_points')
    def test_short(self): self.assertEqual(estimate(np.zeros((49,2)))['reason'],'fewer_than_50_points')
    def test_resource(self): self.assertEqual(estimate(np.zeros((513,2)))['reason'],'resource_cap')
    def test_grid_profiles(self):
        self.assertEqual(sample_sizes(100,'paper_prose_v1'),[40,49,57,66,74,83,91,100])
        self.assertEqual(sample_sizes(100,'gptid_notebook_v1'),list(range(40,92,8)))
        self.assertEqual(estimate(self.x,Config(protocol='gptid_class_defaults_v1'))['reason'],'invalid_or_insufficient_sampling_grid')
    def test_notebook_runs(self):
        r=estimate(self.x,Config(protocol='gptid_notebook_v1',reruns=1))
        self.assertEqual(len(r['runs'][0]['draw_energies'][0]),9)
        self.assertEqual(len(r['runs'][0]['draw_energies'][-1]),3)
    def test_plan_rejects_replacement(self):
        plan=make_plan(100,sample_sizes(100,self.c.protocol),self.c);plan[0][0][0][0]=plan[0][0][0][1]
        with self.assertRaises(ValueError):estimate(self.x,self.c,plan)
    def test_input_rejects_nonfinite(self):
        with self.assertRaises(ValueError):estimate([[np.nan]])
    def test_invalid_config(self):
        for c in [Config(reruns=0),Config(seed=-1),Config(slope_margin=0),Config(max_cloud_points=5000)]:
            with self.assertRaises(ValueError):estimate(self.x,c)
    def test_cloud_not_modified(self):
        old=self.x.copy();estimate(self.x,self.c);np.testing.assert_array_equal(self.x,old)


if __name__=='__main__':unittest.main()
