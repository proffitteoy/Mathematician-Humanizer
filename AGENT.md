# 项目约定

默认中文。修改前读 README、docs/architecture.md 与 docs/research.md。

主线只有一条：统计分析 → 风格总结 → 用参考数学家的博客风格增补改写 Humanizer → 实际改稿与复核。根目录 `SKILL.md` 是唯一 skill 正文，名称为 `mathematician-humanizer`。

- 不重新引入通用写作 skill、作者检测、模型动力学训练或以指标数量定义的路线。
- 参考作者统一用 `one of the mathematicians` 或中性中文代称；技能名称、目录、正文和来源标识均不使用姓名。匿名化转换保留原始与当前指纹，不改统计数值或测量参数。
- 代码服务于统计和规则总结；写作由调用 skill 的语言模型完成。不要把分析器叫成改写生成器。
- `SKILL.md` 自身包含完整工作流与规则，普通改写不要求安装 Python。保持 README 使用说明、`agents/openai.yaml` 与 skill 一致；行为改变时更新 CHANGELOG。
- `references/{statistical-style,mathematician-style}.md` 由 `style-compiler compile` 生成。改其解释规则时修改 `src/style_compiler/profiles.py`，然后重新生成；构建回执默认输出到 stdout，按需保存到被忽略的 `artifacts/`。
- `docs/research.md` 说明问题、测量方法、最终结果、规则转换与验证状态。`research/` 只保留最终结果、来源清单与实际测量合同；历史探索、全量分层导出和旧示例回执通过清单中的 Git 提交追溯，不堆回当前目录。
- `research/manifest.json` 绑定现有冻结证据。更新研究结果必须保留来源、测量口径、划分与失败；不能只改哈希使旧结果变成新实验。
- 不把英文词性或句长阈值搬到中文。中文参考来源标签不升级为所有人、作者身份或写作质量。
- 数学条件、量词、否定、定义域、归属和证明依赖优先于风格。不要为指标补内容。
- 没有隐式下载、远端上传或训练。可选解析依赖使用现有本地权重。
- 优先修改现有函数，不增加无实际用途的框架。代码或结构改变后运行 `python -m unittest discover -s tests -v`，检查文档链接、生成卡和示例。
