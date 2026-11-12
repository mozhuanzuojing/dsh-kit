# dsh-kit — DeepSeek Harness 技能包

dsh-kit 的 **DSH bundle 形态**：**95 个技能**隔离在包内，经 bundle patch 聚合加载，`~/.agents/skills` 零污染。

## 安装

```powershell
dsh plugin --profile <profile> add "<本仓库>/integrations/deepseek-harness"
```

等价的手工写法（写进 `$DSH_HOME/profiles/<profile>/package.json`）：

```jsonc
"dependencies": { "dsh-kit": "link:<本仓库>/integrations/deepseek-harness" },
"dsh.profile.bundles": [ ..., "dsh-kit" ]
```

包清单变化后由 DSH 重载生效；HMR 未接管时重启 DSH。

## 加载方式

`cordis.patch.yml` 插入一行 `dsh-kit-skill-filesystem`，使用 `@deepseek-ai/dsh-skill-filesystem`：

- `providerName: dsh-kit`
- `includeDefaultRoots: false` —— 项目根、用户根、`$DSH_BUNDLED_SKILL_DIR` 均不参与，只加载本包 `skills/`
- `bundledSkillDir` 经 `createRequire(baseUrl).resolve('dsh-kit/package.json')` 解析，不写死路径

| 项 | 值 |
|---|---|
| 包名 | `dsh-kit` |
| 版本 | 6.2.1 |
| 技能 | 95（11 包内自有 + 84 上游合并） |
| 上游 | `affaan-m/ECC` 59；`mattpocock/skills` 19；`thedotmack/claude-mem` 6；`alibaba/open-code-review` 0 |
| 参考文件 | `rules/`（2）、`references/`（grow-dream 类型定义 1 + 上游来源登记 5） |
| 运行期服务 | 无（`lib/index.js` 为空实现） |
| frontmatter 认可键 | `name`、`description`、`metadata`、`disable-model-invocation`、`user-invocable`（未认可的上游杂键被静默忽略；legacy 键会让该技能被 DSH 整体丢弃，只留一条 warn 日志） |
| 运行期依赖 | `@deepseek-ai/dsh-skill-filesystem` 由 **DSH 宿主自带**，本包**故意不声明**为 dependency/peerDependency：声明会让 pnpm 在 profile 里再装一份副本，产生第二个模块实例，而该服务靠模块级标识工作。宿主版本要求见其 `Config` 三键（`providerName` / `includeDefaultRoots` / `bundledSkillDir`） |
| Node | 包本身无运行期代码；唯一可执行载荷 `skills/standup/standup.ts` 需 Node ≥22.18（原生 type-stripping） |
| DSH | ≥ 0.2.2-rc.2（宿主按 `engines.dsh` 校验兼容门；低于此版本会被拒绝加载） |
| 许可 | `LICENSE`（包内 MIT）+ `LICENSES/`（上游许可正文）+ `THIRD-PARTY-NOTICES.md`（第三方声明与变更声明） |

## 校验

```powershell
dsh plugin --profile <profile> list --depth 0
```

应看到 `dsh-kit@link:<本仓库>/integrations/deepseek-harness`；会话技能目录中出现 `dsh-kit`、`code-review`、`tdd` 等即加载成功。

包内技能面自查（**不需要 DSH 运行**；脚本在**仓根** `tools/`，不在本包目录内，所以必须在仓库根执行）：

```powershell
# 在 <本仓库> 根目录执行，不是在本包目录
node tools/validate-package.ts
```

它校验：技能数 = 95、一层拍平、无 legacy 键、`name`/`description` 必填且 `name` == 目录名、**`description` 英中双语**、**正文不含 CJK**（上游自带中文的只有带理由的显式豁免）、8 个用户调用型名单、84 个上游技能的 `metadata` 三元组、**正文内包内相对路径无死链**、以及**版本一致性**（两处 `package.json` 的 `version` 相等，两份 README 的版本行与之一致）；退出码非 0 即有问题。
**不覆盖**：上游正文的字节级保真（需上游快照）、`description` 的质量（含"是否真有一句英文"——`description` 判据只证明出现了拉丁字母）、技能行为正确性。
（`tools/` 未列入本包 `files`：它是维护者/CI 用的仓内工具，装成 npm 包的消费方拿到也改不了包本身。若希望随包分发，需把它移入本包目录并加进 `files`。）

## 上游来源

见 `references/upstream-sources.md`（索引）与 `upstream-ecc.md`、`upstream-mp-skills.md`、`upstream-claude-mem.md`、`upstream-ocr.md`。

> 版本:6.2.1 | 技能:95 | 上游:ECC/mattpocock/claude-mem（+ open-code-review 仅参考资料）
