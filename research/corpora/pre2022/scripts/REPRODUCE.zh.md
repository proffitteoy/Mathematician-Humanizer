# 复现来源统计

这组脚本只核验既有来源和输出聚合资料，不会下载语料、改变实验分割、读取WikiConv正文/测试目标或进行模型拟合。使用Python 3标准库。将本目录脚本放在一起，保持相互导入关系。

SOURCE_ROOT是来源交付根目录，包含public/与私有private/；WIKICONV_DIR是既有2017年度档案和只读structural-frame.sqlite所在目录；SELECTION是旧实验冻结的元数据选择文件；AUDIT_TOOLS是项目既有research/audits目录。不得把这些私有输入、逐页账本或旧分割定位放入公开仓库。

## 维基结构与角色统计

输入为private/wiki-acquisition-receipt.json及private/raw/两个已下载xml.bz2。以下命令重新流式扫描XML，重建私有逐页元数据，并自动附加角色标记，输出public/wiki-census.aggregate.json。

```sh
python scripts/census_wiki_archives.py "$SOURCE_ROOT"
```

如果已保存逐页元数据而只需复现角色标记，可以运行：

```sh
python scripts/add_wiki_role_flags.py "$SOURCE_ROOT"
```

只计主空间非重定向页，模板名忽略大小写。头条取headline item/header；VOA取完整名称voa，不包括VOA-部分；原创取original模板或包含原创/原創的分类并集；outline取名称前缀；guide/star取两个名称前缀；列表取listing、see、do、eat、drink、sleep、buy。粗筛采用原文至少200字符及基本汉字区/扩展A占Unicode字母数字至少一半，并排除头条模板。这些规则复现来源标签，不验证内容为原创或纯人工。公开高频分类列表中的记者归属类标签会以统一占位符显示；私有分类记录与统计计数不变。

## WikiConv元数据容量

只解压conversations.json元数据，不解压utterances.jsonl；SQLite以mode=ro与query_only打开。检查原档案SHA256和字节数、元数据选择SHA256、192旧分量、475暴露分量及只读结构库的来源控制值。

```sh
python scripts/reproduce_wikiconv_capacity.py \
  --corpus-dir "$WIKICONV_DIR" --selection "$SELECTION" \
  --audit-tools "$AUDIT_TOOLS" \
  --out "$SOURCE_ROOT/public/wikiconv-metadata-capacity.json"
```

所用项目读取器须保持以下SHA256；脚本在导入前核验，不执行从来源档案下载的代码。

- wikiconv_annual_census.py：e5051bd239812935096a035daadb3350a63ca151c7acd24021fa6eb6e39710b5
- wikiconv_zip_audit.py：84ced8137313f6d81c54b4fa6c271ef7f65ff110dc3d395330ce9cf603997e73

冻结选择元数据SHA256为ddbe04ae3a3a1d289fbb53e35872b2eb9df27407d92f6002066c992c1580b0b8。它只含定位、分区、分量、字符数和位置区间，没有正文或目标。容量脚本使用其中的分量与分区元数据，不复跑旧采样器，不打开测试正文或模型预测。

## 来源表

完成上述聚合后，用已保存private/metadata/清单和收据重建catalogue。Git树通过目录条目的mode、名称和对象SHA按Git对象格式重建，检查所有非根子树；不把按commit查询的响应sha直接当成tree SHA。

```sh
python scripts/build_catalogue.py "$SOURCE_ROOT"
```

created_at固定为原来源表的创建时刻，以便重跑逐字节一致；修订时间和前后哈希记录于REVISION_LOG.json。正文计划是编辑性报告，不由脚本自动生成。

2026-10-01修订验证已在另一个本地输出目录重新生成完整wiki census和catalogue，并与修订版逐字节比较；容量脚本也重复运行核对。临时输出中只有本轮wiki文本元数据，不含旧测试正文。最终FILE_HASHES.json绑定公开文件和这些脚本；如后续改变任何输入或规则，应产生新的修订记录，不能继续沿用本次核验结论。
