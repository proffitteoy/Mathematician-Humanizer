# Markdown 连续视图 v0.2 审查与 v0.2.1 窄修订

日期：2026-10-01。**原冻结 v0.2 不通过容器隔离检查；按 root 明确指示另建的 v0.2.1 已通过全部合成检查，仍等待 root 独立检查 diff 并复跑。** 本次没有处理自然正文，没有新的运行器、开始标记、诊断 GO、校准或准入。

审查与修改的作者身份必须区分：原始缺陷由本审查独立发现；后续窄修订也由本审查者完成，因此不能把修订后的结果称为已经获得独立作者审核。root 将承担最终独立检查。本报告结束当前任务，不启动自然验证。

## 原提交与实质缺陷

原 v0.2 清单 SHA256：`6d9a42b7828bf811fdb930061e39dfa3d32fac98add557fa9e2c4fc3a7b5aeb7`；投影器 SHA256：`795d57ef4e39114ff34a6faa6e43f830cd12a5bb5516c4f5b5627f1312f1df94`。八个清单文件已逐一核验，原包未修改；另保存了完整提交快照及初次失败日志。

实现用 `tuple(stack)` 判断表格与后续标题是否处于同一容器，但 stack 只存 token 类型。不同列表项、不同列表或不同引用块可以具有相同的类型序列，因此后一个容器中的标题会错误解除前一张表的注释隔离。

三个不含来源正文的反例都重现：表格在一个列表项中而标题位于兄弟项；表格在前一个列表而标题位于另一列表；表格在前一个引用块而标题位于另一引用块。三者均可能将后续注释重新发为正文候选。原版在新增的 33 项检查中失败 3 项，另外 30 项通过。这个问题是确定的容器身份错误，不是自然样本不足造成的不确定性。

## 单独保存的 v0.2.1 修订

修订目录为 `style-markdown-projection-v02-1/public`。投影器 SHA256：`7b9330df302fa3272617667662879a31cec13c323904b5f91715126704345688`；完整清单 SHA256：`b42198a2e35f852dfdf5ba9af63dfa3792a608b140543741c2e2ae1f5454bcdc`。

代码变更只有两部分：

- profile／schema 改为 `historical-blog-markdown-display-continuity/0.2.1` 和 `markdown-display-continuity/2.1`
- 保留原来的类型栈供角色判断使用，另维护每个容器的完整 AST opener 路径。路径元素为 token 类型与唯一 token 序号；关闭时同步弹出。表注范围只能由实际相同路径内的标题或分隔线解除

精确差异见 `container-identity.diff`，SHA256：`1ff29887ae360cc9f0318674c4f11572544266e69b899abb400da0fe35a977cb`。没有修改 Markdown 可见文字规则、旧 v0.1、其已执行 smoke、原 v0.2 或旧指纹证书。

新增 10 项容器回归测试覆盖兄弟列表项、独立列表、独立引用块、有序列表项、嵌套项、根／内层错位以及真实同容器的正例。原 61 项、这 10 项及额外 33 项对抗检查均通过，共 104 个测试方法。原套件中包含 200 个确定性 fuzz 输入，不能另算成 200 个独立自然样本。

## 连续视图与硬边界的检查结论

支持的连续性限定于 CommonMark 已识别的强调界符和有效链接外壳。链接标签中的每个保留字符仍映射到原始位置；目的地址、标题或引用键不会作为正文输出。独立案例检查了空标签、重复文本、保留空格、组合字符、补充平面字符、嵌套强调及链接标题内换行。

代码、引文、数学、实体、转义、自动链接、图片、脚注和可见换行仍构成硬边界。标签内部的这些内容不会因外部链接合法而恢复为正文。每个不连续字符邻接都必须由语法删除证明覆盖；完整源分区、保留字符覆盖和映射顺序另外检查。伪造后重新计算哈希的证明跨度、边、角色、内容边界和旧证书适用声明均被默认 validator 拒绝。

公共 validator 默认 `replay=True`，会重新派生相同 profile。此重放是实质计算，未来执行预算须计入；`replay=False` 是刚生成结果的内部快速检查选项，不能作为不可信外部结果的完整一致性认证。重放一致性仍不证明语义原作、角色真值、权利或人类来源。

表格前的可能标题和表格后的注释范围采取保守隔离，可能遗漏正常正文。显式同容器标题只是结构停止规则，不能证明后续文字来自同一作者或是未引用的原创文章。v0.1 中已经观察到的表注问题仍如实保留，未以修订覆盖旧事实。

## root 检查与后续建议

建议 root 先核对上述窄 diff，并执行：

```sh
cd /workspace/shared/style-markdown-projection-v02-1/public
/workspace/shared/style-ml-env/bin/python -B -m unittest -v test_continuity_projection.py test_container_identity.py
```

额外对抗集位于本审查目录，须显式选择修订源码：

```sh
cd /workspace/shared/style-markdown-projection-review-v02/public
CONTINUITY_PROJECTOR_SOURCE=/workspace/shared/style-markdown-projection-v02-1/public/continuity_projection.py /workspace/shared/style-ml-env/bin/python -B -m unittest -v test_independent_continuity.py
```

通过 root 独立检查后，可以考虑一份全新的三篇既有暴露诊断契约。条件性建议随修订保存为 `BOUNDED_DIAGNOSTIC_CONTRACT_PROPOSAL.zh.md`：精确三篇、52,679 原始字节，新的源码／依赖／解释器绑定、独占标记、累计预算、读取账本、持久化 seal，并对默认 replay 的额外计算收费。建议数值为实现及审查衍生物合计 4 MiB、累计 60 秒、512 MiB、2 线程；它们尚未获准，也不能复用 v0.1 的已消耗标记和额度。

没有授权新的 12 篇校准或全部 788 篇投影。新 profile 改变 n-gram 的邻接及分母，旧 wiki 兼容证书明确不适用；之后必须另审跨视图覆盖、复制闭包及永久暴露规则。三篇诊断及旧 96 篇与其污染闭包保持排除。本次没有自然正文、个人化材料、指纹数据库读取或远程写入。

当前唯一剩余程序性门槛是 root 对自修代码的独立审查。原 v0.2 仍为 blocked；v0.2.1 为合成测试通过、待独立核验，不是执行 GO 或来源准入。
