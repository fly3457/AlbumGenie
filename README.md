# AlbumGenie

通过本地 InDesign 和 Nutria MCP，将文案、图片及版式设计制作成可继续编辑的画册，交付 INDD、IDML 和 PDF。HTML/CSS/SVG 可用于组件设计与预览；正文在 InDesign 中保持原生文本及 Story 重排。

AlbumGenie 是一个开源的画册排版工作流与组件工具项目。当前包含排版技能、持久经验、任务模板和组件选型工具；尚无面向任意输入的一键全书排版器。运行原生生产需要本机 InDesign、可用的 Nutria 桥接和实际字体。

| 入口 | 用途 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Agent 的简短工作约定与读取顺序 |
| [项目全局经验](docs/memory/global.md) | 已确认的跨画册设计与生产经验 |
| [记忆与反馈流程](docs/memory/README.md) | 日志、当前画册经验、规则提炼及用户确认 |
| [任务模板](docs/templates/) | 日志、反馈、画册记忆与组件使用记录 |
| [设计组件库](design-library/README.md) | 按内容和容量查找、适配并验证组件 |
| [目录与 Git 边界](docs/repository-layout.md) | 共享源码与本地输入输出的分离方式 |
| [原生排版技能](.agents/skills/albumgenie-indesign-layout/SKILL.md) | 排版实施和检查入口 |
| [InDesign MCP 检查与安装](docs/indesign-mcp-setup.md) | 先验证连接，缺失时安装、构建和配置客户端 |
| [首次使用时准备字体](design-library/foundations/fonts/README.md) | 从固定官方来源下载并校验预览字体，仓库不分发字体二进制 |

组件工具仅依赖 Python 3.9+ 标准库，可在项目外通过完整脚本路径调用：

```powershell
git clone https://github.com/fly3457/AlbumGenie.git
cd AlbumGenie
python tools/design_library.py list
python tools/design_library.py select --category information --query 目录
python tools/design_library.py check
```

新画册将资料放在 `input/<album-id>/`，根据[画册记忆模板](docs/templates/album-memory.md)在 `.local/albums/<album-id>/MEMORY.md` 建立约束；任务日志记在 `.local/任务日志.md`。这些内容及 `output/`、`validation/`、`feedback/` 默认均不进入 Git。可复用脚本应先去除客户数据和固定机器路径，再整理到 `tools/`。

本地保留两个技能：`albumgenie-indesign-layout` 负责原生排版和交付，`moodboard-builder` 在需要时辅助参考分析与方向规划。准备实际排版前先按安装文档检查MCP；仅使用组件工具不需要安装或启动InDesign。

项目原创源码、组件和文档采用 [MIT 许可证](LICENSE)。随附的第三方技能与源片段保留各自许可，按需下载的字体适用其原始许可；见[完整第三方声明](THIRD_PARTY_NOTICES.md)及[组件来源说明](design-library/THIRD_PARTY_NOTICES.md)。
字体二进制不随源码或发布包分发。首次运行组件gallery预览时自动从固定官方来源下载并缓存；后续复用，离线可用`gallery --offline`回退系统字体。检索和静态检查不联网。

当前公开版提供可独立运行的组件选型与静态检查工具、排版技能、规则及模板。Nutria 的本机扩展尚未作为可移植运行时发布，新的机器不能直接一键重建历史画册；运行原生排版前需按[目录与运行时说明](docs/repository-layout.md)配置并验证 InDesign／Nutria。共享组件的浏览器、原生与视觉验证状态以各自元数据为准。

仓库不附带客户资料、历史画册成品或用户参考截图。问题与改进建议可通过 GitHub Issues 提交，请使用去除客户内容的复现材料。
