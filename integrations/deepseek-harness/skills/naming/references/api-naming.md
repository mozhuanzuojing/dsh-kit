# 跨层命名：API / 数据库 / 事件 / 指标 / 配置

> 用途：code 模式，当同一个业务概念要同时出现在 **API 字段、DB 列、事件属性、指标/属性、配置 key** 五层时。
> 核心结论：**跨层改名不是大小写变换，是语义重命名**。能机械转换的只有很小一片白名单。
> 强度：**机构**＝官方规范/linter 文档；**经验**＝业界惯例；**判断**＝本文推断。

## 0. 先记住三条"跨层陷阱"（最容易踩、且没有 linter 管）

| 陷阱 | 冲突双方 | 后果 |
|---|---|---|
| **`is_` 前缀的双向矛盾** | AIP-140 要求布尔**省略** `is`（`disabled`）；GitLab SQL 指南要求布尔**必须**以 `has_/is_/does_` 开头（`is_deleted`） | 任何"字段名自动 snake↔camel 同步"都会在某一侧违规 |
| **时间戳的时态矛盾** | AIP-142 明确**不得用过去式**（`publish_time`，禁 `published_time`）；Azure/GitLab/K8s 全用过去式或 `Timestamp` 后缀 | 跨层改名必须建**显式映射表**，不能字符串变换 |
| **指标 `_total` 的双标准** | Prometheus 强制 `_total`；OpenTelemetry 明确 SHOULD NOT 加 | 同一定义导出两套后端，必有一侧违规；必须维护「规范名 + 每后端映射」 |

来源：AIP-140 <https://google.aip.dev/140>、AIP-142 <https://google.aip.dev/142>、GitLab SQL style guide <https://gitlab.com/gitlab-com/content-sites/handbook/-/blob/main/content/handbook/enterprise-data/platform/sql-style-guide.md>、Prometheus naming <https://prometheus.io/docs/practices/naming/>、OTel naming <https://opentelemetry.io/docs/specs/semconv/general/naming/>。

## 1. API 字段与资源（AIP 为主）

| 规则 | 正例 | 反例 | 来源 |
|---|---|---|---|
| 字段名 `lower_snake_case` | `display_name` | `displayName`（在 proto 里） | AIP-140 |
| 布尔**省略** `is`/`has` | `disabled`、`deleted` | `is_disabled` | AIP-140 |
| 时间字段用**现在时** | `create_time`、`update_time` | `created_at`、`createdTime` | AIP-142 |
| 时间戳后缀统一 `_time`，时长用 `Duration` 类型 | `expire_time`、`ttl`（Duration） | `expire_at`、`ttl_seconds` | AIP-142 |
| 数量/度量带**单位后缀** | `distance_km`、`timeout_sec` | `distance`、`timeout`（无单位） | AIP-141 |
| 资源名统一 `name`，**禁**用它表示人名 | `name: "projects/p/books/b"` | `name: "张三"` | AIP-122 |
| 分页：`page_size` / `page_token` / `next_page_token`；token **不透明** | — | 把 offset 塞进 token 并暴露给前端 | AIP-158 |
| 枚举值 `UPPER_SNAKE` 且零值 `*_UNSPECIFIED` | `STATE_UNSPECIFIED` | `UNKNOWN`（与业务态混淆） | AIP-126 |
| 标准错误用 `google.rpc.Code` 语义，不自造字符串 | — | `{"error": "not_found"}` | AIP-193 |

**判断**：AIP 是"祈使/现在时"体系，Azure/GitLab/K8s 是"过去时/后缀"体系。选一套当**权威**，另一套只在边界处映射——不要试图两边都满足。

## 1.5 命名总则（AIP-190，2025-06 新批准）

AIP-190 是 Google 2025 年新加的"命名总则"，比逐字段规则更靠前——先满足这五条，再谈大小写：

| 规则 | 原文要点 | 落地 |
|---|---|---|
| **同概念同词，异概念异名** | "Use the same name or term for the same concept"；"Avoid name overloading" | 与 `code-style.md` §10 的 glossary 同源；跨 API 也要一致 |
| **避免过度一般的名字** | `instance` / `info` / `service` 被点名为历史问题词；要求"说清是什么的 instance" | `info` 已在 `anti-patterns.md` 的 weasel 后缀里 |
| **用美式英语** | license（非 licence）、color（非 colour） | 非英语团队最常犯；品牌名不受此约束 |
| **公认缩写可用** | `API` 优于 `Application Programming Interface` | 与 `code-style.md` §7 的缩写白名单同一逻辑 |
| **慎用与常见编程语言关键字冲突的名字** | 可用，但会引发额外审查；"use them judiciously and sparingly" | `type`、`class`、`default` 这类作为字段名要谨慎 |

出处：AIP-190 <https://google.aip.dev/190>（**机构**，2025-06 批准）。

## 2. IDL（protobuf / gRPC）

- 字段 `lower_snake_case`、消息 `PascalCase`、枚举 `PascalCase` + 值 `UPPER_SNAKE` + 类型名前缀、服务 `FooService`、RPC `GetBook`。
- **可直接用 `buf lint` 落地**：STANDARD 级覆盖字段/消息/枚举/服务/RPC/包名大小写、枚举值前缀、零值后缀、service `Service` 后缀、RPC 请求/响应命名。
- `buf breaking` 的 `FIELD_SAME_NAME` 等规则能在 CI 拦下**改名**——即"改名即破坏"。来源：<https://buf.build/docs/lint/rules/>、<https://buf.build/docs/breaking/rules/>。

## 3. 数据库

| 规则 | 约定 | 说明 |
|---|---|---|
| 表名 | 复数蛇形 `orders`（Rails 系）或单数（部分团队） | **选一个并在 glossary 里定死**；混用是最常见的跨层漂移 |
| 主键 | `id` | 与 API 的 `name` 不是同一物（API 资源路径 ≠ DB 主键） |
| 外键 | `<单数表>_id`（`order_id`） | 不是 `orderId`、不是 `fk_order` |
| 时间 | `created_at` / `updated_at` / `deleted_at` | **与 API 的 `create_time` 冲突**，需映射 |
| 布尔 | `is_active` / `has_shipped`（GitLab 派） | 与 AIP 相反，见 §0 |
| 索引 | `idx_<table>_<cols>` / 唯一 `uq_<table>_<cols>` | 约束命名见 GitLab 约定 |
| 长度 | PostgreSQL 标识符 **63 字节**，超出**静默截断** | `squawk` 的 `identifier-too-long` 可查 |

来源：<https://www.postgresql.org/docs/current/sql-syntax-lexical.html>、<https://docs.gitlab.com/development/database/constraint_naming_convention/>、<https://squawkhq.com/docs/rules>。

**注意**：`sqlfluff` 只有 `CP02`（大小写）、`AL01–AL09`（别名）、`CV09`（禁用词）——**没有任何表/列命名规范规则**。`_at`、`is_`、`idx_` 这些都要自己查（判断）。

## 4. Kubernetes / 可观测性 / 配置

- **K8s**：JSON/Go 字段 `camelCase`，禁下划线与短横；`spec` 是期望态、`status` 是观测态；Condition 的 `type` 用短 PascalCase（`Available`）。
  来源：<https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md>
- **OTel**：属性用点分命名空间 `http.request.method`；指标名不加单位后缀（单位在元数据）。
  来源：<https://opentelemetry.io/docs/specs/semconv/general/naming/>
- **Prometheus**：`namespace_subsystem_name`，计数器加 `_total`，单位用基础单位后缀（`_seconds`、`_bytes`）。
  来源：<https://prometheus.io/docs/practices/naming/>
- **配置 / env**：`UPPER_SNAKE`（POSIX 字符集）；12-Factor 要求配置放环境变量。
  来源：<https://12factor.net/config>、<https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap08.html>
- **Feature flag**：key 一旦进 DB/日志就是**永久契约**（LaunchDarkly 的 key 不可改），必须一开始就按 `release.*` / `ops.*` / `experiment.*` 分组。
  来源：<https://launchdarkly.com/docs/guides/flags/flag-conventions/>

## 5. 跨层概念表（唯一真源）

**做法**：为每个跨层概念维护一行，五列都写出来；**代码/DDL/指标定义都从这里生成或校验**。

| 概念 | API 字段 | DB 列 | 事件属性 | 指标/属性 | 配置 key | 判定 |
|---|---|---|---|---|---|---|
| 创建时间 | `create_time` | `created_at` | `time` | `*.created.timestamp` | — | 陷阱：需映射表 |
| 资源标识 | `name` | `id` | `subject` / `id` | `*.id`（高基数，禁作标签） | — | 陷阱：三层语义不同 |
| 布尔状态 | `disabled` | `is_disabled` | `enabled` | `*.enabled` | `FEATURE_X_ENABLED` | **陷阱：规则相反** |
| 时长/超时 | `timeout`（Duration） | `timeout_ms` | `duration` | `*.duration` / K8s `*TimeoutSeconds` | `TIMEOUT_MS` | 陷阱：三套单位制 |
| 地区 | `region_code`（禁 `country_code`） | `region_code` | `region` | `geo.region.iso_code` | — | 允许（同名） |
| 计数量 | `node_count` | `node_count` | `count` | `system.node.count` | `MAX_NODES` | 允许；指标侧禁 `_total` |
| 累计请求 | — | `request_count` | — | `http_server_requests_total`（Prom） | — | 陷阱：Prom 加 `_total`，OTel 不加 |

**落地（现在有工具了）**：

```
python scripts/check-cross-layer.py init  --out docs/naming-map.md      # 生成骨架
python scripts/check-cross-layer.py check --map docs/naming-map.md       # 校验三宗陷阱
python scripts/check-cross-layer.py audit --map ... --code <schema 目录>  # 报"表里没有的名字"
```

`check` 机器化以下规则：`is_prefix_conflict`（API 层禁 `is_`、DB 层要求 `is_`，两侧同时报）、
`tense_conflict`（API 层用过去式）、`total_conflict`（`_total` 双标准）、`unit_missing`
（**AIP-141 度量**在 API 层也要带单位；**AIP-142 时长**在 API 层用 Duration 类型不带单位，只在 DB/配置层带）、
`name_as_person`、`row_malformed`。

`audit` 默认只扫 `.proto` / `.sql` 等 schema 源（名字真正被定义的地方），加 `--include-code` 才扫普通源码
——否则局部变量噪声会淹没结果。自检：`python scripts/test_check_cross_layer.py`（10 用例）。

新概念先入表再写代码（与 `code-style.md` §10 的 glossary 同源）。

## 5.5 改名的兼容性与顺序（AIP-180 的硬规则）

跨层改名不是一次文本替换，是**契约变更**。AIP-180 的原文规则（直接引用要点，标 **机构**）：

| AIP-180 规则 | 原文要点 | 对命名的含义 |
|---|---|---|
| **删除/改名 = 删除 + 新增** | "Renaming a component is semantically equivalent to 'remove and add'"；同一 major 版本内**不得删除**既有组件 | 改名必须**新增**新名并**保留**旧名，不能原地替换 |
| **资源名不得改** | "A resource **must not** change its name"，且跨 major 版本也必须一致 | `name` 字段/资源路径是**永久标识**，不是可优化项 |
| **字段类型不得改** | 即使 wire 兼容，生成代码会破坏 | `int32` → `string` 这类"顺手改名"不可做 |
| **不得移入/移出 oneof** | Go stubs 破坏 | 布尔/可选字段的重构有隐藏成本 |
| **默认值不得变** | "Default values must not change" | 新增字段的默认行为必须等于"没有该字段时"的旧行为 |

**改名的三步顺序（expand → migrate → contract）**：

1. **expand**：新增新名，旧名保留并标记 deprecated；两者同时可写，读出时取有值的一方；显式规定冲突时的优先级。
2. **migrate**：数据/调用方迁移；监控旧名调用量直到归零（**这是唯一的完成判据**，不是"代码改完了"）。
3. **contract**：旧名进入 reserved（字段号/枚举值不得复用），文档标注移除版本；**只有在确认无调用方后**才删。

**回滚**：expand 阶段可无损回滚（新名不用即可）；一旦 contract 就**不可回滚**（旧名已不可写）。所以 contract 必须单独一次发布，且带观察窗口。

来源：AIP-180 <https://google.aip.dev/180>（`Removing or renaming components`、`Changing resource names`、`Default values must not change` 三节）。**未验证**：字段号 reserved 的具体写法本轮未取到原文，按"不要复用字段号"这一通用惯例执行。

## 6. 允许的机械转换（白名单）与禁用转换

**允许**：
- `lower_snake_case` ↔ `camelCase`（proto ↔ JSON，官方保证）
- Go `PascalCase` ↔ JSON `camelCase`（K8s 官方保证）
- `UPPER_SNAKE_CASE` ↔ 环境变量（POSIX 字符集内）
- 点分命名空间 → 指标前缀（`http.server.request.duration` → `http_server_request_duration`，OTel↔Prom 官方对照）

**禁止机械转换**（必须人工映射）：
- 单复数（`book`/`books` 在 AIP 里是语义区分）
- `name` ↔ `id`
- `*_at` ↔ `*_time`
- `_total` 的有无
- 枚举零值（`*_UNSPECIFIED` 只存在于 proto，DB 里没有）
- `uri` ↔ `url`

## 7. 现有 linter 能覆盖到哪（别重复造轮子）

| 层 | 工具 | 能查 | 查不到 |
|---|---|---|---|
| protobuf | `buf lint` / `buf breaking` | case、枚举前缀、零值、service 后缀、改名破坏 | 单复数、介词、单位后缀 |
| OpenAPI | `spectral`（`casing` + `operation-operationId`） | 7 种 case、operationId 唯一性与风格 | 资源层级、分页字段 |
| SQL | `sqlfluff`（CP02/AL） / `squawk` | 标识符大小写、别名、63 字节、改名风险 | **表/列命名规范**（完全没有） |
| K8s | `kube-linter` | 端口名、secret 环境变量、重复 env | 通用字段命名 |
| AIP | `api-linter` | AIP 风格检查（规则清单未逐条验证） | 非 AIP 风格 |

**判断**：IDL 层已高度工具化，DB 层几乎空白——所以**自定义检查的投入应优先给"跨层映射表"和"DB 命名"**，而不是再写一个 proto linter。

## 与其它文件的关系

- 语言层（camel/snake、S-I-D、动词）→ `code-style.md`；本文件只讲**跨层**。
- 重命名影响面三档 → `code-style.md` §10.1（`risky` 档正是本文件 §0 的三种陷阱）。
- 近名/一致性聚合脚本 → `scripts/check-code-names.py`（`--synonyms` / `--rename`）。
- 证据与出处 → `sources.md` §9。
