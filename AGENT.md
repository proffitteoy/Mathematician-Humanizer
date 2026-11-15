# 项目约定

默认中文。修改前读 README、docs/architecture.md 与 docs/research.md。

仓库交付数学理解、论证讲解与统计反馈工具，skill 名称为 `mathematician-humanizer`，根目录 `SKILL.md` 是唯一技能正文。2026-11-15 用户要求优先于旧的“只交付固定风格改写”定位：以带证据的证明依赖图和数学动机重建为核心，表达规则服务于理解。README 优先说明用途、调用、安装和示例；协议与研究在 docs 中说明。

- 不重新引入通用写作 skill、作者检测、模型动力学训练或以指标数量定义的路线。
- 参考作者统一用 `one of the mathematicians` 或中性中文代称；技能名称、目录、正文和来源标识均不使用姓名。匿名化转换保留原始与当前指纹，不改统计数值或测量参数。
- `math_reader` 负责保留原文的解析、证据和依赖检查；`math_exposition` 负责版本化分阶段 prompt、任务门槛与双重审核；`style_compiler` 保留统计职责。数学解释和写作由调用模型完成，不把分析器叫成证明器或生成器。
- `SKILL.md` 自身包含完整工作流与规则，普通改写不要求安装 Python。保持 README 使用说明、`agents/openai.yaml` 与 skill 一致；行为改变时更新 CHANGELOG。
- README 与 SKILL 开头保留 Humanizer 的改编声明；26 项主题、编号与分组全部来自上游，工作流和通用内容保护也有上游来源。更新时区分改编与本项目增补，保持固定版本、逐条对应和随技能分发的完整 MIT 版权通知；参考数学家的匿名约定不替代上游版权归属。
- `references/{statistical-style,mathematician-style}.md` 由 `style-compiler compile` 生成。改其解释规则时修改 `src/style_compiler/profiles.py`，然后重新生成；构建回执默认输出到 stdout，按需保存到被忽略的 `artifacts/`。
- `docs/research.md` 说明问题、测量方法、最终结果、规则转换与验证状态。`research/` 只保留最终结果、来源清单与实际测量合同；历史探索、全量分层导出和旧示例回执通过清单中的 Git 提交追溯，不堆回当前目录。
- `research/manifest.json` 绑定现有冻结证据。更新研究结果必须保留来源、测量口径、划分与失败；不能只改哈希使旧结果变成新实验。
- 不把英文词性或句长阈值搬到中文。中文参考来源标签不升级为所有人、作者身份或写作质量。
- 数学条件、量词、否定、定义域、归属和证明依赖优先于风格。不要为指标补内容。
- 原文引用候选不自动成为证明边；每条边有数学用途和原文锚点。区分作者明确动机、数学结构重建与未核实联系。DAG/引文检查不认证数学正确性。
- Prompt 的可执行正文在 `src/math_exposition/prompts.py`，变更同步 `docs/prompt-engineering.md`；统计回执必须来自当前稿，改稿后重新审核。托管旧 MCP 和本地新 MCP 的能力及部署状态分别说明。
- 没有隐式下载、远端上传或训练。可选解析依赖使用现有本地权重。
- 优先修改现有函数，不增加无实际用途的框架。代码或结构改变后运行 `python -m unittest discover -s tests -v`，检查文档链接、生成卡和示例。
