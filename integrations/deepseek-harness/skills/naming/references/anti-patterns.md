# 反模式：什么会毁掉一个名字

## A. 产品命名 — AI 味与五宗罪

### AI Name Slop（AI 生成味的红旗）
| 模式 | 例子 | 为何死 |
|---|---|---|
| 后缀成瘾 | Glidely, Parsify, Chatible, Syncora | 所有 AI 都用 -ly/-ify/-able/-ora，千篇一律 |
| 无意义混拼 | Brightrix, Nexagen, Vaultora | 技术唯一但彼此可互换，无故事无意象 |
| 同义词库抽取 | Apex, Pinnacle, Summit, Zenith | 被用烂，同义词库不是命名工具 |
| 类别+修饰 | CloudGuard, DataSync, SiteWatch | 描述但不可记 |
| 空洞企业词 | X Solutions / Labs / Platform / HQ | 什么也没说 |
| 过度拼写错误 | 去所有元音、K 替 C | 2010 年短暂有效，现只表示"真名被占" |
| 假拉丁/希腊 | Cognivex, Synaptiq, Quantera | 唬人 2 秒，毫无意义 |
| 空洞形容词 | BrightPath, TrueNorth, ClearView | 任何品类都能用 |

**判据**：能在三个不同品类产品间互换还"成立" → 就是 slop。好名是**具体**的。

### 五宗罪（命中任一即死）
1. **无聊的描述名**（"WordPress Site Monitor" 是描述不是名）
2. **无意义生造混拼**（Syncora/Brightrix…）
3. **同义词库名**（Apex/Pinnacle/Summit）
4. **空洞企业词**（Solutions/Network/Systems/Platform/Labs/Group/Global）
5. **为极端而极端**（DEATHKRYPT ULTRA 给待办 App）

### 复合词陷阱
- **首词填充**：Smart / Auto / Cloud / AI / Data / Cyber / Next / Digital / True / Pure / Open / Fast / Easy / Pro / Ultra / Hyper / Super / Meta / Omni / Core
- **次词空泛**：Hub / Lab(s) / Base / Flow / Sync / Link / Stack / Forge / Shift / Scape / Verse / Craft / Wise / Path / Nest / Box
- **复合测试**：盖住一半，另一半还具体吗？能否用同义词替换还"一样好"？能→无特异性，杀。

### AI 产品专属（2023–2025）
- `AI` 前后缀（AIWriter/CopyAI）：会过时，像当年的 e-/cloud。
- `Co-/pilot` 模仿（xxxPilot）：cockpit 隐喻已被 Copilot 占，`[品类]pilot` 是定位不是名。
- 人类名（Sarah/Devin）：仅当 AI 就是界面本体才成立。
- Magic 系（Magic/Spell/Wand/Conjure）：B2B 几乎都错。
- Smart / Neural / Neuro 前缀：冗余、装饰。

### 红旗清单（≥2 个"是"→淘汰）
听起来像另外 10 个产品？讲不出 15 秒故事？要逐字母拼？只在视觉上好听？只是"酷词"无隐喻？换品类还成立？去掉大小写/特殊字符就变通用？命中 ≥3 条 slop？职业介绍会尴尬？唯一优点是域名空着？

## B. 代码命名 — anti-patterns

| 反模式 | 例子 | 修法 |
|---|---|---|
| 缩写 | `req`/`resp`/`svr`/`obj`/`biz` | 用全称（白名单除外） |
| vague verb | `process`/`handle`(泛)/`manage`/`do`/`run`/`data`/`temp`/`foo` | 换成具体动词（parse/validate/dispatch…） |
| weasel 后缀 | `Info`/`Data`/`Manager`/`Helper`/`Util`/`Base`/`Item`/`Processor`/`Impl`/`Object`/`Entity` | 删掉或换成有信息的名 |
| 垃圾模块名 | `utils`/`helpers`/`common`/`shared`/`lib`/`core`/`base` | 按领域拆分成具体模块 |
| 否定式布尔 | `isNotReady`/`hasNoItems`/`isDisabled`（被取反用） | 用正向：`isReady`/`isEmpty`/`isEnabled` |
| 单字母/过短 | `a`/`b`/`x`（非紧凑循环/数学） | 按作用域给具名 |
| 上下文重复 | `class MenuItem { handleMenuItemClick }` | `handleClick` |
| 同义不一致 | `db`/`conn` 混用、`getUser`/`getUserInfo`/`getClientData` 混用 | 归一到一个词（glossary） |
| 近名异义 | `clazz`/`clz`、`agentName`/`agentNames` | 语义区分或统一，别只差后缀 |
| flag 参数 | `render(true, false, true)` | 用具名 options 对象/枚举 |
| 冗余类型 | `strName`/`userObject`/`dataList` | 类型交给类型系统 |

**代码红旗**：名字里能删的词（删了意思不变）→ 填充词；一个函数叫不出一个动词 → 做了太多事，拆。
