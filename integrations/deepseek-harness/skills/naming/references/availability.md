# 可用性 / 校验（availability）

> 口径：**不查不发**，但"查"要分层——一层查不清就标"未查"，不许把"没查到"写成"可用"。
> 全部输出都带免责：本技能只做检索，不做商标判断、不做法律意见。

## 产品模式：分级可用性门（L1 / L1.5 / L2 / L3）

专业机构的做法都是分级的（Catchword 走 Google screen → CatchAll → TrademarkNow；Lexicon 强调"beyond knockout"；Atom 在同一段里声明"preliminary, not a clearance search, not legal advice"）。按同样形态**逐行输出**：L1、L2、L3 恒有；**L1.5 只在"买家会问 AI 助手"时跑，跑了才写**。

| 级别 | 查什么 | 怎么查 | 能得出的结论 | 不能得出的结论 |
|---|---|---|---|---|
| **L1 公开冲突** | 同名/近名产品、竞品、已倒闭公司、社区口碑 | web 搜 `"[name]" <品类>`、`"[name]" app/software`、`"[name]" <英文品类词>`；私密窗口搜 `[name]` | "公开层面未见直接竞品/已见" | 不等于商标可用 |
| **L1.5 生成式可提及性** | 名字在 AI 回答里能否被提及/引用（不是排名） | 3 引擎（其一带联网）× 5 条**不含自身品牌名**的买家 prompt × 3 次 = 45 观测；记录提及次数/前三/引用 | "提及 4/15 次，2 次前三，1 次被引用" | 不能排"第 N 名"、不能跨厂商比分数、单次 run 只是快照 |
| **L2 商标库同名** | 目标类别（Nice 分类）内是否已有相同/近似注册 | USPTO **Trademark Search**（TESS 已于 2023-11-30 退役，不要再教"去 TESS 搜"）、EUIPO eSearch、WIPO Global Brand Database；中国商标网（如需中国） | "同名在 XX 类未见/已见" | 不是 clearance search，近似判断需专业 |
| **L3 正式 clearance** | 全面检索 + 法律意见 | 商标律师/代理机构 | — | 本技能**不做**，只建议 |

补充法理口径（防止把 L2 结论说成法律结论）：描述性名字**不是不能注册**，而是要走"第二含义"（Lanham Act §2(f)）且成本高、周期长，且通常不能走"意图使用"（ITU）；显著性要按"名字 × 商品/服务类别"三元组判断，同一个词对不同商品可属不同类别（*Abercrombie & Fitch v. Hunting World*, 537 F.2d 4, 9-11 (2d Cir. 1976)）。

**输出格式（必须照抄）**：

```text
L1 公开冲突：已查（web/私密窗口）→ 未见直接竞品 | 命中 <名称>（同品类）
L1.5 生成式可提及性：提及 4/15 次，其中 2 次前三，1 次被引用（3 引擎 × 5 prompt × 3 次）
L2 商标库同名：已查 USPTO 类 9/42 → 未见完全相同 | 未查（无网络/无权限）
L3 正式 clearance：未做（建议商标律师）
免责：以上为初步检索，不构成法律意见，也不构成 clearance search。
```

> L1.5 的完整方法、方差纪律与禁止写法见 `ai-era.md` §4；不看 AI 渠道的场景（内部系统、B2B 直客）可整行省略，但**不能**用"排名第 N"替代。

出处：knockout search 的标准动作（定义类别 → 多形态检索（含拼写变体/近似）→ 判"混淆可能性"，且"已死商标不等于安全"），见 <https://www.lexology.com/library/detail.aspx?g=27f98c1a-29e2-465f-b2ff-4d7c4c640599>；机构免责声明形态见 <https://www.atom.com/>。

**顺序不变**：① L1 竞品冲突（最常杀名，先做）→ ② 域名 → ③ 包名 → ④ 社媒/应用商店 → ⑤ L2 商标库。

### 1. 竞品冲突（先于一切）

- `"[name]" <品类>`、`"[name]" software/app`、`"[name]" <目标语言品类词>`。
- 有**直接竞品且同品类**＝死，别再查域名。
- 有**同名但不同品类**＝记录 + 看商标类别是否重叠；不同类不等于安全，但也不等于死。
- 更进阶：先做「竞品命名占位图」（见 `product-playbook.md` 第 3 步），把"名字是否已被占据"从个案判断变成位置判断。

### 2. 域名

- **字典常见词**跳过 `.com/.dev/.io/.app/.co` 精确匹配（基本被占），直接看 `get[name]` / `use[name]` / `[name]hq` / `.sh` / `.site` / 国别域。
- **生造词**才值得查精确匹配。
- 工具：`bash scripts/check-availability.sh <name> domain`（whois 优先，失败降级 HTTP 探测）；更快的替代是 **RDAP**：`https://rdap.org/domain/<name>.<tld>`，**404 通常表示未注册**（一次性提示，不作结论）。
- **判据**：域名缺失**不是否决项**。Tesla / Peloton / Square 都不是直取 `.com`；给出替代路径（`getX.com`、国别域、路径式落地页）即可（经验，Lexicon 公开材料）。

### 3. 包名与代码托管

- npm：`npm view <name> version`（失败=可能可用）
- PyPI：`https://pypi.org/project/<name>/`（404=可用）
- crates：`https://crates.io/api/v1/crates/<name>`（404=可用）
- RubyGems：`https://rubygems.org/api/v1/gems/<name>.json`（404=可用）
- GitHub org：`https://github.com/<name>`（404=可用）
- WP slug：`https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&slug=<name>`（含 `Plugin not found`＝可用）
- Telegram：`https://t.me/<name>`（404=可用）

### 4. 社媒 / 应用商店（脚本不覆盖，用搜索）

- `site:x.com/<name>`、`site:instagram.com/<name>`、`site:github.com/<name>`
- 应用商店：`"[name]" site:apps.apple.com`、`"[name]" site:play.google.com`
- **handle 扫一遍要跨 10 个平台**（实践者建议，见下），并且**逐平台记录"丑陋妥协"**（如 `@name_hq`、`@name.app`）——这些妥协本身就是品牌的长期成本。

### 5. 六个低成本现实测试（来自一线实践 + AI 时代的补充，建议全部做）

出处：Anand Chowdhary 的 X 长帖（2025-10-13，<https://x.com/AnandChowdhary/status/1977732312298307805>，镜像：<https://github.com/AnandChowdhary/notes/blob/main/threads/2025/names-that-work-in-systems.md>）：

1. **嘈杂通话测试**：在 5 人语音里说一遍，看能不能被复述（电话测试的加强版）。
2. **听写测试**：iOS 与 Android 各口述一次，看转出来的文本是否一致——语音输入/助手已经是名字的日常入口。
   - 为什么值得做（有数据的一侧）：Palanica et al. (2019, *npj Digital Medicine* 2:52) 让语音助手识别药品名，**Alexa 误识 38.2%、Siri 41.5%、Google 8.2%**——注意这是 2019 年、药品名任务，**不能外推成"品牌名误识率"**；流传的"47% 语音搜索会第一次听错品牌名"**查无一手来源，本技能不引用**。
3. **私密窗口搜索测试**：无痕搜 `[name]`，看自己能不能排在被占的既有内容之上；排不上＝未来获客成本高。
4. **10 平台 handle 测试**：一次把目标平台全部占位，记录妥协项。
5. **AI 朗读门**：把候选填进 `"我推荐 __，因为它 __"`，用 2 个不同厂商的 LLM（其一带联网）+ 1 个 ASR 各跑 1 次，统计"需改写名字/需额外解释/复述拼错"；3 次中 ≥1 次失败 → 降级备选并写明失败类型。方法见 `ai-era.md` §5。
6. **品类默认探测**：不带上下文问 3 个模型各 1 次「X 是一家做什么的公司？」，记录它们给的行业标签；模态标签 ≠ 目标品类且非故意留白 → 换名，或把"需持续投入品类纠偏"写进让步项。方法见 `ai-era.md` §5。

### 6. 输出里必须带的免责

```text
可用性状态为公开检索结果，非法律意见，非 clearance search；
商标注册可行性需商标律师出具意见；域名/账号状态以注册商与平台为准。
```
