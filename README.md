# dsh-kit（DeepSeek Harness 版）

DeepSeek Harness **bundle 形式**的技能包：**95 个技能**（11 个包内自有 + 84 个上游合并），包内隔离加载（provider `dsh-kit`，`includeDefaultRoots: false`），不写入 `~/.agents/skills` / `~/.dsh/skills` 等 canonical 技能目录。

| 项 | 值 |
|---|---|
| 包位置 | `integrations/deepseek-harness/`（包名 **`dsh-kit`**） |
| 版本 | **6.2.1** |
| 技能 | **95** = 11 个包内自有 + 84 个上游合并（`affaan-m/ECC` 59 / `mattpocock/skills` 19 / `thedotmack/claude-mem` 6 / `alibaba/open-code-review` 0） |
| 随包参考 | `rules/`（WSL CLI 工具链、代理管理）、`references/`（grow-dream 类型定义 + 上游来源登记） |
| 上游来源登记 | `references/upstream-sources.md` 与四份分册（论文引用格式：作者/载体/快照 SHA/许可/URL/取用范围/**引用键**） |
| 许可 | `LICENSE`（自有部分 MIT）+ `integrations/deepseek-harness/LICENSES/`（上游许可正文：MIT×2、Apache-2.0、claude-mem 的 `NOTICE`）+ `integrations/deepseek-harness/THIRD-PARTY-NOTICES.md`（第三方声明与**变更声明**） |

## 安装（本地 link）

```powershell
# 1) 取到本仓库
git clone <本仓库地址> <本地路径>

# 2) 用官方 CLI 装进目标 profile
#    Desktop 端用安装包自带 CLI：<安装目录>\resources\runtime\cli\bin\dsh.cmd
dsh plugin --profile <profile> add "<本地路径>/integrations/deepseek-harness"

# 3) 验证
dsh plugin --profile <profile> list --depth 0
```

`dsh plugin add` 会写入 `"dsh-kit": "link:<本地路径>/integrations/deepseek-harness"`，并把 `dsh-kit` 追加到该 profile 的 `dsh.profile.bundles`；包清单变化会触发 DSH 重载。

## 卸载

```powershell
dsh plugin --profile <profile> remove dsh-kit
```

## v6.2.1 变更（ast-grep CLI 引擎"假绿"修复）

**问题**：`check-code-names.py` 的 CLI 引擎调用 `ast-grep run --kind <KIND>`，而 `run` 子命令只有 `--pattern`——对上表所有 kind 都返回 `error: unexpected argument '--kind'`，旧代码对每个非 0 返回 `continue`，于是**全部 kind 失败 → 抽取结果为空 → findings=0**，输出"未发现明显命名问题"。这是"代码命名全合格"的**假绿**，不是真实结论。

**修复**：改用官方受支持的 `scan --stdin --inline-rules`（`--inline-rules` 自 ast-grep 0.15.1 起可用）：
- 该语言全部 kind 编成一个规则文档，**每文件 1 次子进程**（原为文件 × kind 次）；
- 非 0 退出码**不再吞掉**：先逐条探测、剪掉该版本不认的 kind 并告警，全废则抛错 → 显式降级正则；
- 0 匹配与规则损坏区分开（后者必然非 0）；
- 顺带修掉真实语料暴露的两个取名缺陷：`@Transactional(...)` 被误取名为 `Transactional`、函数体注释 `// ... method stub` 被误取名为 `stub`（真实方法 `doInsert` 漏检），并按名字实际位置回算真实行号；
- **逐 finding 标注实际生效引擎**（降级文件写 `regex`，不全沿用全局引擎名），仓库级聚合 findings 亦补齐 `engine`，并新增 `degraded_files` 读数。

**回归**：新增 11 条用例（含"坏名样例各引擎必须报出问题"的反假绿自检），`run-all-tests.py` 共 **74** 条，Windows/WSL 双平台全绿；另用 424 个真实 Java 文件对照 CLI 与正则两引擎（CLI 1355 条 / 正则 1159 条，差异逐条核实为 AST 更准）。

## v6.2.0 变更（naming 技能深度化 + 校验门转绿）

**校验门首次全绿**：`node tools/validate-package.ts` → exit 0（此前 v6.1.0 遗留 4 项红）。

### naming 技能（22 个参考文件 + 14 个脚本）

- **产品侧**：类型选型、竞品命名占位图、否决门（SCRATCH）+ 0–3 锚点评分、分级可用性（L1 / L1.5 / L2 / L3）、语音象征三层、中文音形义、跨语言、代号、品牌架构、tagline、开源命名。
- **AI 时代**：生成端失效模式（分布坍缩 / 后缀配额 / temperature 误区）、L1.5 生成式可提及性（只报提及率 + n，禁止排名）、AI 朗读门、零记忆冷启动。
- **代码侧**：语言层规则 + 跨层（API / DB / 事件 / 指标 / 配置）三宗陷阱 + UI 层（按钮 / aria / 令牌 / i18n / 空态）。
- **6 个检查器 + 63 个回归用例**：
  | 脚本 | 用途 | 用例 |
  |---|---|---|
  | `check-code-names.py` | 代码标识符（三层引擎：ast-grep-py → CLI → 正则） | 14 × 2 |
  | `check-cross-layer.py` | 跨层一致性（init / check / audit） | 10 |
  | `check-ui-names.py` | UI 文案 / aria / 令牌 / i18n | 11 |
  | `check-brand-slop.py` | 品牌 AI 味（非拉丁名显式"未检查"） | 12 |
  | `check-ai-visibility.py` | L1.5 采集与统计 | 8 |
  | `run-all-tests.py` | 一键回归 | 63 合计 |
- **证据台账**：所有结论带强度标注（实证 / 机构 / 经验 / 判断 / 未验证），并列出「不要重复的伪结论」。
- **依赖**：`python3 >= 3.6`，零第三方依赖；`ast-grep-py` 可选（不装则降级为纯标准库正则）。脚本共享 `scripts/_common.py`，拷走需整个 `scripts/`。

### 两个此前"红"的技能补全

`ssrf-remediation`、`dsh-remote-wsl-troubleshooting` 的正文已英文化并补 `metadata.origin: dsh-kit`，二者加入 `tools/validate-package.ts` 的 `NATIVE` 名单（现 11 个包内自有）。

## 技能清单

完整逐条清单（含上游路径与处置）见 [`integrations/deepseek-harness/references/upstream-sources.md`](integrations/deepseek-harness/references/upstream-sources.md) 与四份分册。这里按来源分组列出全部 95 个：

> **计数口径**：**95** 指 DSH 会发现的一层技能（`skills/<name>/SKILL.md`）。用 `**/SKILL.md` 递归计数会得到 **96**——多出的 1 个是 `skills/grow-dream/templates/w-ocean/skills/w-ocean-agent/SKILL.md`（grow-dream 的技能载荷模板，DSH 不发现、不计入技能面）。

### 包内自有（11）

|  |  |  |  |
|---|---|---|---|
| `chrome-devtools-wsl` | `dsh-kit` | `grow-dream` | `karpathy-guidelines` |
| `write-a-skill` | `wsl-network` | `github-repo` | `diagnose` |
| `naming` | `ssrf-remediation` | `dsh-remote-wsl-troubleshooting` |  |

### 上游合并 · `affaan-m/ECC`（59）

|  |  |  |  |
|---|---|---|---|
| `accessibility` | `agent-harness-construction` | `agent-introspection-debugging` | `agent-self-evaluation` |
| `agentic-engineering` | `api-design` | `architecture-decision-records` | `benchmark` |
| `codebase-onboarding` | `coding-standards` | `context-budget` | `contract-first` |
| `council` | `database-migrations` | `deployment-patterns` | `django-patterns` |
| `django-tdd` | `docker-patterns` | `dotnet-patterns` | `e2e-testing` |
| `error-handling` | `eval-harness` | `git-workflow` | `golang-patterns` |
| `golang-testing` | `hexagonal-architecture` | `intent-driven-development` | `iterative-retrieval` |
| `java-coding-standards` | `kotlin-patterns` | `kotlin-testing` | `kubernetes-patterns` |
| `laravel-patterns` | `living-docs-governance` | `loop-design-check` | `mcp-server-patterns` |
| `nextjs-turbopack` | `parallel-execution-optimizer` | `postgres-patterns` | `production-audit` |
| `prompt-optimizer` | `python-patterns` | `python-testing` | `rails-patterns` |
| `react-patterns` | `react-testing` | `rules-distill` | `rust-patterns` |
| `rust-testing` | `safety-guard` | `santa-method` | `search-first` |
| `security-review` | `skill-scout` | `springboot-patterns` | `strategic-compact` |
| `swiftui-patterns` | `verification-loop` | `vue-patterns` |  |

### 上游合并 · `mattpocock/skills`（19）

|  |  |  |  |
|---|---|---|---|
| `code-review` | `codebase-design` | `domain-modeling` | `grill-me` |
| `grill-with-docs` | `grilling` | `handoff` | `improve-codebase-architecture` |
| `pr` | `prototype` | `research` | `retro` |
| `setup-pre-commit` | `tdd` | `to-spec` | `to-tickets` |
| `triage` | `wizard` | `writing-for-agents` |  |

### 上游合并 · `thedotmack/claude-mem`（6）

|  |  |  |  |
|---|---|---|---|
| `babysit` | `design-is` | `learn-codebase` | `session-handoff` |
| `standup` | `what-the` |  |  |

### 上游合并 · `alibaba/open-code-review`（0）

该上游的 2 个技能均为 `ocr` CLI 调用封装，按「工具本体不进技能面」未纳入 `skills/`，仅登记于 [`references/upstream-ocr.md`](integrations/deepseek-harness/references/upstream-ocr.md)。

## 参考资料（上游来源登记）

| 引用键 | 上游 | 快照 | 许可 | 取用 |
|---|---|---|---|---|
| `ecc-ef648e0` | `affaan-m/ECC` | `ef648e01899b` | MIT | 59 / 上游规范目录 |
| `mp-24fe0ef` | `mattpocock/skills` | `24fe0ef7737e` | MIT | 19 / 上游规范目录 |
| `cmem-3b3baaa` | `thedotmack/claude-mem` | `3b3baaa55ebb` | Apache-2.0 | 6 / 上游规范目录 |
| `ocr-182898c` | `alibaba/open-code-review` | `182898cf522d` | Apache-2.0 | 0 / 上游规范目录 |

**84 个上游技能**的 `metadata` 里带有 `origin` / `upstream` / `snapshot`，与上表一一对应（`tools/validate-package.ts` 会逐条校验三元组与本表一致）。11 个包内自有技能没有上游来源：`karpathy-guidelines` 与 `naming` 为 `origin: dsh-kit`（前者另带 `metadata.license: MIT`），其余 9 个不设 `metadata`（其中 `dsh-remote-wsl-troubleshooting`、`ssrf-remediation` 为新增、`metadata` 待补）——**以门的 ⑪ 读数为准**（它会把超出 `origin`/`upstream`/`snapshot` 的子键逐个打印，别照抄本行）。

## 结构与合并约定

```
dsh-kit/
├── CONTEXT.md                        # 术语表（只放规范词）
├── README.md
├── LICENSE                           # 自有部分 MIT（仓根副本）
└── integrations/deepseek-harness/
    ├── package.json                  # dsh-kit
    ├── cordis.patch.yml              # 注册 dsh-kit-skill-filesystem（技能从包内 skills/ 提供）
    ├── lib/index.js                  # skill-only bundle，无运行期服务
    ├── LICENSE                       # 同文 MIT（npm 只随包分发包目录内文件，故此处另存一份）
    ├── LICENSES/                     # 上游许可正文：MIT-ECC.txt、MIT-mattpocock-skills.txt、Apache-2.0.txt、NOTICE-claude-mem.txt
    ├── THIRD-PARTY-NOTICES.md        # 第三方声明 + 变更声明（Apache-2.0 §4 履行情况）
    ├── skills/                       # 95 个技能，每个含 SKILL.md
    ├── rules/                        # wsl-cli-tools.md、proxy-management.md
    └── references/                   # grow-dream-types.md + upstream-*.md（上游来源登记）
```

| 约定 | 内容 |
|---|---|
| 目录 | 技能必须是 `skills/<name>/SKILL.md` **一层**（DSH 不发现嵌套的深层 `SKILL.md`） |
| frontmatter | 只用 DSH 认可键：`name`、`description`（必填）+ `metadata`、`disable-model-invocation`、`user-invocable`；未认可的上游杂键被静默忽略，legacy 键会让该技能**被整体丢弃**（详见 CONTEXT「DSH 认可键」） |
| 语言 | **正文英文**（= 上游逐字为底，仅叠加 CONTEXT「最小适配（A）」的 7 项）；**`description` 英中双语**（英文侧 = 上游 description 折叠成一行 + 中文触发语，召回用）；无 DSH 等价物的 Claude Code / 其他 runner 语境加**英文横幅标注**（不再改写正文）；`claude-mem` 源本轮被改的 4 个文件另有 **§4(b) 变更标注**（见 `THIRD-PARTY-NOTICES.md`） |
| 署名 | 上游正文/参考文件/脚本版权归上游作者：`metadata`（84 个上游技能）与 `references/upstream-*.md` 双重登记；第三方许可正文与**变更声明**见 `integrations/deepseek-harness/THIRD-PARTY-NOTICES.md` |
| 附带载荷 | `skills/<name>/` 下的**非技能文件**（除 95 个技能 `SKILL.md` 与 1 个载荷 `SKILL.md` 之外）——**个数口径见下**，别照抄：「除 95 个技能 SKILL.md 外的全部文件」与「除全部 96 个 `SKILL.md` 外的文件」相差 1（差别是 `skills/grow-dream/templates/w-ocean/skills/w-ocean-agent/SKILL.md`，DSH 不发现它）。复现：<br>`(Get-ChildItem integrations/deepseek-harness/skills -Recurse -File).Count` 与 `(git ls-files integrations/deepseek-harness/skills).Count`（提交后两者应相等；含未提交新增时 disk ≠ git tracked，需提交后复核）。其中值得单列的：`agents/openai.yaml`（每个上游来源技能一个，见 `skills/<name>/agents/`）、`skills/standup/standup.ts`（**可执行载荷**，`node` 直接跑，需 Node ≥22.18 原生 type-stripping）、`chrome-devtools-wsl/` 的 `.py`/`.sh`/`.vbs`/`justfile`/`.env.example`/`pyproject.toml`、`grow-dream/templates/w-ocean/` 的 `README.md`/`commands/`/`config.yaml`/`graph.json` |
| `rules/` | 随包分发但**不经任何注册**：没有任何插件加载它，靠模型按相对路径自取（`skills/dsh-kit/SKILL.md` 与 `skills/chrome-devtools-wsl/SKILL.md` 各有一处指引） |

## 验收与可复现

本仓**唯一**可运行的自查器是 `tools/validate-package.ts`。在**仓库根**执行：

```powershell
node tools/validate-package.ts
```

它检查：技能数 = 95、只有 `skills/<name>/SKILL.md` 一层、无 legacy 键、`name`/`description` 必填且 `name` 与目录名一致、**`description` 英中双语**（须同时含拉丁字母与 CJK）、**SKILL.md 正文不含 CJK**（上游正文自带中文的只有 `LANGUAGE_ALLOWED` 里**带理由**的显式豁免，逐条打印，含"白名单已腐化"提示）、D8 的 8 个用户调用型名单完全一致（多一个少一个都算失败）、84 个上游技能的 `metadata` 三元组与引用总表一致、正文内包内相对路径**无死链**；嵌套载荷必须恰为 grow-dream 那 1 个。退出码非 0 即有问题（未认可的上游杂键只报告、不计入失败，因为 DSH 会静默忽略它们）。

**不覆盖**：上游正文的字节级保真（需要上游快照，本仓不含）、`description` 的措辞质量（含"**是否真有一句英文**"——判据 ⑤ 只证明出现了拉丁字母，中文描述里提到一个拉丁术语同样会过）、技能行为正确性。

> 历史说明：v6.0.1–v6.0.4 的 commit message 里引用的 `merge-manifest.ts`、`import-upstream-skills.ts`、`.docs/fix/2026-10-05/review-audit.ts` **从未进入本仓历史**（`git log --all --name-only` 可复现），故那些 commit 声称的"保真 44/44、正文 66 原样"等结论无法在本仓重跑。可复现的验证边界以上面的脚本为准。

## 许可

本仓**自有部分**为 MIT，见 [`LICENSE`](LICENSE)（`integrations/deepseek-harness/LICENSE` 是同文的包内副本，因为 npm 只随包分发**包目录内**的文件）。

随包合并的上游技能各自沿用其许可，正文与变更声明随包分发：

| 上游 | 许可 | 版权行 | 随包许可正文 |
|---|---|---|---|
| `affaan-m/ECC`（59） | MIT | `Copyright (c) 2026 Affaan Mustafa` | `integrations/deepseek-harness/LICENSES/MIT-ECC.txt` |
| `mattpocock/skills`（19） | MIT | `Copyright (c) 2026 Matt Pocock` | `integrations/deepseek-harness/LICENSES/MIT-mattpocock-skills.txt` |
| `thedotmack/claude-mem`（6） | Apache-2.0 | `Copyright 2026 Alex Newman` | `.../LICENSES/Apache-2.0.txt` + `.../LICENSES/NOTICE-claude-mem.txt` |
| `alibaba/open-code-review`（0，未取用） | Apache-2.0 | `Copyright 2026 alibaba/open-code-review Contributors` | 未分发该上游任何内容，故不单列 |

许可正文逐字节取自各上游快照 commit 处的 `LICENSE` / `NOTICE`；**变更声明**（哪些文件被改过、Apache-2.0 §4(b)/§4(d) 的履行情况与已知残留）见 [`integrations/deepseek-harness/THIRD-PARTY-NOTICES.md`](integrations/deepseek-harness/THIRD-PARTY-NOTICES.md)。
