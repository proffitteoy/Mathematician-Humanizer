from pathlib import Path
import json,hashlib,re,subprocess,itertools
P=Path(__file__).parent
S=P.parents[2]/'skills/tao-inspired-math-exposition'
reviews={
'english-max-cut':('exposition',{
'goal':('We will show that every finite simple undirected graph has a cut containing at least half of its edges.','开头直接给出对象、量词和目标；初等图论读者只需理解两侧分组。'),
'assumptions':('There is no requirement that the two groups have equal size.','有限、简单、无向图在首段声明；不加入平衡割约束。简单图无自环，单边交叉概率确为一半；空边集另行覆盖。'),
'reasoning':('Linearity of expectation gives','每条边的两个顶点有四种等概率赋值，两种交叉。有限求和线性性不要求边指标联合独立。有限平均不超过最大值，所以存在至少m/2条边的割，整数性给出向上取整。局部改进终止后逐点跨边数至少度数一半，求和得到2X至少m。'),
'boundary':('Its expectation is one half, but that is not even a possible cut size.','单边随机割分布为0与1各半，区分期望和单次结果；三角形最多2条交叉，二部图全部边可交叉，说明下界不总等于最大割。'),
'originality':('A useful way around this difficulty is to begin with a partition chosen without trying to make it good.','依据通用概率方法独立撰写，未复制博客原句。仅读取技能公开统计与讲解卡，未读取留出或私有语料；不声称全库逐句排重或作者相似度已证实。')}),
'chinese-least-squares':('exposition',{
'goal':('向量 $x$ 是系数，向量 $Ax$ 才是拟合结果','明确分离系数唯一性与拟合值唯一性，避免不说明对象的答案唯一说法。'),
'assumptions':('这里采用通常的欧氏范数，不附加约束，也不加入正则项。','有限维实矩阵、欧氏平方损失、所有系数无约束。秩不足明确为rank A<n，而非含混地与行数比较。'),
'reasoning':('全部最优系数恰好是 $x_*+\\ker A$','有限维列空间闭，投影存在。误差正交分解的第二项仅在拟合向量相同时为零。Ax=Ax*等价于x-x*在核内，从而满列秩恰好对应系数唯一。示例目标为(x1+x2-2)^2+1，最优线x1+x2=2、拟合(2,0)、最小值1均复算。'),
'boundary':('这是增加选择标准后的唯一性','最小范数代表与原优化问题区分；奇异正规方程不能求逆。严格凸性只在拟合空间必然成立，系数核方向目标不变。'),
'originality':('残差的第二个分量无法消去','选用自足的二乘二矩阵原创说明，数学事实属标准线性代数；未读取留出或私有语料，未复制作者原句，不作作者相似度主张。')}),
'chinese-tower-property':('exposition',{
'goal':('先按细分组取平均，再按粗分组取平均，与直接按粗分组取平均相同。','讲义目标在定义前明确，并由嵌套分组公式和带权练习落实。'),
'assumptions':('每个点的概率都为正','有限概率空间正点质量使所有非空原子分母为正；G包含于H给出粗细嵌套。随后准确扩展到含零点质量时的几乎处处版本。'),
'reasoning':('每个分母 $\\mathbb P(B_j)$ 都被权重抵消','在粗原子C上用细原子B_j加权，P(B_j)与内层均值分母抵消；不交并把求和恢复为C内逐点加权总和。证明适用于任意粗原子故逐点相等。'),
'boundary':('直接平均得到五点五','三等概率点细组大小2与1，细均值1和10，真实加权平均4；无权均值5.5有误。练习检验分组后仍需保留概率。'),
'originality':('练习的目的是检验权重，而非背诵公式。','例子和练习为本任务独立编写，未读取留出或私有语料、未复制作者原句；基础条件期望定理不冒称原创数学成果。')}),
'chinese-weak-convergence':('learning',{
'goal':('可以先把“所有测试都看不出差别”中的量词写出来','以固定测试与变动测试的差别作为明确理解缺口，非泛泛学习感想。'),
'assumptions':('这里讨论实数轴上概率测度的弱收敛','声明概率测度与有界连续测试，不混同Banach空间向量弱收敛；一致检验另加无穷范数至多一的归一化。'),
'reasoning':('由零点处的连续性，它们的差趋于零','delta点质量积分是函数取值，因此每个固定连续f由1/n趋零得到弱收敛。f_n=min(1,n|x|)逐个连续有界且在1/n和0取值1与0，否定整个有界连续单位球的一致误差收敛。'),
'boundary':('极限测度恰好把全部质量放在那里','B=(0,infty)对所有n概率1、极限delta0概率0，边界{0}有全部极限质量。文稿仅展示失败边界，不把该例未经证明地推广为完整集合收敛定理。'),
'learning_test':('限制变化速度，正好排除了上面越来越陡的 $f_n$。','修正测试为共同1-Lipschitz函数后，本例每个积分差至多距离1/n，故一致上界可验证。明确结论只针对该例，不偷换成所有弱收敛序列的一般断言。'),
'originality':('这次检验留下一个可以继续复算的修正。','围绕标准点质量序列独立组织理解检验，无虚构个人经历；未读取留出或私有语料、未复制作者原句，不声称作者相似度。')})}
for name,(mode,checks) in reviews.items():
 t=(P/(name+'.txt')).read_text()
 o={'mode':mode,'text_sha256':hashlib.sha256(t.encode()).hexdigest(),'checks':{k:{'status':'pass','quote':v[0],'reason':v[1]} for k,v in checks.items()}}
 rp=P/(name+'.review.json');rp.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
 subprocess.run(['python',str(S/'scripts/audit.py'),'--text',str(P/(name+'.txt')),'--review',str(rp),'--out',str(P/(name+'.audit.json'))],check=True)
# Reproducible bounded arithmetic checks, not substitutes for the general proofs.
counts=0
for n in range(6):
 edges=list(itertools.combinations(range(n),2))
 for bits in range(1<<len(edges)):
  es=[e for i,e in enumerate(edges) if bits>>i&1]
  sizes=[sum(((a>>u)&1)!=((a>>v)&1) for u,v in es) for a in range(1<<n)]
  assert 2*sum(sizes)==len(sizes)*len(es)
  assert 2*max(sizes)>=len(es)
  counts+=1
from fractions import Fraction as F
assert (F(0)+2+10)/3==4
assert F(2,3)*1+F(1,3)*10==4
assert (F(1)+10)/2==F(11,2)
for t in range(-10,11):
 assert (t+(2-t)-2)**2+1==1
for n in range(1,101):
 assert min(1,n*abs(F(1,n)))-min(1,n*abs(F(0)))==1
report={'status':'PASS','text_sha256':{n:hashlib.sha256((P/(n+'.txt')).read_bytes()).hexdigest() for n in reviews},'graph_enumeration':{'labelled_simple_graphs':counts,'vertex_counts':[0,1,2,3,4,5]},'other_checks':['tower exercise exact rational weighted average','21 least-squares points on minimizer line','100 exact rational weak-convergence test-function evaluations'],'limits':'Bounded numerical checks supplement, but do not prove, general mathematical statements. Manual proof review is separate from language statistics.'}
(P/'mathematical-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
