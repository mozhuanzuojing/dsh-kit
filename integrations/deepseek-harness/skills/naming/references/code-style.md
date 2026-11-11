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
- 测试命名：`test_<行为>__<场景>`（双下划线），祈使句，不用 should/expect/it

## 11. 上下文重复 / 冗余
- `class MenuItem { handleClick }` 而非 `handleMenuItemClick`（去掉重复语境）
- `Car { make }` 而非 `carMake`
- 不要冗余类型：`userObject`→`user`、`dataList`→`items`

## 12. 快速自检
能否发音？同词是否一致？可搜索（无裸魔术数）？无 mental mapping（`location` 非 `l`）？无 flag 参数？无语境重复？加/删一个词意思变不变（不变=填充词）？
