# 代码命名 Review 清单（可直接产出 review 意见）

用法：对目标文件/PR 逐项过；输出按 Critical / Major / Minor 分级，附 文件:行号 与建议名。可先跑 `python scripts/check-code-names.py <path>` 自动出草稿，再人工校准语义。

## 一、一致性（先查）
- [ ] 是否沿用周边代码/项目 glossary 的命名与词形？（precedent 优先）
- [ ] 同一概念是否只用同一个词？（无 save/store/put、fetch/retrieve 混用）
- [ ] 有无同名异义 / 近名异义（`db`/`conn`、`clazz`/`clz`、`agentName`/`agentNames`）？

## 二、语义 / 结构
- [ ] 过 S-I-D（Short/Intuitive/Descriptive）？
- [ ] 函数是 A/HC/LC、动词具体、无 vague（process/handle/manage/do/run/data/temp）？
- [ ] split test：一个函数叫得出一个动词？（叫不出＝该拆）
- [ ] 布尔正向、用 is/has/can/should，无否定式？
- [ ] 单复数正确（单值/集合）？
- [ ] 类=名词、方法=动词、Getter 省 get、Predicate is/are？

## 三、词形 / 冗余
- [ ] 无未认可缩写（req/resp/svr/obj/biz…；白名单 config/id/spec/stats/db/regex 除外）？
- [ ] 无 weasel 后缀（Info/Data/Manager/Helper/Util/Base/Item/Processor/Impl/Object/Entity）？
- [ ] 模块名非 utils/helpers/common/shared/lib/core/base？
- [ ] 无语境重复（MenuItem.handleClick 非 handleMenuItemClick）、无冗余类型（userObject→user）？
- [ ] 无 flag 参数？

## 四、领域特殊
- [ ] 时间用 at 后缀+时区；时长/超时带单位（ms/secs）；度量带单位？
- [ ] 测试名 `test_<行为>__<场景>`、祈使句？

## 五、输出模板
```
## 命名 Review — <文件/PR>
### Critical（必改）
- `path:line` `oldName` → 建议 `newName`：<原因，命中哪条规则>
### Major（应改）
- ...
### Minor（建议）
- ...
### 一致性小结
- 项目既有约定：<camel/snake…>；glossary：<…>；本 PR 一致/不一致点：…
```
