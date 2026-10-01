# Chinese-first Style Compiler: primary-evidence audit

Checked 1 October 2026. This is a research and writing-quality project. Classification results below are historical experimental outcomes, not authorship verdicts, writing objectives, or expected product performance.

## 1. Requested sources

### Chen, Xiong, He & Ross, 2026, Digital Scholarship in the Humanities

[Publisher article](https://doi.org/10.1093/llc/fqag064), published 23 June 2026. **4,346 documents = 2,173 matched pairs**, not 4,346 pairs. English Aeon essays span 110 topics; roughly 1,500 actual writers. Each human title prompted GPT-4o mini with a fixed 1,000-word, no-heading instruction. Features: 70 function-word proportions plus residual-word proportion. MDS visualizes more concentrated generated profiles. Tests vary representation, length, training size and topic. Whole-document frequencies do not measure sentence-order dynamics. Model/prompt/genre replication and hybrids remain untested. Article: CC BY 4.0. Exact generation date/version and sampling settings are not supplied. Tables 4–7 report accuracy (full/first-200-words): Delta 97.98/90.59%, RF 99.93/50.69%, SVM 99.26/88.72%. The prose's short-text SVM-superiority claim conflicts with Delta's higher reported accuracy and F1. Locate details in §§2.2, 3, 5 and 6.

### Li & Zhang, 2025, CCL

[Paper](https://aclanthology.org/2025.ccl-1.64/). Chinese Weibo, January–December 2024; officially disclosed bot accounts identify generated comments. Collection: 417,361 human-labelled + 46,021 bot comments = 463,382. No underlying generator/version inventory. Replies-to-comments excluded; mentions, URLs and pictures replaced. The nominally balanced subset prints 18,337 triggered + 18,337 voluntary bot comments against 33,674 human comments: inconsistent arithmetic requiring clarification. SFSC uses 34 features, five families, attention and MLP; 80:20 sample split. F1: SFSC .918, no-attention .907, RoBERTa .934. Attention averages rank sentiment and length-related features highly. No author/post-disjoint or prospective test established. Response latency and monthly evaluation are not within-text temporal structure. Paper: CC BY 4.0. No data/code release or separate licenses found. Details: §§2–3, Tables 1–4, Figures 2, 5–6.

### He, Lashkari, Vombatkere & Sharma, 2024

[Authorship Attribution Methods, Challenges, and Future Research Directions: A Comprehensive Survey](https://www.mdpi.com/2078-2489/15/3/131), Information 15(3):131, 28 February 2024. Secondary survey covering both prose and source code. Useful taxonomy of models, features, datasets, evaluation and limitations; not a new experiment on AI uniformity. Its data-availability statement says no datasets were generated. Article license: CC BY 4.0. Follow references to original studies rather than citing the survey as experimental evidence. In particular, code-authorship benchmark sizes and results should not become Chinese-prose design requirements.

### Georgios P. Georgiou, 2026

[What Distinguishes AI-Generated from Human Writing? A Rapid Review of the Literature](https://www.mdpi.com/2504-2289/10/2/55), Big Data and Cognitive Computing 10(2):55, 8 February 2026. Secondary rapid review: 565 retrieved records, 479 after deduplication, 88 full texts assessed, 40 included studies. English-language journal publications dated 2022-01-01 through 2026-01-01; conference papers and preprints excluded. English publication language does not mean all studied texts were English. Five cue families organize the review, but heterogeneous studies prevent pooled effect estimates. Supplement contains search strategy and study list; no new human/AI text corpus. Article: CC BY 4.0. Use for discovery and taxonomy only; do not infer a universal signature or causal intervention.

## 2. Reproducibility audit of the OUP repository

[Repository](https://github.com/xiongshizhao/stylometric-analysis-human-and-chatgpt-texts), inspected commit **924d4ad753a62dc13bc9a9030b754202e71f9b65** (20 November 2025). This commit predates the published article, so discrepancies could reflect an unupdated archive.

- [Study 1](https://github.com/xiongshizhao/stylometric-analysis-human-and-chatgpt-texts/blob/924d4ad753a62dc13bc9a9030b754202e71f9b65/code/study1/howessayrepresentation.R) sets `num_fold <- 10` and calls `createFolds`; this does not match the article's default leave-one-out description
- [setup.R](https://github.com/xiongshizhao/stylometric-analysis-human-and-chatgpt-texts/blob/924d4ad753a62dc13bc9a9030b754202e71f9b65/code/setup.R) refers to two helper scripts under the author's desktop. Neither helper appears in the inspected recursive tree
- README advertises raw essays, function-word files and R scripts. No LICENSE appears in the tree; GitHub's license endpoint returned 404
- The linked [Aeon Kaggle source](https://www.kaggle.com/datasets/mannacharya/aeon-essays-dataset/versions/1) resolved, but its content license was not verified

Conclusion: readable source material exists, but end-to-end reproducibility and reuse rights are not yet established. Do not translate a paper's CC BY license into assumed rights over separately scraped essays or unlicensed code. This inspection did not execute the code or download the corpus.

## 3. More directly useful primary antecedents

### Chinese function words: Bei Yu, 2012

[Function Words for Chinese Authorship Attribution](https://aclanthology.org/W12-2506/). Nine male writers across three periods; novels, essays and blogs gathered from online repositories. A hand-screened list of 35 frequent Chinese characters excludes personal pronouns; Weka EM clusters normalized frequencies. Reported three-author average accuracies: novels .90, essays .85, blogs .68. Some reported results select the better three- versus four-cluster solution. Genre can interfere with author grouping; no solid period association was established. This is small-scale human-author analysis, not AI detection or a validated contemporary Chinese feature dictionary. Publication access does not establish licensing for the source literary works. Use as evidence for Chinese-specific feature validation and genre control.

### Ordered relations: Segarra, Eisen & Ribeiro, 2015

[Authorship Attribution through Function Word Adjacency Networks](https://arxiv.org/abs/1406.4469); [author publication record](https://segarra.rice.edu/publications/), IEEE Transactions on Signal Processing 63(20):5464–5478, DOI 10.1109/TSP.2015.2451111. The accessible 2014 preprint studies English literary authors, initially 21 nineteenth-century writers, then additional historical/genre comparisons. Directed, distance-discounted within-sentence co-occurrences become Markov transitions compared with relative entropy. Combining relational information with frequency features improves attribution in those experiments. Sample length and available author-profile length matter substantially. This supports testing ordered relations beyond marginal counts, not a universal human/AI covariance claim. No transfer to modern Chinese generation is demonstrated here. Reuse licenses for original data/code were not established.

## 4. What the evidence does and does not justify

The defensible empirical premise is conditional: particular generators, prompts and corpora exhibit distinguishable distributions. The proposed compiler should model variation conditional on language, register, intent and audience, then validate whether a feature helps its actual writing task.

The following are **research hypotheses**, not findings established by the requested sources:

1. An author's covariance between sentence length, stance, specificity and discourse moves is stable enough to estimate and useful for editing
2. Preserving joint distributions is better than matching independent feature means
3. Rhetorical transitions and sentence-level autocorrelation add value beyond document-level distributions
4. Adding topological geometry improves predictions of reader-assessed quality or style fit after controlling surface features
5. Intervening on a measured feature improves the text rather than merely moving a detector score

An MDS picture is an exploratory projection. Compactness can depend on scaling, length, content, prompt constraints and sampling. A pooled cloud mixes between-author and within-author variability; it is not an estimate of a particular person's style. Attention weights are model-internal summaries, not causal feature effects. A random comment split is weaker evidence for transfer than held-out accounts, threads, dates and bot families.

## 5. Minimum evidence-to-model contract

Every proposed component should specify:

- Unit: document, fixed-character window, sentence, paragraph, conversation turn, or author profile
- Conditioning: Chinese variety, genre, topic, period, purpose, target audience, source and length
- Measurement: normalization, extractor/version, missingness, uncertainty and the effect of segmentation
- Alternative explanation: which nuisance variable could produce the same signal?
- Falsification: a held-out result under which the component is dropped
- Intervention: a constrained edit, with semantic preservation and independent reader evaluation

Do not infer real experiences, add errors, or inject arbitrary variability to match a statistical profile. The end objective is faithful, useful writing. Authorship labels can be one research axis, but they should not be the compiler's success criterion.

## 6. Corpus admission is separate from article/code access

The initial source audit found no corpus already admitted to this repository. WikiConv Chinese distinguishes CC0 metadata from CC BY-SA 3.0 comment content; a generic release badge must not overwrite content-specific terms. Its action-level user fields identify the editing actor, not necessarily the author of the wording affected by modification, deletion or restoration. Raw actions and ConvoKit's final-state utterances are different units.

CSL's Apache 2.0 repository notice does not by itself settle every underlying abstract right. Its [original paper, Ethical Considerations](https://aclanthology.org/2022.coling-1.344.pdf) reports permission for the authors' NLP use of some metadata; preserve that positive evidence while checking downstream scope.

UD Chinese GSD declares CC BY-SA 4.0, but its [official v2.5 changelog entry, verified at commit e0d85a0](https://github.com/UniversalDependencies/UD_Chinese-GSD/blob/e0d85a020182e264d6384be2a59c0f4879a1cc35/README.md#changelog) explicitly limits Google's removal of the NC restriction to UD annotations, not underlying text over which Google claims no ownership. Preserve separate source-text rights/attribution and annotation-version evidence; a treebank badge is not a blanket prose-rights clearance. It is an annotation-validation candidate, not intact author profiles.

Restricted PKU multilevel corpus terms prohibit redistribution and do not permit requesting access to the restricted files; it is not admitted. The initial LCMC catalogue lookup was blocked, but the [official EULA](https://www.lancaster.ac.uk/fass/projects/corpus/LCMC/lcmc/LCMCorder.asp) is now verified: research use is licensed, nonprofit research is free, and corpus sharing is restricted to the licensee/research group. No agreement was accepted; LCMC remains quarantined. No alternative mirror was used to evade restrictions. The user's personal material remains excluded. The later Yihui candidate review concerns a third-party public site, not the user's blog; it establishes a prose-specific license notice, not verified unaided authorship. See [corpus provenance](corpus-provenance.md), the [admission addendum](corpus-admission-addendum.md), and the [provenance feasibility decision](design/provenance-feasibility-v0.1.zh.md).

Primary links: [WikiConv maintainer terms](https://github.com/conversationai/wikidetox/tree/main/wikiconv), [Chinese release](https://figshare.com/articles/dataset/WikiConv_-_Chinese/7376012), [CSL](https://github.com/ydli-ai/CSL), [UD Chinese GSD](https://universaldependencies.org/treebanks/zh_gsd/index.html), [PKU source notice](https://opendata.pku.edu.cn/dataset.xhtml?persistentId=doi:10.18170/DVN/SEYRX5).

## 7. Topology references and limits

[Kushnareva et al., EMNLP 2021](https://aclanthology.org/2021.emnlp-main.50v2.pdf) analyze token attention graphs and persistence summaries; this is distinct from a contextual-embedding cloud. [Tulchinskii et al., NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/7baa48bc166aa2013d78cbdc15010530-Paper-Conference.pdf) use PH0/MST scaling of contextual-token embeddings; the reported Chinese PHD AUROC is .709 in that historical setting. Representation, finite sample size and generator matter. Random text can have large estimated dimension, so increasing dimension is not a quality objective. [Short-PHD's 2025 preprint](https://arxiv.org/abs/2504.02873) alters detector-side context; it does not justify adding unrelated material to user prose, and preprint/conference equivalence remains unverified. The protocol treats geometry as optional, unavailable and subject to an incremental-value/drop test.
