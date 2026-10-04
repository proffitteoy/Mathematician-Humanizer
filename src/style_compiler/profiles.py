"""Compile frozen descriptive evidence into readable, explicitly scoped style cards."""
import hashlib
import json
import math
from pathlib import Path


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Style card requires a finite measured value")
    return f"{value:.3f}"


def general_card(paired, joint):
    model, audit = paired["model"], paired["development_audit"]
    if model["fit_split"] != "TRAIN" or audit["test_opened"] is not False:
        raise ValueError("General reference must retain its TRAIN/DEV-only scope")
    train = {row["feature_id"]: row for row in model["features"]}
    dev = {row["feature_id"]: row for row in audit["features"]}
    if len(train) != len(model["features"]) or set(train) != set(dev) or len(dev) != len(audit["features"]):
        raise ValueError("Duplicate or mismatched TRAIN/DEV feature identities")
    actions = {
        "F013": ("句长中位数", "检查是否把紧密关联的条件拆成了许多短句；必要时合并。"),
        "F014": ("句长四分位距", "按信息负担安排句长，避免把所有句子修成同一个模子。"),
        "F015": ("句长90分位数", "允许承载完整条件的长句；过长而难读时仍应拆分。"),
        "F024": ("相邻句长变化/中位数", "让关键判断、例子、展开占用不同篇幅，避免逐句等长。"),
        "F025": ("相邻句长秩相关", "检查实际衔接；不使用随机的长短句交替公式。"),
    }
    lines = ["# 中文统计对参考博客风格改写的补充", "",
        "这张卡从已完成的 TRAIN/DEV 汇总生成。HUMAN/CHATGPT 是原语料标签；以下差异不证明改写效果，也不是所有人的统一风格。", "",
        "## 句子与节奏", "",
        "下表保留训练筛查和开发检查均支持的观察。差值为 HUMAN − CHATGPT；句长使用 Unicode L/N 内容字符，不是分词词数。", "",
        "| 观察 | TRAIN差值 | DEV差值 | TRAIN/DEV分量数 | 编辑时回看的问题 |",
        "|---|---:|---:|---:|---|",
    ]
    supported = []
    for feature in sorted(train):
        first, second = train[feature], dev[feature]
        if first["train_inspection_eligible"] is True and second["inspection_supported"] is True:
            if feature not in actions:
                raise ValueError("No reviewed editorial interpretation for supported feature " + feature)
            delta, later = first["train"]["human_minus_ai"], second["dev"]["human_minus_ai"]
            if delta * later <= 0 or second["dev_direction_reproduced"] is not True:
                raise ValueError("Supported feature has inconsistent TRAIN/DEV direction")
            name, action = actions[feature]
            lines.append(f"| {feature} {name} | {_number(delta)} | {_number(later)} | {first['train']['components']}/{second['dev']['components']} | {action} |")
            supported.append(feature)
    lines += ["", "这些编辑问题是解释性建议，没有接受过干预效果验证。统计支持的是观察差异，不能据此要求所有稿件变长、变乱或接近某个数值。", "",
              "## 按来源保留差异", "",
              "| 来源 | TRAIN段落密度差值 F002 | DEV差值 |",
              "|---|---:|---:|",
    ]
    for source in ("baike", "web"):
        lines.append(f"| {source} | {_number(train['F002']['train_domains'][source]['human_minus_ai'])} | {_number(dev['F002']['dev_domains'][source]['human_minus_ai'])} |")
    lines += ["", "两来源方向相反；F002、F003、F016 没有通过这份汇总的通用检查门，不编译成段落数、单句段或离散程度处方。物理行不等于修辞段落。", "",
              "## 中文词汇与句法参考", "",
              "十项语言学参考是 TRAIN 中全部坐标可用的 HUMAN 分量均值。每个分量先合并文档再等权；空值不补零。", "",
              "| 来源 | 可用文档/分量 | 名词均值 | 动词均值 | 副词均值 | 单汉字词元均值 | 词元平均码点长 |",
              "|---|---:|---:|---:|---:|---:|---:|",
    ]
    ids = [feature["id"] for feature in joint["features"]]
    for source in ("baike", "web"):
        row = joint["sources"][source]
        values = dict(zip(ids, row["reference"]["mean"], strict=True))
        selected = ("zh:upos.NOUN", "zh:upos.VERB", "zh:upos.ADV", "zh:word.single_han", "zh:word_length.mean")
        lines.append(f"| {source} | {row['joint_available_human_documents']}/{row['joint_available_components']} | " + " | ".join(_number(values[key]) for key in selected) + " |")
    lines += ["", "词性比例使用固定解析器的非标点、非空白词元分母，不能用汉字数估算。来源差异用于选择表达方式：实体与约束密集的说明保留准确术语；解释型文字可把名词堆叠还原为行动和从句。", "",
              "同一来源仍有很大差异。第一/第二人称与否定形式首先服务于原意；不要为了追均值加入‘我/你’，也不要删除‘仅/不/最多’。", "",
              "两份已冻结示例中，较口语版的单汉字词元占比反而更低、平均词元更长。‘熟悉短词 → 更短解析词元’尚未成立；不把短语替换当作确定的数值控制器。", "",
              "## 写作时怎么用", "",
              "先确认具体阅读问题，再考虑这张卡支持哪项编辑。内容、读者和作者声音优先。普通改写直接使用这些总结；只在研究评估或用户要求时重新量测原稿和终稿。", "",
              f"表层仪器 profile：`{model['measurement_profile_sha256']}`。语言学 profile：`{joint['provenance']['measurement_profile_sha256']}`。两者是不同仪器，不混成质量分。", "",
              "交付所用统计和失败结果见研究仓库的 `research/results.json`；当前文件指纹和历史来源由 `research/manifest.json` 绑定，研究路线见 `docs/research.md`。", ""]
    return "\n".join(lines), supported


def mathematician_card(profiles, summary):
    if profiles["development_articles"] != summary["development_articles"]:
        raise ValueError("Reference profile/summary development counts disagree")
    lines = ["# 参考数学博客的风格：固定底色，按体裁展开", "",
        f"官方公开博客快照登记 {summary['public_records']} 个记录，纳入测量 {summary['eligible_measured_articles']} 份；规则使用 {summary['development_articles']} 份开发文章。另有 {summary['heldout_articles']} 份年份/文章级留出，已有冻结规则的描述性覆盖检查。这里重新编译汇总，没有重新解析博客。", "",
        "## 始终保持的风格", "",
        "- 围绕一个明确对象或理解障碍推进；开头给读者进入问题所需的最少背景。",
        "- 先说明关键选择的动机，再进行计算或调用工具；使每个转折都有可追踪的数学理由。",
        "- 有帮助时从例子、特殊情形或弱结论出发，逐步增强；清楚交代模型保留与丢失的结构。",
        "- 用克制的语气写精确判断；自然使用共同推演的‘我们’，不靠戏剧化片段或夸张评价制造重要性。",
        "- 对象、术语和记号保持一致；分清直觉、猜想、证明和数值支持，条件与量词随结论一起出现。",
        "- 按读者的困难分配篇幅；展开决定性步骤，压缩已经熟悉的例行工作。",
        "- 回到原问题说明得到了什么，适用边界在哪里；开放问题必须具体。", "",
        "这是对已读博客组织方式的编辑总结。下面的测量支持其适用范围和节奏选择；它不能自动证明上述论证机制的语义识别、模仿效果或作者独特性。", "",
        "## 英语中的体裁差异", "",
        "数字是文章/重叠家族加权的中位数，句长和段长单位为该固定英文仪器的词项；不是中文阈值。", "",
        "| 体裁 | 开发文章 | 重叠家族 | 句均词数中位数 | 段均词数中位数 | for instance/千词中位数 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    genres = {"math_exposition": "数学说明", "lecture_notes": "课程讲义",
              "learning_advice": "学习/职业建议", "writing_advice": "写作建议"}
    for genre, label in genres.items():
        row = profiles["groups"]["genre/" + genre]
        features = row["features"]
        values = [features[key]["family_weighted_median"]
                  for key in ("sentence_words_mean", "paragraph_words_mean", "cue_for_instance")]
        lines.append(f"| {label} | {row['article_count']} | {row['families']} | " + " | ".join(_number(value) for value in values) + " |")
    lines += ["", "用同一套问题意识、动机解释、术语稳定性和克制语气贯穿所有文章；讲义可展开证明和练习，短说明围绕一个关键机制，札记保留真实的疑问和检查过程。不要给每篇文章硬套同一开头或同一段落模板。", "",
              "英语举例时，开发材料的 for instance 比 for example 常见；真正需要例子时可优先考虑，不能靠重复短语制造风格。", "",
              "## 中文迁移", "",
              "中文保留同一套论证习惯，用自然的中文句法表达。这里没有参考数学家亲笔中文语料；不移植英文词性百分比、句长或依存阈值。一般中文参考也不能冒称参考数学家的中文统计。", "",
              "## 阅读参考", "",
              "作者以 one of the mathematicians 代指，来源使用 `public-mathematics-blog/1` 别名。以下保留阅读篇目，作者姓名与可识别作者的链接不在当前交付中展示。", "",
              "- Crossing number inequality（2007-09-18）：逐步加强弱结论与关键步骤动机。",
              "- Dyadic models：模型保留与丢失的结构。",
              "- Compactness in topological spaces：定义、目标、证明与练习之间的承接。",
              "- Learn and relearn your field：围绕已知引理重新提问。",
              "- Give appropriate amounts of detail：按读者知识与关键步骤配置细节。", "",
              "快照覆盖 2007—2026 年。客座作者、索引/勘误混合页、过短目录等先分流；保留文章仍可能有合作叙述或引文。体裁由启发式路由；没有对照作者实验，也没有模仿保真度或真人偏好结论。", "",
              "当前交付的四类体裁统计和留出结果见研究仓库的 `research/results.json`；英语仪器合同见 `research/english-contract.json`。完整历史分层表通过 `research/manifest.json` 指向的 Git 提交追溯，保留原始指纹与匿名化说明。", ""]
    return "\n".join(lines)


def compile_profiles(research: Path, skill: Path):
    manifest = json.loads((research / "manifest.json").read_text(encoding="utf-8"))
    names = ("results.json", "chinese-parser.json", "english-contract.json")
    inputs = {}
    for name in names:
        raw = (research / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["inputs"][name]["sha256"]:
            raise ValueError("Frozen research input changed: " + name)
        inputs[name] = json.loads(raw)
    results = inputs["results.json"]
    if results["schema"] != "style-study-results/1":
        raise ValueError("Unsupported published research result schema")
    general, supported = general_card(results["chinese_surface"], results["chinese_lexical"])
    blog = results["reference_blog"]
    mathematician = mathematician_card(blog["development_profiles"], blog["summary"])
    outputs = {"references/statistical-style.md": general,
               "references/mathematician-style.md": mathematician}
    hashes = {}
    for name, content in outputs.items():
        path = skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        hashes[name] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    receipt = {"schema": "style-cards-build/2", "research_inputs": {
        name: manifest["inputs"][name]["sha256"] for name in names},
        "supported_surface_observations": supported, "outputs": hashes,
        "new_corpus_measurement": False, "quality_or_similarity_score": None}
    return receipt
