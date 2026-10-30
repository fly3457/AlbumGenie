# Windows / Nutria 连接与恢复

本地实际安装与补丁状态先发现。当前工程可有 `tools/nutria-mcp/` 独立工作区，它默认不进入共享Git；批量 album_* 接口是本地扩展，不保证干净的上游版本具备。共享边界见[目录说明](../../../../docs/repository-layout.md)。

## 接入

- 首次原生生产或连接异常时，先按[MCP检查与安装](../../../../docs/indesign-mcp-setup.md)识别当前会话是否有工具且只读调用成功；没有工具不直接重装，先区分客户端注册与本地运行时状态。
- 优先发现已连接的Nutria工具及当前schema；注册过服务不等于本会话已热加载。必要时使用已核实的本地MCP stdio客户端，仍走同一条文档操作路线。
- 本地基线采用stdio＋COM，环境参数常为 `COM_BRIDGE_ENABLED=true`、`HTTP_BRIDGE_ENABLED=false`、`LOG_LEVEL=error`，具体以当前配置为准。TEMP／TMP与调用日志使用本次独立工作目录。
- 先查实际InDesign版本、文档、字体INSTALLED、PDF预设和ICC，Node／Python路径在新机重新发现。修改TypeScript后构建并确认运行dist，保留锁文件及本地补丁，不重置运行时。

## 桥接必须保留的行为

| 部分 | 关键行为 |
| --- | --- |
| JSX读取／COM返回 | ADODB.Stream以UTF-8读脚本；结果和错误的非ASCII有可靠编码与解码，空返回输出null |
| JSON序列化 | 先反斜杠、再引号与C0控制符；正确处理tab字体名、中文路径、字面反斜杠u与换行 |
| 持久引擎 | 修补序列化器时更新运行中的版本，不能只改磁盘源码 |
| 交互模式 | 使用 `UserInteractionLevels.NEVER_INTERACT` 符号枚举，不照抄不明数字 |
| 写入接口 | 校验token＋完整路径、限定页／对象范围；完整Story操作；PDF使用实际预设对象 |

桥接变更按范围回归中文文字／文件名、反斜杠路径、tab、控制字符、字面转义、空结果和错误；再在自有文档小样验证。不能用新客户文件做破坏性测试。

## 批量接口边界

从实际schema确认 `album_environment`、`album_buildPage`、`album_inspectPage`、`album_documentAudit`、续排、换图与导出的可用参数。历史实现存在页数／对象数／样式数、路径白名单和固定出血限制，不直接沿用为项目规格。

`album_buildPage(replace:true)`移除整页，须保护当前现场并校验expectedPath；不同工具的bounds可能分别使用页内与跨页坐标。实际首基线属性为 `minimumFirstBaselineOffset`。某些换图接口会重做fill，原稿需要contain时另行适配并检查。绝对路径、schema和调用后的实际结果都须核对。

## 超时与恢复

1. 停止依赖写入。关闭stdio、终止cscript或MCP超时不等于InDesign DoScript取消，先检查上一次是否完成，避免重复对象。
2. 读取全部打开文档的name／saved／modified／path。常规调用被模态阻塞时优先使用已验证的只读恢复诊断；不能把连接失败直接解释成应用未运行。
3. 有用户未保存或归属不明文档时保留现场，继续独立工作。需要重启或改变这些文档时核实当前授权与实际状态，不以旧任务许可代替本次判断。
4. 恢复后读取检查点及实际文档、文件与对象，不由文件存在或旧token推断完成。缺图／移位测试只处理自有复制资源，路径确认在本次目录内，并用finally恢复。

## 原生读取与串联细节

- 泛型 `pageItems[j]` 先 `getElements()[0]` 解析具体类，再按constructor判断，否则可能漏TextFrame；快照先断言页数和对象数，空集合不得判通过。
- 插入串联框后先读回前后关系，InDesign可能已自动接回后续框；重复赋同一个next可能导致对象无效。
- 合并Story后按原语义字符边界修复各框分配，再收紧高度；用有意义的几何容差比较浮点值，文字、范围格式与顺序精确核对。
- Paragraph.textStyleRanges可能跨段，用段落插入点索引裁切范围再取文字／属性；检查字体、tracking、字宽、noBreak及可变轴，不只读首字符。
- 大文档按明确页批次读取并去重Story，记录每批完成状态；只读调用超时同样先查状态，不能和另一个原生调用并发。
