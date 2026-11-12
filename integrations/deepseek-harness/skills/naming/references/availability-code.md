# 代码侧的「可用性」：能编译 + 合规范 + 不冲突

> 用途：code 模式。产品侧的可用性（域名/商标/生成式可提及性）见 `availability.md`，两者互不适用——
> 别把「域名可注册」当成「这个变量名可用」。

## 1. 代码里"名字可用"的四个判据

1. **编译/解析通过**：改名后 build 与 test 变绿。这是唯一的硬门槛。
2. **lint 通过**：项目既有 ESLint / ruff / golangci / checkstyle 等；部分 S-I-D 可规则化。
3. **glossary 命中**：用项目词表里的词；新概念**先入词表**再写代码。
4. **近名冲突扫描**：同一作用域里是否有同名异义、近名异义。

## 2. 机器扫描

```
python scripts/check-code-names.py <path> \
    [--lang auto] [--engine auto|ast-grep-py|ast-grep-cli|regex] \
    [--json|--out F] [--strict] [--synonyms] [--rename OLD=NEW]
```

- 三层引擎自动降级并**打印警告**；JSON 带 `engine` 与 `scope`，能看出结果是 AST 还是正则产出。
- 输出：缩写 / vague verb / 否定式 / 单字母 / 同类型大小写冲突 / 垃圾模块名，以及仓库级 `near_name`。
- `--synonyms`（默认关）追加同义动词混用提示；默认关的理由是同义动词常是**合理区分**（`fetch` vs `load`）。
- 近名与同义都是**启发式 Minor**，语义仍由 glossary 与人工定夺。
- 自检：`python scripts/test_check_code_names.py`。

## 3. 跨层时另有一套

同一个概念要出现在 API 字段 / DB 列 / 事件 / 指标 / 配置里时，"可用"还包括**跨层一致**：

```
python scripts/check-cross-layer.py check --map docs/naming-map.md
python scripts/check-cross-layer.py audit --map docs/naming-map.md --code <schema 目录>
```

三宗陷阱（`is_` 前缀方向相反、`*_time` vs `*_at`、`_total` 有无）与 expand→migrate→contract
的顺序见 `api-naming.md` §0 与 §5.5。

## 4. 改名前的影响面

查引用（`grep` / IDE rename）；对外 API、序列化字段、DB 列改名要评估兼容（别名 / 双写 / 版本化）。
影响面按三档标注：**可自动改 / 需人工确认 / 不要动**（DB 列、契约字段、事件名、序列化键）。

```
python scripts/check-code-names.py <path> --rename OLD=NEW
```

它做**文本级**分类（声明行 / 注释与引用 / 字符串与序列化键），不做重写；跨文件语义改名请用 IDE/LSP。

## 与其它文件的关系

- 产品侧可用性（域名/商标/L1.5）→ `availability.md`；本文件只讲代码。
- 语言层命名规则 → `code-style.md`；跨层规则 → `api-naming.md`。
- UI 文案/无障碍标签的可理解性 → `ui-naming.md`（不可正则化，只给检查表）。
