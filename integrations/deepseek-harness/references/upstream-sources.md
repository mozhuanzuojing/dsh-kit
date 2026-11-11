# dsh-kit 上游来源登记（参考资料索引）

> 本文件由 `dsh-kit` 维护，随包分发。只登记**上游来源与取用范围**，不含技能正文；
> 技能执行请见 `skills/`，包内隔离加载（provider `dsh-kit`，`includeDefaultRoots: false`）。


## 引用总表

| 引用键 | 上游 | 快照 | 许可 | 地址 | 取用技能数 |
|---|---|---|---|---|---|
| `ecc-ef648e0` | ECC — Engineering Context Collection | `ef648e01899b` | MIT | https://github.com/affaan-m/ECC | 59 |
| `mp-24fe0ef` | Matt Pocock's Skills | `24fe0ef7737e` | MIT | https://github.com/mattpocock/skills | 19 |
| `cmem-3b3baaa` | claude-mem | `3b3baaa55ebb` | Apache-2.0 | https://github.com/thedotmack/claude-mem | 6 |
| `ocr-182898c` | Open Code Review (OCR) | `182898cf522d` | Apache-2.0 | https://github.com/alibaba/open-code-review | 0 |

## 分册

- [`ecc-ef648e0`](upstream-ecc.md) — ECC — Engineering Context Collection
- [`mp-24fe0ef`](upstream-mp-skills.md) — Matt Pocock's Skills
- [`cmem-3b3baaa`](upstream-claude-mem.md) — claude-mem
- [`ocr-182898c`](upstream-ocr.md) — Open Code Review (OCR)

## 取用与处置约定

| 项 | 约定 |
|---|---|
| 选中技能 | 目录拍平为 `skills/<name>/SKILL.md`（DSH 只发现这一层） |
| frontmatter | 只保留 DSH 认可键：`name`、`description`（+ 可选 `metadata`、`disable-model-invocation`、`user-invocable`）；上游杂键在此登记，不再随技能保留 |
| `description` | **英中双语**：英文侧 = 上游 description 折叠成一行（不是新写）、+ 中文触发语（原样保留，召回用）。**正文英文**——上游逐字，仅叠加下面的「最小适配」；上游自带 CJK 区字符的正文例外见 `../../CONTEXT.md` 的「正文语言」（豁免表在 `tools/validate-package.ts` 的 `LANGUAGE_ALLOWED`，**以表为准，此处不抄名单/计数**） |
| 最小适配 | 入库只做 7 件必要事（目录拍平 / frontmatter 只留认可键 / `description` 英中双语 / CC 专有路径与工具名→DSH 等价物（**例外**：主语是 Claude Code 本身或跨 harness 并列时保留原名，逐处见 CONTEXT「最小适配（A）」）/ 死链中性化（含**裸相对**目标）/ **英文** CC 语境横幅 / **Apache-2.0 §4(b) 变更标注**（仅 `claude-mem` 源本轮被改的 4 个文件，逐字文本见 `THIRD-PARTY-NOTICES.md` 的 §4(b) 节））——逐条判据与`据实读数`见 `../../CONTEXT.md` 的「最小适配（A）」 |
| 逐技能偏离 | **本表只登记来源与批量口径。**逐技能的实际处置以**本仓可复核的东西**为准：① `git log -p -- integrations/deepseek-harness/skills/<name>/`（每个技能的改动史，含本轮英文化）；② `tools/validate-package.ts` 的判据与读数（frontmatter / 语言 / 死链 / 元数据）。⚠ **相对上游的逐行偏离无法在本仓复核**：上游快照不在包内（`README`「不覆盖」同此），故本表**不**声称有一份仓内的「逐技能偏离清单」，也不给任何无法就地重跑的计数 |
| 署名 | **84 个上游技能**的 `metadata.origin` / `metadata.upstream` / `metadata.snapshot` 指向本表条目（11 个包内自有技能无上游来源：`karpathy-guidelines` 与 `naming` 为 `origin: dsh-kit`（前者另带 `metadata.license: MIT`）；其余 9 个不设 `metadata`，其中 `dsh-remote-wsl-troubleshooting`、`ssrf-remediation` 为新增、`metadata` 待补） |
| 许可正文 | 随包分发于 `../LICENSES/`（MIT×2、Apache-2.0、claude-mem 的 `NOTICE`）；**变更声明**见 `../THIRD-PARTY-NOTICES.md` |
| 未选中技能 | 不复制进包；原因见各分册「未取用说明」 |
| 工具本体 | 上游的可执行服务/CLI/hooks 不进技能面（见 `upstream-ocr.md`） |
