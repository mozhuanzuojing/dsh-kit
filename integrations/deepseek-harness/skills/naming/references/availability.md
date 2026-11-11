# 可用性 / 校验（availability）

## 产品模式（域名 / 包名 / 社媒 / 商标）
**顺序**：① 竞品冲突搜索（最常杀名，先做）→ ② 域名 → ③ 包名 → ④ 社媒/应用商店 → ⑤ 商标（只提示，法律判断交用户）。
- 竞品：web 搜 `"[name]" <品类>`、`"[name]" app/software`；有直接竞品＝死，别再查域名。
- 域名：字典常见词跳过 .com/.dev/.io/.app/.co 精确匹配，直接看 `get[name]`/`use[name]`/`.sh`/`.site`；生造词才查精确匹配。
- 包名：npm `npm view <name>`；PyPI `https://pypi.org/project/<name>/`（404=可用）；crates `https://crates.io/api/v1/crates/<name>`；RubyGems `<name>.json`；GitHub org `https://github.com/<name>`（404=可用）；WP slug `api.wordpress.org/plugins/info/1.2/?action=plugin_information&slug=<name>`；Telegram `https://t.me/<name>`（404=可用）。
- 脚本：`bash scripts/check-availability.sh <name> domain npm github pypi crates rubygems wp telegram`（按需传平台；Windows 用 WSL/Git Bash）。
- **字典词捷径**：常见单词精确 .com 基本被占，别浪费查询。
- 判定：hit 竞品/必须平台不可用 → 弃；强名但仅次要平台缺 → 标记保留并给变通。

## code 模式（"可用性"= 能编译 + 合规范 + 不冲突）
代码里"名字可用"不是查域名，而是：
1. **编译/解析通过**（改名后 build/test 绿）。
2. **lint 通过**（项目 ESLint/ruff/golangci 等；部分 S-I-D 可规则化）。
3. **glossary 命中**（用项目词表里的词；新概念先入词表）。
4. **近名冲突扫描**：同作用域是否有同名异义/近名异义。
5. **机器扫描**：`python scripts/check-code-names.py <path> [--lang auto] [--json|--out f] [--strict]` → 缩写/vague verb/否定式/单字母/同类型大小写冲突/垃圾模块名，分级并给 文件:行号。（脚本只扫声明行，**参数名、复杂签名、近名异义**可能漏检，需配合 glossary 人工核；见脚本文件头「已知局限」。）

改名前影响面：查引用（`grep`/IDE rename）；对外 API/序列化字段改名需评估兼容（别名/迁移）。
