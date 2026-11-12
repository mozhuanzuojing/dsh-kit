# 代码标识符命名规则（code 模式）

> 综合 Google Go Style、PEP 8、Airbnb JS、Microsoft .NET、kettanaito/naming-cheatsheet、clean-code-javascript、codingjoe/naming-things、heyJordanParker/naming、腾讯《起名根治指南》。

## 0. 权威顺序
**项目既有约定 > 语言/框架约定 > 通用最佳实践**（heyJordanParker）。先读周边代码 + 项目 glossary/Domain.md；保持一致比"更正确"更重要。

## 1. 语言约定（格式层，速查）
| 语言 | 变量/函数 | 类型/类 | 常量 | 备注 |
|---|---|---|---|---|
| JS/TS | camelCase | PascalCase | UPPER_SNAKE（仅导出+const+不变） | 不用首尾下划线 |
| Python | snake_case | CapWords | UPPER_CASE | `_x` 内部、`__x` name-mangling |
| Java | camelCase | PascalCase | UPPER_SNAKE | 不用下划线 |
| Go | camelCase（导出 Pascal） | PascalCase | Pascal/Camel | 缩写全大写：`HTTPServer` |
| C#/.NET | camelCase(参数/局部) | PascalCase(公共成员/类型) | PascalCase | 不用下划线；`Id` 非 `ID` |
| Rust | snake_case | PascalCase | UPPER_SNAKE | — |

## 2. S-I-D（每个名字都要过）
- **Short**：不长到难打/难记。
- **Intuitive**：读起来自然，像日常用语（`isPaginatable` 生造 → `hasPagination`）。
- **Descriptive**：高效反映它做什么/有什么。

## 3. 函数 A/HC/LC 模式
`prefix? + action(A) + highContext(HC) + lowContext?(LC)`
| 名字 | prefix | A | HC | LC |
|---|---|---|---|---|
| getUser | – | get | User | – |
| getUserMessages | – | get | User | Messages |
| handleClickOutside | – | handle | Click | Outside |
| shouldDisplayMessage | should | Display | Message | – |
语境顺序改变含义：`shouldUpdateComponent`（我准备更新组件）vs `shouldComponentUpdate`（组件自我更新）。

## 4. 动词词典
- 取数：`get`（同步/异步皆可）；`fetch/load/read`（远端/磁盘/流）
- 设值：`set`；重置：`reset`
- 增：`add/append/insert/push`（按容器语义）；删：`remove`（配 add）、`delete`（配 create）、`clear`
- 造：`create/from/of/with/valueOf`（工厂）；`compose`（组合出新数据）
- 处理事件：`handle`（回调）；`on[Event]`
- **禁 vague**：`process/handle(泛用)/manage/do/run/data/temp/foo/bar`
- **split test**：一个函数叫不出一个动词＝做太多事，拆分。

## 5. 前缀 / 布尔
- `is`（特征/状态）、`has`（是否有）、`can`（能否）、`should`（是否应当）；`min/max`、`prev/next`
- **正向表述**：`isEnabled` 而非 `!isDisabled`；`isEmpty` 而非 `hasNoItems`
- 单数=单值，复数=集合：`friend`/`friends`

## 6. 语法规则
- **类/类型 = 名词**：`BookService`（非 `ServiceOfBook`）、`PriorityQueue`；接口表能力用 `-able`（Java/C++：`Serializable`）
- **方法 = 动词/动宾，动词在前**：`replaceTire()`（非 `tireReplace()`）
- **Getter 省 get**：`count()` 非 `getCount()`
- **Predicate**：`is/are` 或直接形容词（`done()`、`enabled()`）；`must`=失败即抛（`MustCompile`）
- **介词**：`to`（转换出新对象）/`as`（视图/引用）/`of|from|with`（工厂）/`on`（监听）
- 辅助类（Java）用被辅助类复数：`Strings`/`Lists`，不用 `StringUtils`

## 7. 缩写白名单（公开 API 用全称）
- ✅ 认可：`config, id, spec, stats, db(Go/C++), regex/regexp, html, url, api, http`
- ❌ 未认可：`req, resp/rsp, svr, obj, meta, biz, mgr, ctrl`（除非项目已约定）
- 局部变量可宽松，但**公开名称一律写全**。

## 8. 时间 / 单位 / 度量
- 时间点用 `at` 后缀 + 时区：`created_at`、`scheduled_at`
- 时长/超时带单位：`timeout_ms`、`ttl_secs`
- 度量带 SI/尺寸单位：`weight_kg`、`w1200_h300`

## 9. 禁用词（weasel / 垃圾模块）
- 模块名禁：`utils, helpers, common, shared, lib, core, base`
- 类名后缀禁（无信息）：`Info, Data, Manager, Helper, Util, Base, Item, Processor, Impl, Object, Entity`；但**含真实角色语义时保留**（如 `PaymentProcessor` / `OrderItem` / `FooImpl` / `BaseService`）。
- `Service/Repository/Controller/Adapter/Decorator/Proxy` 只在架构角色确有其义时用，且与项目一致。

## 10. 一致性 / 词表 / 近名
- 维护 **glossary**：一个概念一个词；同义归一（save/store/put → 选一个；fetch/retrieve → fetch）
- 检测**近名冲突**：同名异义（`db`/`conn`）、近名异义（`clazz`/`clz`、`agentName`/`agentNames`）；语义不同必须区分，语义相同必须统一
- **可机器化的部分交给脚本**：`python scripts/check-code-names.py <path>` 会出 repo 级 `near_name`（大小写/编辑距离≤1/单复数/容器后缀），加 `--synonyms` 再出 `synonym_drift`（同义动词混用 + 本仓库主流用法）。两类都是**启发式 Minor 提示**，语义仍由 glossary 定夺（判断）
- 测试命名：`test_<行为>__<场景>`（双下划线），祈使句，不用 should/expect/it

## 10.1 重命名（blast radius）
改名前先分级，再动手（`python scripts/check-code-names.py <path> --rename OLD=NEW` 给出三个计数）：

| 档 | 典型位置 | 处理 |
|---|---|---|
| **auto** 可自动改 | 声明行 + 同文件引用（有编译器/LSP 保证） | IDE rename / codemod |
| **manual** 需人工确认 | 注释、文档、日志文案、测试名、跨语言调用 | 逐处判断是否属于同义 |
| **risky** 不要动 | 字符串字面量、序列化键、DB 列名、事件名、HTTP 路由、配置键 | 改名即破坏契约；要改走迁移（别名/双写/版本化） |

判定顺序：**先看是不是契约（risky 优先），再看是不是注释，最后才当普通引用**。脚本只做文本级分类，跨文件语义改名请用 IDE/LSP（判断）。

**改名的执行顺序**（涉及 risky 档时必须走这三步，见 `api-naming.md` §5.5）：**expand（新旧并存）→ migrate（监控旧名调用量归零）→ contract（删除旧名，字段号/枚举值 reserved）**。expand 可无损回滚，contract 不可回滚 —— 所以 contract 单独一次发布并留观察窗口。判据是"旧名调用量为 0"，不是"代码改完了"。

## 11. 上下文重复 / 冗余
- `class MenuItem { handleClick }` 而非 `handleMenuItemClick`（去掉重复语境）
- `Car { make }` 而非 `carMake`
- 不要冗余类型：`userObject`→`user`、`dataList`→`items`

## 11.1 跨层命名（API / DB / 事件 / 指标 / 配置）

语言层对了不代表跨层对。同一个概念在五层里的名字常常**不能机械转换**（`is_` 前缀在 AIP 与 GitLab 指南里方向相反、`create_time` vs `created_at`、Prometheus 要 `_total` 而 OTel 明文不要）。做法与三宗陷阱见 `api-naming.md`：维护一张「跨层概念表」，新概念先入表再写代码。

## 11.2 UI 层（界面文案 / CSS / 组件 / aria / i18n）

代码标识符对了，界面上的名字仍可能错。按钮、空态、错误提示、CSS 类、设计令牌、组件名、路由、`aria-label`、i18n key 的规则见 `ui-naming.md`。三条最常犯的：危险操作不写后果（`删除` vs `永久删除 3 个文件`）、设计令牌用外观名（`--color-red` 而非 `--color-danger`）、图标按钮没有含对象的 `aria-label`。

## 12. 快速自检
能否发音？同词是否一致？可搜索（无裸魔术数）？无 mental mapping（`location` 非 `l`）？无 flag 参数？无语境重复？加/删一个词意思变不变（不变=填充词）？
