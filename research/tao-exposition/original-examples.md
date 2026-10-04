# 原创试写

各篇的单独正文、量测和审核回执在examples目录；本汇编只供阅读。它们是本次原创文本，不是陶哲轩原文或译文。

## 中文数学说明：最小二乘

最小二乘中，“答案是否唯一”要先说明答案指什么。设 $A$ 是实 $m\times n$ 矩阵，$b\in\mathbb R^m$，我们要在所有 $x\in\mathbb R^n$ 中最小化 $\|Ax-b\|_2^2$。这里采用通常的欧氏范数，不附加约束，也不加入正则项。向量 $x$ 是系数，向量 $Ax$ 才是拟合结果；这两个对象的唯一性并不相同。

先把变量换成 $y=Ax$。允许的 $y$ 恰好组成列空间 $M=\operatorname{im}A$，问题于是变成在 $M$ 内找离 $b$ 最近的点。有限维子空间是闭的，正交投影定理保证这样的点存在。记它为 $y_*$，则 $b-y_*$ 与 $M$ 正交。对任意 $y\in M$，勾股恒等式给出 $\|b-y\|_2^2=\|b-y_*\|_2^2+\|y-y_*\|_2^2$。第二项非负，而且仅在 $y=y_*$ 时为零。因此拟合向量唯一；这一结论不要求列向量线性无关。

障碍只在从拟合结果恢复系数时出现。选取一个满足 $Ax_*=y_*$ 的向量，那么全部最优系数恰好是 $x_*+\ker A$。一方面，加上核中的向量不改变拟合值；另一方面，两个最优系数的拟合值都必须等于 $y_*$，相减后便落在核中。所以系数唯一当且仅当 $\ker A=\{0\}$，也就是 $A$ 满列秩。若“秩不足”明确指 $\operatorname{rank}A<n$，最优系数实际上一定不唯一，而不只是有可能不唯一。

算一个可以直接检查的例子。取 $A=\begin{pmatrix}1&1\\0&0\end{pmatrix}$，$b=(2,1)^T$。目标函数为 $(x_1+x_2-2)^2+1$，最小值是一，所有满足 $x_1+x_2=2$ 的系数都最优。比如 $(2,0)^T$ 与 $(1,1)^T$ 不同，却都给出拟合向量 $(2,0)^T$。残差的第二个分量无法消去，改变系数也不能把它变成可拟合的方向。

正规方程 $A^TAx=A^Tb$ 同样刻画这些最优系数，但矩阵 $A^TA$ 奇异时不能直接求逆。若另外要求系数范数最小，则在上述解集中还能选出唯一代表；例子中就是 $(1,1)^T$。这是增加选择标准后的唯一性，不能反过来说原来的最小二乘已经确定了系数。区分系数空间与拟合空间，正是避免这一混淆的关键。

也可以从严格凸性看清问题所在。关于拟合向量，平方距离是严格凸的，所以两个不同的拟合结果不可能同时最优。关于系数，如果沿着核中的非零方向移动，目标函数完全不变，就谈不上严格凸。把这两种凸性混在一起，会误以为平方损失天然保证所有未知量唯一。


## 中文讲义：塔式性质

在有限概率空间上，条件期望可以理解为按现有信息分组后取平均。本节要证明：先按细分组取平均，再按粗分组取平均，与直接按粗分组取平均相同。这个陈述的关键是分组必须嵌套；两次任意的平均操作没有这样的保证。

设 $\Omega$ 有限，每个点的概率都为正，$X:\Omega\to\mathbb R$。令 $\mathcal G\subseteq\mathcal H$ 为两个子 $\sigma$ 代数。每个子代数对应一个由其原子组成的分割：原子内部的点，凭该信息无法区分。包含关系意味着每个 $\mathcal G$ 原子都是若干个 $\mathcal H$ 原子的并。对信息 $\mathcal H$，条件期望 $Y=\mathbb E[X\mid\mathcal H]$ 在原子 $B$ 上恒等于 $\sum_{\omega\in B}X(\omega)\mathbb P(\{\omega\})/\mathbb P(B)$。

塔式性质说 $\mathbb E[Y\mid\mathcal G]=\mathbb E[X\mid\mathcal G]$。要证明两个按粗分组保持常数的函数相等，只需检查每个粗原子。固定一个 $\mathcal G$ 原子 $C$，将它写成互不相交的细原子之并 $C=B_1\cup\cdots\cup B_r$。在 $C$ 上，左边的值为 $\mathbb P(C)^{-1}\sum_j\mathbb P(B_j)Y|_{B_j}$。代入定义后，每个分母 $\mathbb P(B_j)$ 都被权重抵消，所得恰好是 $\mathbb P(C)^{-1}\sum_{\omega\in C}X(\omega)\mathbb P(\{\omega\})$，即右边的值。证明用到的是带权平均，不能把各组平均数不加权地再平均。

正概率的假设只是省去零分母。如果允许零概率点，只在正概率原子上使用上述公式，零概率原子上的值任取；结论应表述为几乎处处相等。信息嵌套则直接保证一个粗原子能完整拆成细原子，这是本证明的结构性步骤。

练习的目的是检验权重，而非背诵公式。取三个等概率点 $a,b,c$，令 $X$ 的值依次为 $0,2,10$。细分组为 $\{a,b\},\{c\}$，粗分组只有整个空间。计算两层条件期望，并指出把两个细组平均数直接相加除以二错在哪里。

答案：细组上的平均数分别为一和十，故 $Y$ 在三个点上的值为 $1,1,10$。再取粗平均得到四，也等于 $X$ 的平均数。两个组的概率是三分之二和三分之一，因此正确计算是一乘三分之二加十乘三分之一；直接平均得到五点五，是把概率不同的两组误当成等概率。塔式性质保留了原来的概率权重，并没有把组改造成新的等概率点。

实际使用时，可以先画出两层分组，再检查每个粗组是否由完整细组拼成。这个小检查有助于发现信息包含关系写反或根本不存在的情形。


## 中文学习札记：弱收敛

检验“弱收敛”是否理解准确，可以先把“所有测试都看不出差别”中的量词写出来。这里讨论实数轴上概率测度的弱收敛：$\mu_n\Rightarrow\mu$ 意味着对每个有界连续函数 $f:\mathbb R\to\mathbb R$，都有 $\int f\,d\mu_n\to\int f\,d\mu$。测试函数必须先固定，然后才让 $n$ 趋于无穷；定义并没有允许每一步随意更换测试标准。

取 $\mu_n=\delta_{1/n}$ 与 $\mu=\delta_0$，其中 $\delta_x$ 表示集中在点 $x$ 的单位质量。对固定的有界连续函数 $f$，两个积分分别为 $f(1/n)$ 与 $f(0)$。由零点处的连续性，它们的差趋于零，因而这列测度弱收敛。这个验证没有估计所有函数的共同误差；它只是对任意一个已固定的函数使用连续性。

理解检验的下一步是尝试加强结论：能否说对所有有界连续函数，误差一致趋于零？为免函数任意放大，先限制 $\|f\|_\infty\leq1$。即使这样也不成立。令 $f_n(x)=\min(1,n|x|)$，每个 $f_n$ 都连续且有界，却满足 $f_n(1/n)=1$、$f_n(0)=0$。所以在这一类测试函数上取误差上确界，结果始终至少为一。失败的原因是这些函数在零点附近越来越陡，而弱收敛只处理固定函数。这里得到的是量词边界，而不是原定义的反例。

另一个容易混淆的加强是把连续函数换成任意指示函数。取集合 $B=(0,\infty)$，则 $\mu_n(B)=1$，但 $\mu(B)=0$。虽然点 $1/n$ 越来越接近零，它始终没有离开这个开半轴；质量到达边界时，集合的指示函数发生跳跃。因此弱收敛不保证每个集合的概率都收敛。本例中边界为 $\{0\}$，极限测度恰好把全部质量放在那里。

这次检验留下一个可以继续复算的修正。若只测试满足 $|f(x)-f(y)|\leq|x-y|$ 的函数，则本例的积分误差至多为 $1/n$，而且这个上界对该类函数一致成立。限制变化速度，正好排除了上面越来越陡的 $f_n$。于是三件事可以分开：固定连续测试给出弱收敛；随序列改变测试可能放大差别；加入共同的变化速度控制，在这个例子中又能恢复一致估计。这些结论来自同一对可直接计算的测度，无须借助对“接近”的模糊直觉。

为了避免偷换概念，记录一次极限计算时，还应注明测试函数是否依赖序列指标，以及使用的是逐个函数的极限还是整个函数类上的上确界。


## English exposition: an averaging proof

Suppose a collection of objects is joined by links, and we want to divide the objects into two groups so that many links run between the groups. In graph language, a cut is specified by a subset $S$ of the vertex set $V$; its crossing edges have one endpoint in $S$ and the other in $V\setminus S$. We will show that every finite simple undirected graph has a cut containing at least half of its edges. There is no requirement that the two groups have equal size.

Write $G=(V,E)$ and $m=|E|$. Choosing a good partition directly can look awkward: placing one vertex may help some edges and hurt others. A useful way around this difficulty is to begin with a partition chosen without trying to make it good. We can then measure its average performance. If that average is already large enough, at least one of the partitions must do at least as well.

Assign each vertex independently to one of two sides, choosing each side with probability one half. For an edge $e=\{u,v\}$, let $I_e$ be one if the endpoints receive different sides, and zero otherwise. There are four equally likely assignments to the ordered pair of endpoints. Exactly two put them on different sides, so $\mathbb{E}I_e=1/2$. This is where we use the fact that an edge has two distinct endpoints.

The number of crossing edges is the random variable $X=\sum_{e\in E}I_e$. Linearity of expectation gives $\mathbb{E}X=\sum_{e\in E}\mathbb{E}I_e=m/2$.

This calculation does not require the entire family of edge indicators to be independent. Indeed, on a triangle the three indicators cannot all be one, even though each individual edge crosses with probability one half. Independence was used to generate the vertex assignments and compute an individual edge's probability; it is not an extra hypothesis needed when adding expectations.

There are finitely many vertex assignments, each equally likely. Consequently, the expectation just computed is the arithmetic average of their cut sizes. If every cut had size strictly smaller than $m/2$, their average would also be strictly smaller than $m/2$, a contradiction. Thus some cut has size at least $m/2$.

Since a cut size is an integer, this also gives the slightly more precise bound $\lceil m/2\rceil$. The argument includes the graph with no edges, whose every cut has size zero.

It is worth separating this existence conclusion from a claim about a particular random trial. The calculation does not say that every assignment works, or that one trial is certain to work. With a single edge, the random cut has size zero half the time and size one half the time. Its expectation is one half, but that is not even a possible cut size. An expected value is an average over outcomes, rather than a description of what must happen in an individual outcome.

For instance, a triangle has three edges and maximum cut size two. No division can make all three edges cross: after placing two adjacent vertices on opposite sides, the third vertex must share a side with one of them. The expectation argument supplies a cut of size at least two, which is sharp here after rounding. But it does not usually determine the maximum. A bipartite graph already comes with a partition for which every edge crosses; using only the average discards that additional structure.

There is also a simple deterministic procedure behind the same bound. Start from any cut. If some vertex has more neighbours on its own side than on the other side, move that vertex across. The number of crossing edges increases by the difference between these two counts, so it increases by at least one. It can never exceed $m$, and hence this procedure stops.

At termination each vertex has at least half of its incident edges crossing. Summing these inequalities over the vertices counts every crossing edge twice and every edge twice, giving the desired bound again.

This second proof identifies a cut by repeated improvements, while the first identifies a reason that a satisfactory cut must exist before we search for it. Neither proof says that its satisfactory cut is a maximum cut. The common point is that a modest global guarantee can be obtained without understanding the best partition in detail. In the averaging proof, the complicated interaction among choices disappears because each edge contributes a quantity whose expectation can be computed separately.


