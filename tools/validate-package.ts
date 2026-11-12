/**
 * dsh-kit 包内技能面自查（不需要 DSH 运行）。
 *
 * 语言政策（v6.0.6 起；判据见 CONTEXT「正文语言 / 最小适配」）：
 *   **正文英文**（上游逐字，仅叠加必需适配；CC 语境横幅也是英文）、**`description` 英中双语**。
 *   本轮之前是"正文保留上游原文、中文只出现在元数据层"⇒ ⑤ 曾经反向要求 description **含中文**，
 *   现按新政策收口；⑥ 是本轮**新增**的正文语言门。
 *
 * 校验项（除 ⑩ / ⑪ 两项读数外全部计入退出码）：
 *  1) 技能数 = 95，每个技能目录都有 SKILL.md
 *  2) 只有 skills/<name>/SKILL.md 一层会被 DSH 发现；嵌套 SKILL.md 只允许 grow-dream 的模板载荷，数量与路径必须与预期一致
 *  3) frontmatter 无致命 legacy 键（disableModelInvocation / modelInvocable / userInvocable）
 *  4) name/description 必填，且 name 与目录名一致
 *  5) description 必须**英中双语**：同时含拉丁字母与 CJK 区字符。缺任一侧即失败
 *     ⚠ 这是"必要条件"不是"充分条件"：它答不了"有没有一句英文"（见 LATIN 的注释与 README「不覆盖」）
 *  6) SKILL.md **正文（frontmatter 之外）不得出现 CJK 区字符**。豁免只有 LANGUAGE_ALLOWED 里**带理由**的那些，
 *     且逐条打印；**白名单腐化计入失败**（文件已无 CJK 却仍挂着豁免 ⇒ 该条会永远无人清理）
 *  7) 8 个用户调用型技能的名单必须与 CONTEXT D8 完全一致（disable-model-invocation 在位、无第 9 个）
 *  8) 84 个上游技能的 metadata 必须带 origin/upstream/snapshot，且与 references/upstream-sources.md 的引用总表一致
 *  9) 正文内指向包内相对路径的 markdown 链接（**含不带 `./` / `../` 的裸相对目标**）与反引号中带 `../` 的路径必须存在（防死链）
 * 10) 未认可键只报告不报错（DSH 解析器忽略未知键，见 skill-filesystem parseSkillFile）；`metadata` 子键另有 ⑪ 读数
 * 11) 读数（非致命）：`metadata` 子键超出 `origin`/`upstream`/`snapshot` 的技能（`topKeys` 只认列 0 的键，
 *     子键在 ⑩ 里完全不可见 ⇒ 这一项专门把它显示出来，而不是让它被读成"一个都没有"）
 * 12) **frontmatter 标量语法**（计入退出码）：本包全部用单行标量 ⇒ `key: "…"` 必须引号配对、内部 `"` 必须转义、
 *     `\` 后必须是合法转义；块标量（`>` / `|`）本门不支持 ⇒ 直接报错，不让它静默通过
 * 13) **版本一致性**（计入退出码）：本仓有两套 `package.json`（仓根 `dsh-kit-repo` 仅占位、包内 `dsh-kit` 才是发布体），
 *     二者 `version` 必须相等；两份 README 的版本行（各一份表格 + 包 README 页脚）必须与之一致。
 *     为什么要有它：版本号靠手改，v6.2.0 → 6.2.1 曾手动同步 4 处，而旧门不校验版本 ⇒ 只改一处照样全绿。
 *
 * ## 明确**不覆盖**（先读这段，别据此宣称"门管了"）
 *  · 上游正文的字节级保真（本仓不含上游快照）、`description` 的措辞质量、"是否真有一句英文"；
 *  · YAML 全语法（锚点 / 别名 / 多行折叠 / 流式集合）：只做**本包实际用到的单行标量**这一档；
 *  · `rules/` 与 `references/` 内的相对链接（门只扫 `skills/<name>/SKILL.md` 一个文件）；
 *  · 随附载荷（`agents/openai.yaml`、`.py` / `.sh` / `.vbs` / `.ts`、模板 `.md`）的语言与内容；
 *  · DSH 真机加载行为（本门只判包内自洽，不判 load 是否成功）。
 *
 * 用法（在仓库根执行，脚本假定自己在 <repo>/tools/）：node tools/validate-package.ts
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILLS = join(HERE, "..", "integrations", "deepseek-harness", "skills");
const EXPECTED = 95;

const ALLOWED = new Set(["name", "description", "whenToUse", "metadata", "disable-model-invocation", "user-invocable"]);
const LEGACY = new Set(["disableModelInvocation", "modelInvocable", "userInvocable"]);

/** CONTEXT D8：本包的 8 个用户调用型技能（上游 mattpocock/skills 成文策略）。 */
const USER_INVOKED = ["grill-me", "grill-with-docs", "handoff", "improve-codebase-architecture", "retro", "triage", "to-spec", "to-tickets"];

/** Native (in-house) skills: no upstream source; metadata may be only origin: dsh-kit. */
const NATIVE = ["chrome-devtools-wsl", "diagnose", "dsh-kit", "github-repo", "grow-dream", "karpathy-guidelines", "naming", "write-a-skill", "wsl-network", "dsh-remote-wsl-troubleshooting", "ssrf-remediation"];

/** 上游 metadata 三元组，与 references/upstream-sources.md 的引用总表一一对应。 */
const ORIGINS = new Map<string, [upstream: string, snapshot: string]>([
  ["ecc", ["affaan-m/ECC", "ef648e01899b"]],
  ["mp-skills", ["mattpocock/skills", "24fe0ef7737e"]],
  ["claude-mem", ["thedotmack/claude-mem", "3b3baaa55ebb"]],
]);

/** 唯一允许的嵌套 SKILL.md：grow-dream 的技能载荷模板，DSH 不会发现它。 */
const EXPECTED_PAYLOAD = ["grow-dream/templates/w-ocean/skills/w-ocean-agent/SKILL.md"];

/**
 * **CJK 区字符**：表意字（含扩展 A 与兼容区）**加**「中文排版才会出现的那些区」——
 * CJK 标点（`\u3000-\u303f`，含全角空格 U+3000）、假名（`\u3040-\u30ff`）、谚文（`\uac00-\ud7af`）、
 * 全角形式（`\uff00-\uffef`，含全角逗号/句号）。description 要**有**它；正文**不得有**它。
 *
 * ⚠ **为什么不是只判表意字**（v6.0.6 修复轮）：文档（CONTEXT ⑥ / README 验收节）的口径是
 * 「正文不含 CJK」，而旧类 `[\u4e00-\u9fff]` 只覆盖表意字 ⇒ 实测 `loop-design-check` 的英文正文里
 * 用 U+3000 做 `①②③④` 的间隔符却判 ✅，**文档比门宽**。现在类与措辞一致：正文里出现中文排版字符即报，
 * 属上游自带的排版字符走 `LANGUAGE_ALLOWED` 的显式豁免（见下）。
 * 仍**不**覆盖：emoji、西里尔/阿拉伯等非 CJK 文字（不在本包政策的对象内）。
 */
const CJK = /[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]/;

/**
 * 拉丁字母 —— description 要**有**它。
 *
 * ⚠ **能力边界（诚实标注，别据它宣称"描述已是英文"）**：这条判据只证明"出现了拉丁字母"，
 * 证明不了"有一句英文"。中文描述里只要提到一个拉丁术语（如 `TDD`）就会通过。
 * 收紧判据试过两条、都被实测否决：
 *   · `[A-Za-z]{3,}`（要求 ≥3 字母的拉丁词）—— 它**既没用又误报**：`TDD` 本身就匹配，
 *     而真正合法的英文短语 `go/no-go`（`council` 的 description）**反而被判失败**；
 *   · 要求小写拉丁串 —— 会把 `(RAG)` 这类全大写术语的合法描述误伤。
 * ⇒ 保留最弱但**零误报**的这一条；"描述写得够不够英文"仍需人读（README「验收」节已列入不覆盖项）。
 */
const LATIN = /[A-Za-z]/;

/**
 * **正文含 CJK 的显式豁免**（唯一出口；键 = 技能目录名，值 = 理由）。
 *
 * 纪律（v6.0.6 立；修复轮补第二类理由）：**不许为了让门变绿而删/改上游正文** —— 确属上游自带时，
 * 在这里登记一条**带理由**的豁免。可登记的理由只有两类：
 *   ① **中文是职能数据**（删掉即破坏该技能的行为，如中文意图触发词表）；
 *   ② **上游英文正文自带的 CJK 排版字符**（删改即改动上游文本，如 U+3000 间隔符）。
 * 门会逐条打印豁免（**命中 / 腐化**两种状态都可见）；**腐化（文件已无 CJK 却仍挂着）计入失败**。
 * 空表 = 正文全英文，是本包的默认目标形态；**本表是唯一权威，别在文档里另抄一份名单或计数**。
 */
const LANGUAGE_ALLOWED = new Map<string, string>([
  [
    "prompt-optimizer",
    "上游正文自带中文，且中文是该技能的**职能数据**：① 触发词/意图表的中文列（`优化prompt`、创建、实现、添加 等——识别中文意图正是它的职责）；② `## Examples` 的 Example 1（`### Example 1: Vague Chinese Prompt`）是一份「中文 prompt → 优化后中文 prompt」的完整实例。删掉即破坏该技能",
  ],
  [
    "loop-design-check",
    "上游英文正文自带的 **CJK 排版字符**：判定清单 「① …　② …　③ …　④ …」 用 U+3000（表意空格）做间隔。它不是中文内容、删改即改动上游文本 ⇒ 保留并登记，而不是重写上游正文",
  ],
]);

function topKeys(fm: string): string[] {
  const keys: string[] = [];
  for (const line of fm.split(/\r?\n/)) {
    const m = /^([A-Za-z][A-Za-z0-9_-]*)\s*:/.exec(line);
    if (m) keys.push(m[1]);
  }
  return keys;
}

/**
 * 切出 frontmatter 与正文。正文 = 闭合 `---` 行**之后**的全部内容（含 CC 语境横幅）。
 * `bodyLine` = 正文第一行的 1-based 行号（供报"首次出现于 :N"）。
 * 返回 undefined = 无 frontmatter（`---` 不在首行 / 没有闭合行）。
 * 一次扫描同时给两样东西：⑤ 只看 fm、⑥ 只看 body，判据同源，不会各自解析一遍。
 */
function splitFrontmatter(raw: string): { fm: string; body: string; bodyLine: number } | undefined {
  const nl = raw.indexOf("\n");
  if (nl < 0 || raw.slice(0, nl).replace(/\r$/, "") !== "---") return undefined;
  let lineStart = nl + 1;
  let line = 2;
  for (;;) {
    const next = raw.indexOf("\n", lineStart);
    const lineEnd = next < 0 ? raw.length : next;
    if (raw.slice(lineStart, lineEnd).replace(/\r$/, "") === "---") {
      return { fm: raw.slice(nl + 1, lineStart), body: raw.slice(lineEnd + 1), bodyLine: line + 1 };
    }
    if (next < 0) return undefined;
    lineStart = next + 1;
    line += 1;
  }
}

/** 正文里**首次**出现 CJK 的行号（1-based，绝对行号）；没有则 0。 */
function firstCjkLine(body: string, bodyLine: number): number {
  const lines = body.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) if (CJK.test(lines[i])) return bodyLine + i;
  return 0;
}

function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (n === "SKILL.md") out.push(p);
  }
  return out;
}

/** 去围栏代码块：示例代码里的相对路径不是链接。 */
function stripFences(raw: string): string {
  const out: string[] = [];
  let fenced = false;
  for (const line of raw.split(/\r?\n/)) {
    if (/^\s*```/.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (!fenced) out.push(line);
  }
  return out.join("\n");
}

/**
 * 收集正文里指向包内相对路径的目标：
 *   · **markdown 链接目标**（全部，含不带 `./` / `../` 的**裸相对目标** —— 修复轮补：旧版只看带前缀的，
 *     `](no-such-file.md)` 这类死链会静默存活）；
 *   · **反引号路径**（只收含 `../` 的）：反引号里大量是**行内散文引用**（如 `src/auth/middleware.ts:47`），
 *     全收会误报，故只用它覆盖「跨目录引用」这一档。
 */
function relativeTargets(prose: string): string[] {
  const targets: string[] = [];
  for (const m of prose.matchAll(/\]\(([^)\s]+)\)/g)) targets.push(m[1]);
  for (const m of prose.matchAll(/`([^`\n]+)`/g)) {
    if (m[1].includes("../")) targets.push(m[1]);
  }
  return targets;
}

/**
 * 这个目标是不是「包内相对路径」（判据唯一一份；`relativeTargets` 的两类来源共用）。
 * 排除：带 scheme 的（`https:` / `mailto:`）、协议相对（`//`）、纯锚点（`#`）、绝对路径（`/…`、`X:\`、`\\`）、
 * 家目录（`~`）、含占位符（`< > * | { }`）与变量（`$`）的目标 —— 它们都不是「包内相对链接」。
 */
function isPackageRelativeTarget(target: string): boolean {
  const t = target.trim();
  if (!t) return false;
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(t)) return false;
  if (t.startsWith("//") || t.startsWith("#") || t.startsWith("/") || t.startsWith("~")) return false;
  if (/^[A-Za-z]:[\\/]/.test(t) || t.startsWith("\\\\")) return false;
  if (/[<>*|{}]/.test(t) || t.includes("$")) return false;
  return true;
}

/**
 * **frontmatter 单行标量的语法检查**（修复轮新增；本包 95 个技能全部用 `key: "…"` 这一档）。
 * 纯正则抽取无法发现「引号没配对 / 内部裸 `"` / 非法转义」—— 而 frontmatter 坏掉会让 DSH **静默丢弃**该技能
 * （CONTEXT「DSH 认可键」记过 legacy 键的 fail-silent）。返回 `undefined` = 没问题。
 */
function scalarProblem(key: string, value: string): string | undefined {
  const v = value.trim();
  if (/^[>|]/.test(v)) return `块标量（${v.slice(0, 2)}）本门不支持，请改用单行标量`;
  if (v.startsWith('"')) {
    if (v.length < 2 || !v.endsWith('"')) return `双引号未闭合`;
    const inner = v.slice(1, -1);
    const badEsc = [...inner.matchAll(/\\(.)/g)].filter((m) => !`"\\/bfnrtu`.includes(m[1])).map((m) => `\\${m[1]}`);
    if (badEsc.length) return `非法转义 ${badEsc.join(" ")}`;
    if (/(^|[^\\])"/.test(inner)) return `内部出现未转义的 "`;
  } else if (v.startsWith("'")) {
    if (v.length < 2 || !v.endsWith("'")) return `单引号未闭合`;
  }
  return undefined;
}

const dirs = readdirSync(SKILLS).filter((n) => statSync(join(SKILLS, n)).isDirectory());
const allSkillMds = walk(SKILLS);
const discoverable = allSkillMds.filter((p) => p.slice(SKILLS.length + 1).split(/[\\/]/).length === 2);
const payload = allSkillMds.filter((p) => !discoverable.includes(p));

const problems: string[] = [];
const unknown: string[] = [];
const metaExtra: string[] = [];
const withDisableKey = new Set<string>();
/** 语言面的读数（⑤ / ⑥）与白名单命中情况。`bodyOk` 把**白名单命中**也算合规。 */
let descOk = 0;
let bodyOk = 0;
const allowedHit: string[] = [];
const staleAllowed: string[] = [];
let bytes = 0;

for (const d of dirs) {
  const md = join(SKILLS, d, "SKILL.md");
  let raw: string;
  try {
    raw = readFileSync(md, "utf8");
  } catch {
    problems.push(`缺 SKILL.md: ${d}`);
    continue;
  }
  bytes += Buffer.byteLength(raw);
  const split = splitFrontmatter(raw);
  if (split === undefined) {
    problems.push(`无 frontmatter: ${d}`);
    continue;
  }
  const { fm, body, bodyLine } = split;
  const keys = topKeys(fm);
  const bad = keys.filter((k) => !ALLOWED.has(k));
  const legacy = keys.filter((k) => LEGACY.has(k));
  if (bad.length) unknown.push(`${d}: ${bad.join(",")}`);
  if (legacy.length) problems.push(`legacy 键 ${legacy.join(",")}: ${d}`);
  if (!keys.includes("name")) problems.push(`缺 name: ${d}`);
  if (!keys.includes("description")) problems.push(`缺 description: ${d}`);
  if (keys.includes("disable-model-invocation")) withDisableKey.add(d);
  const nameLine = /^name:\s*(.+)$/m.exec(fm);
  if (nameLine && nameLine[1].trim() !== d) problems.push(`name 与目录不一致: ${d} vs ${nameLine[1].trim()}`);

  // ⑫ **frontmatter 单行标量语法**：`key: "…"` 是 DSH 读到的唯一入口，坏掉会**静默丢弃**该技能。
  for (const line of fm.split(/\r?\n/)) {
    const m = /^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$/.exec(line);
    if (!m) continue;
    const p = scalarProblem(m[1], m[2]);
    if (p) problems.push(`frontmatter 标量非法（${m[1]}）: ${d} —— ${p}`);
  }

  // ⑤ description 必须**英中双语**（缺任一侧即失败）。判据见文件头。
  const desc = /^description:\s*(.*)$/m.exec(fm)?.[1] ?? "";
  const descLatin = LATIN.test(desc);
  const descCjk = CJK.test(desc);
  if (descLatin && descCjk) descOk += 1;
  else {
    const lack = [!descLatin ? "缺拉丁字母" : "", !descCjk ? "缺中文" : ""].filter(Boolean).join(" / ");
    problems.push(`description 非英中双语（${lack}）: ${d}`);
  }
  // ⑥ 正文（frontmatter 之外）不得出现 CJK；豁免只有 LANGUAGE_ALLOWED 里带理由的那些。
  // ⚠ 「白名单命中」**算合规**（同一个检查里 ❌ 与「问题 = 0 ✅」不能并存 —— 那会让人以为门自相矛盾）。
  if (CJK.test(body)) {
    if (LANGUAGE_ALLOWED.has(d)) {
      allowedHit.push(d);
      bodyOk += 1;
    } else {
      problems.push(`正文含 CJK（正文须全英文）: ${d} 首次出现于 :${firstCjkLine(body, bodyLine)}`);
    }
  } else {
    bodyOk += 1;
    if (LANGUAGE_ALLOWED.has(d)) staleAllowed.push(d);
  }

  const origin = /^\s+origin:\s*(\S+)\s*$/m.exec(fm)?.[1];
  const upstream = /^\s+upstream:\s*(\S+)\s*$/m.exec(fm)?.[1];
  const snapshot = /^\s+snapshot:\s*(\S+)\s*$/m.exec(fm)?.[1];
  if (NATIVE.includes(d)) {
    if (origin !== undefined && origin !== "dsh-kit") problems.push(`自有技能 metadata.origin 应为 dsh-kit: ${d} -> ${origin}`);
  } else {
    const expected = origin === undefined ? undefined : ORIGINS.get(origin);
    if (expected === undefined) {
      problems.push(`metadata.origin 缺失或不合法: ${d} -> ${origin ?? "(无)"}`);
    } else {
      if (upstream !== expected[0]) problems.push(`metadata.upstream 与引用总表不符: ${d} -> ${upstream ?? "(无)"}`);
      if (snapshot !== expected[1]) problems.push(`metadata.snapshot 与引用总表不符: ${d} -> ${snapshot ?? "(无)"}`);
    }
  }

  // ⑪ 读数（非致命）：`metadata` 的**子键**超出 origin/upstream/snapshot。
  // 为什么要有它：`topKeys` 只认**列 0** 的键 ⇒ 子键在 ⑩ 的读数里完全不可见，而 ⑩ 打印的
  // 「含未认可键的技能 = 0」会被读成「一个都没有」（实测 `karpathy-guidelines` 就有 `metadata.license`）。
  // 白名单只有三元组：`metadata` 是本包**署名**用的三键结构，别的子键一律显示出来（非致命，不挡退出码）。
  const metaBlock = /^metadata:[ \t]*\r?\n((?:[ \t]+[^\r\n]*\r?\n?)*)/m.exec(fm)?.[1] ?? "";
  const metaKids = [...metaBlock.matchAll(/^[ \t]+([A-Za-z][A-Za-z0-9_-]*)\s*:/gm)].map((m) => m[1]);
  const metaBad = metaKids.filter((k) => !["origin", "upstream", "snapshot"].includes(k));
  if (metaBad.length) metaExtra.push(`${d}: metadata.${[...new Set(metaBad)].join(", metadata.")}`);

  const seen = new Set<string>();
  for (const target of relativeTargets(stripFences(raw))) {
    // 判据收一处：`isPackageRelativeTarget`（裸相对目标也判 —— 旧版只判 `./` / `../` 前缀）。
    if (!isPackageRelativeTarget(target)) continue;
    const path = target.split("#")[0].split("?")[0];
    if (path.length === 0 || seen.has(path)) continue;
    seen.add(path);
    if (!existsSync(resolve(join(SKILLS, d), path))) problems.push(`正文相对路径不存在: ${d} -> ${path}`);
  }
}

// ⑭ **版本一致性**（v6.2.1 新增）：仓根 package.json 与包内 package.json 的 version 必须相等；
// 两份 README 的版本行（表格 + 包 README 页脚）必须与之一致。版本号靠手改 ⇒ 旧门不校验就等于没有守卫。
// 判据只认「读出来的字符串相等」：不比较语义化排序，不猜哪个是权威 —— 不一致就报，让人去对齐。
const VERSION_RE = /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/;

function readPkgVersion(rel: string, label: string): string | undefined {
  let raw: string;
  try {
    raw = readFileSync(join(HERE, "..", rel), "utf8");
  } catch (e) {
    problems.push(`版本门：无法读取 ${rel}（${label}）—— ${(e as Error).message}`);
    return undefined;
  }
  let version: unknown;
  try {
    version = JSON.parse(raw).version;
  } catch (e) {
    problems.push(`版本门：${rel} 不是合法 JSON —— ${(e as Error).message}`);
    return undefined;
  }
  if (typeof version !== "string" || !VERSION_RE.test(version)) {
    problems.push(`版本门：${rel} 的 version 缺失或格式非法 —— ${String(version)}`);
    return undefined;
  }
  return version;
}

/** 从 README 里取版本行；`where` 只用于报错措辞（表格 / 页脚）。 */
function readDocVersion(rel: string, re: RegExp, where: string): string | undefined {
  let raw: string;
  try {
    raw = readFileSync(join(HERE, "..", rel), "utf8");
  } catch (e) {
    problems.push(`版本门：无法读取 ${rel} —— ${(e as Error).message}`);
    return undefined;
  }
  const m = re.exec(raw);
  if (!m) {
    problems.push(`版本门：${rel} 找不到${where}版本行`);
    return undefined;
  }
  return m[1].trim();
}

const rootVer = readPkgVersion("package.json", "仓根 dsh-kit-repo");
const pkgVer = readPkgVersion("integrations/deepseek-harness/package.json", "包 dsh-kit");
if (rootVer !== undefined && pkgVer !== undefined && rootVer !== pkgVer) {
  problems.push(`版本门：两处 package.json 版本不一致 —— 仓根=${rootVer} / 包=${pkgVer}`);
}
// 以**包内** package.json 为参照（它才是发布体；仓根只是占位）。包内读不到时才退回仓根。
const canonicalVer = pkgVer ?? rootVer;
// 显式带 label：两份 README 的 basename 都叫 README.md，只打印文件名会让「哪一份出错」不可辨。
const DOC_VERSION_SOURCES: Array<[label: string, rel: string, re: RegExp, where: string]> = [
  ["根 README", "README.md", /\|\s*版本\s*\|\s*\*\*([^*|\n]+?)\*\*\s*\|/, "表格"],
  ["包 README", "integrations/deepseek-harness/README.md", /\|\s*版本\s*\|\s*([^|*\n]+?)\s*\|/, "表格"],
  ["包 README", "integrations/deepseek-harness/README.md", />\s*版本:([^\s|\n]+)/, "页脚"],
];
const docVers: Array<[string, string, string | undefined]> = [];
if (canonicalVer !== undefined) {
  for (const [label, rel, re, where] of DOC_VERSION_SOURCES) {
    const got = readDocVersion(rel, re, where);
    docVers.push([label, where, got]);
    if (got !== undefined && got !== canonicalVer) {
      problems.push(`版本门：${rel} 的${where}版本与 package.json 不一致 —— ${got} / ${canonicalVer}`);
    }
  }
}
const versionOk =
  rootVer !== undefined &&
  pkgVer !== undefined &&
  rootVer === pkgVer &&
  docVers.length === DOC_VERSION_SOURCES.length &&
  docVers.every(([, , v]) => v === canonicalVer);
console.log(
  `⑭ 版本一致性：仓根=${rootVer ?? "?"} / 包=${pkgVer ?? "?"} / ` +
    docVers.map(([label, where, v]) => `${label}(${where})=${v ?? "?"}`).join(" · ") +
    (versionOk ? " ✅" : " ❌"),
);

// ⑥-补 **白名单腐化计违规**（v6.0.6 修复轮）：豁免表只会单向增长 —— 「文件已无 CJK 却仍挂着豁免」
// 说明它该撤了。旧版只打一行 ⚠、**不进 `problems`** ⇒ 这条可以永远绿着（本仓在别处用「白名单腐化即违规」
// 堵的正是这条路：`audit-layers` 的「纯模块白名单不得腐化」）。
if (staleAllowed.length) {
  problems.push(`LANGUAGE_ALLOWED 腐化（文件已无 CJK，请撤销豁免）: ${staleAllowed.sort().join(",")}`);
}
// 白名单自身的**腐化自检之二**：表里写了不存在的技能目录 ⇒ 该条永不命中，等于没登记。
const allowedGhost = [...LANGUAGE_ALLOWED.keys()].filter((n) => !dirs.includes(n));
if (allowedGhost.length) problems.push(`LANGUAGE_ALLOWED 指向不存在的技能: ${allowedGhost.join(",")}`);
// NATIVE 名单的腐化自检：写了不存在的目录 ⇒ 那份「自有/上游」分类静默失效。
const nativeGhost = NATIVE.filter((n) => !dirs.includes(n));
if (nativeGhost.length) problems.push(`NATIVE 名单指向不存在的技能: ${nativeGhost.join(",")}`);

const missingD8 = USER_INVOKED.filter((n) => !withDisableKey.has(n));
const extraD8 = [...withDisableKey].filter((n) => !USER_INVOKED.includes(n)).sort();
if (missingD8.length) problems.push(`D8 名单缺 disable-model-invocation: ${missingD8.join(",")}`);
if (extraD8.length) problems.push(`D8 名单外多出 disable-model-invocation: ${extraD8.join(",")}`);

// ⑬ **D8 的独立旁证**（v6.0.6 修复轮新增；CONTEXT D8 末句原来只是一句无人守的断言）：
// 上游随附的 `skills/<name>/agents/openai.yaml` 是 **Codex 面向**的成文清单，其中
// `allow_implicit_invocation: false` 的恰好应当是本包这 8 个用户调用型技能。
// 它把「D8 是不是我们自己说的」变成**两条独立来源互校**：本包的 `disable-model-invocation`
// 与上游自己的清单必须给出同一个 8 人集（多一个少一个都报）。
// ⚠ `walk` 只收 `SKILL.md`（技能面语料），旁证要另一个遍历：任何 `agents/openai.yaml`。
const walkAgentsYaml = (dir: string, out: string[] = []): string[] => {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walkAgentsYaml(p, out);
    else if (n === "openai.yaml" && p.split(/[\\/]/).slice(-2).join("/") === "agents/openai.yaml") out.push(p);
  }
  return out;
};
const openaiYamls = walkAgentsYaml(SKILLS);
const noImplicit = openaiYamls
  .filter((p) => /allow_implicit_invocation:\s*false/.test(readFileSync(p, "utf8")))
  .map((p) => p.slice(SKILLS.length + 1).split(/[\\/]/)[0])
  .sort();
const onlyOurs = USER_INVOKED.filter((n) => !noImplicit.includes(n));
const onlyUpstream = noImplicit.filter((n) => !USER_INVOKED.includes(n));
if (onlyOurs.length || onlyUpstream.length) {
  problems.push(
    `D8 与上游 agents/openai.yaml 不一致（本包独有: ${onlyOurs.join(",") || "无"} / 上游独有: ${onlyUpstream.join(",") || "无"}）`,
  );
}

const payloadRel = payload.map((p) => p.slice(SKILLS.length + 1).split(/[\\/]/).join("/"));
const payloadOk = payloadRel.length === EXPECTED_PAYLOAD.length && payloadRel.every((p) => EXPECTED_PAYLOAD.includes(p));
if (!payloadOk) {
  problems.push(`载荷型嵌套 SKILL.md 与预期不符: ${payloadRel.join(", ") || "(无)"}（期望 ${EXPECTED_PAYLOAD.join(", ")}）`);
}

console.log(`技能目录数 = ${dirs.length}（期望 ${EXPECTED}）${dirs.length === EXPECTED ? " ✅" : " ❌"}`);
console.log(`可发现的 SKILL.md = ${discoverable.length}`);
console.log(`载荷型嵌套 SKILL.md = ${payload.length}${payloadOk ? " ✅" : " ❌"}`);
for (const p of payloadRel) console.log("   · " + p);
console.log(`用户调用型（disable-model-invocation）= ${withDisableKey.size}（期望 ${USER_INVOKED.length}）${withDisableKey.size === USER_INVOKED.length ? " ✅" : " ❌"}`);
// ⑬ 的双校读数（CONTEXT D8 末句的**独立旁证**）：数量由 glob 现算，不写死在文档里。
console.log(`   ⑬ D8 与上游旁证：agents/openai.yaml = ${openaiYamls.length} 个，其中 allow_implicit_invocation: false = ${noImplicit.length} 个${noImplicit.length === USER_INVOKED.length ? " ✅（与本包同一个 8 人集）" : " ❌"}`);
console.log(`⑤ description 英中双语 = ${descOk} / ${dirs.length}${descOk === dirs.length ? " ✅" : " ❌"}`);
console.log(`⑥ 正文全英文 = ${bodyOk} / ${dirs.length}${bodyOk === dirs.length ? " ✅" : " ❌"}（白名单命中计入合规）`);
console.log(`   正文 CJK 显式豁免 = ${LANGUAGE_ALLOWED.size} 条（本次命中 ${allowedHit.length} 条）${staleAllowed.length ? " ⚠ **有腐化条目 ⇒ 已计违规**" : ""}`);
for (const [name, why] of LANGUAGE_ALLOWED) {
  const hit = allowedHit.includes(name);
  console.log(`   · ${name}${hit ? "" : "（⚠ **该文件已无 CJK ⇒ 豁免已腐化，已计违规，请撤销这条**）"} —— ${why}`);
}
if (LANGUAGE_ALLOWED.size === 0) console.log("   · （空表：正文全英文是目标形态）");
console.log(`致命 frontmatter / 元数据 / 死链 / 语言问题 = ${problems.length}${problems.length === 0 ? " ✅" : " ❌"}`);
for (const p of problems) console.log("  ❌ " + p);
console.log(`非致命：含未认可键的技能 = ${unknown.length}`);
for (const u of unknown) console.log("   · " + u);
// ⑪ **读数**（非致命；只报告，不改退出码 —— 它衡量的是"够不够整齐"，不是"合不合规"）。
// ⚠ 打印时写清口径：⑩ 只覆盖**列 0** 的键，`metadata` 子键在 ⑪ 里另算，两处不要互相读成"没有"。
console.log(`非致命读数 ⑪：metadata 子键超出白名单（origin/upstream/snapshot）的技能 = ${metaExtra.length}`);
for (const u of metaExtra) console.log("   · " + u);
console.log(`SKILL.md 正文总体量 = ${(bytes / 1024 / 1024).toFixed(2)} MB`);

process.exitCode = problems.length === 0 && dirs.length === EXPECTED ? 0 : 1;
