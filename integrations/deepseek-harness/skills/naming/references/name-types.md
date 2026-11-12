# 名字类型与选型（生成之前先定类型）

> 用途：product 模式第 2 步。先声明"我们要哪种类型的名字"，再进隐喻探索。
> 类型选错，后面每一步都在补偿一个错误的起点。标注：**实证**＝有论文/数据；**法理**＝法律判例/官方指南；**经验**＝业界实践；**判断**＝本文推断。

## 1. 为什么类型先于候选

同一句"要个记得住的名字"，在不同类型上有完全不同的代价：

| 目标 | 描述型 | 任意/脱离型 | 生造型 |
|---|---|---|---|
| 一眼懂（降低解释成本） | 强 | 弱 | 弱 |
| 可被记住（无媒介投放时） | 中 | 强 | 弱 |
| 可被保护（商标） | 弱 | 强 | 最强 |
| 可搜索（不与品类词打架） | 弱 | 强 | 强 |
| 可延展（跨品类） | 弱 | 强 | 中 |

三者不可兼得（见 §5 的争议），所以选型就是**先决定牺牲哪一项**。

## 2. 二维分类（Kolenda 版，推荐做主分类）

两个轴：**是否使用真实词** × **是否与品类相关**。四象限：

| 类型 | 真实词？ | 相关？ | 例子 | 强项 | 代价 |
|---|---|---|---|---|---|
| **Descriptive 描述型** | 是 | 是 | General Motors、Home Depot、Travel Advice Publisher | 零解释成本、SEO 友好 | 商标最弱、像品类词、难延展 |
| **Deviant / Arbitrary 任意型** | 是 | 否 | Apple、Amazon、BlackBerry、Grey Goose | 记忆强、可保护、可延展 | 需要故事与投放来建立关联 |
| **Associative 联想型** | 否 | 是（词根相关） | Facebook、LinkedIn、YouTube、Figma（figure） | 有钩子又不直白 | 词根选错会显得廉价 |
| **Neologistic 生造型** | 否 | 否 | Kodak、Spotify、Zynga | 商标空间大、全球无撞义 | 记忆最弱，必须短、好读、可拼 |

> 出处：Nick Kolenda《The Psychology of Business Names》讲稿/指南（2×2 矩阵与四类命名），<https://nickkolenda.com/guides/brand-names/>（原站曾 429，社区多处转述；判断：矩阵本身可用，细节以原站为准）。

**本地技能的默认倾向**（隐喻驱动 + 反对同义词库）实际把候选推向 **Deviant / Associative**，这对消费品牌是对的，但对"内部系统名""基础设施组件名"是错的（见 §4）。

## 3. 机构用的四类（Igor 版，适合作竞品占位图的标签）

Igor International 在竞品分析里按四类给名字落点：**Functional（功能型）/ Invented（生造型）/ Experiential（体验型）/ Evocative（唤起型）**，再按 engagement 强度（y 轴 **−2 到 +5** 八级，越高＝名字里可把玩的材料越多）打分，读出"语义被占满的区域"和"空白位"。

- 价值不在分类名，而在**把竞品名字画在一张图上**，让"我们能不能占一个新位置"变成可见问题，而不是逐个查重。
- 落地：见 `product-playbook.md` 第 3 步「竞品命名占位图」。
- 出处：<https://igorinternational.com/>（Competitive Analysis 一节）。

## 4. 按场景选型（决策表）

| 场景 | 推荐类型 | 理由 | 反例（会翻车） |
|---|---|---|---|
| 消费品牌 / 面向大众的 App | Deviant 或 Associative | 记忆与商标优先；故事可投放 | 纯描述名（如 "Photo Editor Pro"）无法保护、无法延展 |
| B2B SaaS（买家是业务部门） | Associative 为主，Descriptive 作副名 | 要可信 + 要能解释；副名承担"它做什么" | 过度生造（买家听不懂、销售每次都要解释） |
| 开发者工具 / OSS 库 | Associative 或短 Descriptive | 见 §4.1；`import` 要短、要能猜、要能搜 | 诗意但不可猜的名字（社区要靠 README 才知道这是什么） |
| 内部系统 / 平台组件 | **Descriptive（自描述）** | 见 §4.2；内部没有投放预算，靠名字找东西 | 内部系统起神话名（"Whitehall""Maslow"），新人无法从名字定位职责 |
| 硬件 / 实体产品 | Deviant + 强语音 | 口播与货架识别优先 | 长复合描述名（印不上包装） |

### 4.1 开发者工具与 OSS：可猜 + 可搜 + 可 import

- **可猜**：名字应提示"它属于哪类东西"（`react-query`、`django-rest-framework`）。
- **可搜**：通用词会被同题材内容淹没——HN 上有开发者明确指出的反例：项目叫 `plugin-update-checker`，搜文档会被一堆同类词埋掉；叫一个独特词反而更好搜（判断/经验，<https://news.ycombinator.com/item?id=46237390>）。
- **可 import**：包名要短、全小写、无歧义分隔符；`@scope/name` 的 scope 也参与记忆成本。
- 结论：**OSS 名是"Distinctive 但可归类"**，不是纯描述，也不是纯生造。落地细节（CLI/import 友好性、注册表冲突、org vs repo、会议提问测试）见本包 `open-source.md`。

### 4.2 内部系统：UK GDS 的反向立场（必须知道的对立观点）

英国政府数字服务（GDS）的官方规范要求产品名**自描述、禁止双关与品牌化**，并列出自家反例（Panopticon、Whitehall、Maslow、Magna Charta 被判为"含混、可能混淆"），正例是 `Travel Advice Publisher`、`Manuals Publisher`。

- 出处（原文）：<https://github.com/alphagov/gds-way/blob/main/source/standards/naming-software-products.html.md.erb>
- 这与本地技能"五宗罪第 1 条：无聊的描述名"**直接冲突**——冲突是真实的，不是谁错：GDS 优化的是"陌生工程师能否从名字定位系统"，本地技能优化的是"消费者能否记住品牌"。
- 处置：**按场景切换目标函数**（见 §4 决策表），并在输出里显式说明"这是内部名，还是市场名"。

## 5. 证据：真实词更易被记住，但"相关"几乎不影响记忆

- **实证**：Lerman & Garbarino (2002) 比较真实词 vs 生造词品牌名的回忆/再认：真实词回忆率 **68.8% vs 38.1%**；且"与产品无关的真实词"回忆率与"相关的真实词"接近——这为 Apple / Grey Goose 这类**任意型**提供了实验支持。
  - 出处：Psychology & Marketing 19(7-8), 621-639，DOI [10.1002/mar.10028](https://doi.org/10.1002/mar.10028)
  - 数字转引自 Anthony Shore《Real words make better brand names》(2009)，<https://anthony-shore.squarespace.com/blog/2009/04/real-words-make-better-brand-names.html>（原文付费；**二手数字**，引用时注明）。
- **法理**：美国商标显著性谱系（Abercrombie & Fitch v. Hunting World, 537 F.2d 4 (2d Cir. 1976)）：generic < descriptive < suggestive < arbitrary < fanciful。描述型并非不能注册，而是要证明"第二含义"，成本高、周期长。
- **判断**：把上面两条合起来 → "用真实词但脱离品类"（Deviant）在记忆与保护上同时占优，这是消费品牌的最优区；代价是必须付故事与投放。

## 6. 反直觉提醒（避免把规则教条化）

1. **最受欢迎的名字常常最无聊**：Lexicon Branding 的公开材料提到 Pentium 并非测试中最受喜爱的候选，但 80% 受测者认为它"让电脑更强"——喜欢与有效不是同一个指标（经验/二手，<https://www.lexiconbranding.com/brand-naming-process/>）。
2. **域名缺失不是否决项**：Tesla、Peloton、Square 都不是 `.com` 直取；域名可以靠 `getX`/`useX`/国别域/子品牌路径解决（经验，同上）。本地技能的口径应是"**不查不发，但缺域名≠弃名，要给替代路径**"。
3. **大组头脑风暴有害**：Lexicon 明确小团队优于大组（经验，同上）。对 agent 的含义：**少而深的多轮隐喻探索 > 一次吐 50 个**。

## 7. 输出契约（写进简报与最终呈现）

在第 1 步简报里加一行**类型声明**，之后每一步都受它约束：

```text
name_type: descriptive | deviant | associative | neologistic
audience: consumer | b2b | developer | internal
protect_priority: high | medium | low
```

最终呈现时，每个决赛名都要回答一句：**"它属于哪种类型，因此我们在哪一项上做了让步？"** 答不出＝还没想清楚。
