# InDesign MCP：使用前检查与安装

组件检索、文档维护和经验整理不需要启动 InDesign。准备实际原生排版时，先确认 MCP 已在当前会话可用；不能因工具目录或客户端配置存在，就认为已经连通。本文安装的是 Nutria MCP 服务，Adobe InDesign 需在用户本机另行安装和授权。

## 先检查，按结果处理

| 结果 | 下一步 |
| --- | --- |
| 当前会话有 InDesign 工具，且只读调用成功 | 使用现有连接；不重复安装 |
| 工具存在，但只读调用报错／超时 | 查看连接、InDesign进程、客户端日志和上次调用状态；保留现场，不盲重试或重装 |
| 当前会话没有工具，本地运行时已构建 | 检查客户端注册与环境变量，按客户端方式刷新工具或重新连接；不重复克隆 |
| 本地有源码但缺依赖／dist | 先核实是否用户维护的版本及本地修改，再决定补依赖／构建；不覆盖旧目录 |
| 本地确实没有服务 | 按下文安装到独立目录，再注册与验证 |

Agent 先发现当前可调用的工具和 schema，优先使用 `document_listOpen` 等只读工具测试。没有打开文档时成功返回空数组也可以证明此调用响应；不通过创建、保存或关闭客户文档检查连通性。COM 操作串行；超时后先核实实际状态，再恢复。

Windows 的本地文件检查：

```powershell
powershell -NoProfile -File .\tools\check_indesign_mcp.ps1
# 如客户端使用了其他安装位置，显式指定该目录：
powershell -NoProfile -File .\tools\check_indesign_mcp.ps1 -RuntimePath 'C:\path\to\nutria-mcp'
```

脚本只读检查 Node、npm／Git、服务源码、依赖、dist 和 InDesign 进程／通用 COM 注册，不安装、不启动应用、不修改客户端配置。默认查本项目 `.local/runtime/nutria-mcp/` 与历史 `tools/nutria-mcp/`；它不是全盘安装扫描，也不能替代当前客户端的工具发现。退出码0只表示本地文件条件满足，实时桥接仍需只读 MCP 调用；2表示需要处理本地条件。

## 缺失时安装 Windows COM 版本

本项目已核对的上游基线为 Nutria `1.4.2`，提交 `62de33b7806892db4bf1fdd242ec86e8048787d5`。这是可追溯的安装基线，不表示最新版本，也不包含 AlbumGenie 私有历史工作区的补丁。安装依据为该提交的[上游 README](https://github.com/nutriandrea/adobe-indesign-mcp/blob/62de33b7806892db4bf1fdd242ec86e8048787d5/README.md)、[Windows 说明](https://github.com/nutriandrea/adobe-indesign-mcp/blob/62de33b7806892db4bf1fdd242ec86e8048787d5/WINDOWS.md)和[package.json](https://github.com/nutriandrea/adobe-indesign-mcp/blob/62de33b7806892db4bf1fdd242ec86e8048787d5/package.json)。

先准备 Git、满足基线要求的 Node.js 18+／npm，以及本机 InDesign。Node 选择仍在维护的版本。下面从项目根目录执行；原目录已存在时立即停止，避免覆盖本机修补：

```powershell
$albumRoot = (Get-Location).Path
$runtime = Join-Path $albumRoot '.local\runtime\nutria-mcp'
if (Test-Path -LiteralPath $runtime) { throw 'Directory exists; inspect the existing runtime before installing.' }
New-Item -ItemType Directory -Path (Split-Path -Parent $runtime) -Force | Out-Null
git clone https://github.com/nutriandrea/adobe-indesign-mcp.git $runtime
if ($LASTEXITCODE -ne 0) { throw 'Clone failed; resolve the network or Git error first.' }
git -C $runtime checkout --detach 62de33b7806892db4bf1fdd242ec86e8048787d5
if ($LASTEXITCODE -ne 0) { throw 'Could not check out the pinned revision.' }
Push-Location $runtime
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
} finally {
    Pop-Location
}
powershell -NoProfile -File .\tools\check_indesign_mcp.ps1 -RuntimePath $runtime
```

运行时、node_modules 和安装日志都留在忽略的 `.local/`，不提交到 AlbumGenie。安装失败时保留错误和现场，不使用 `git reset --hard` 或删除已有目录恢复。本安装路线是源码克隆／构建，不依赖未经核实的 `npx` 或 npm 全局包名。

Windows COM 连接不需要 UXP 插件；由 MCP 客户端启动服务时设置 `COM_BRIDGE_ENABLED=true`，并先打开本机 InDesign。UXP 或 macOS 路线按上游说明配置，本项目没有宣称完成同等验证。

## 注册到 Codex 或其他客户端

先查看已有 MCP 配置，避免覆盖同名服务器。Codex CLI 已安装时可按以下示例注册；`$runtime` 必须指向上一步的实际绝对路径：

```powershell
codex mcp list
codex mcp add nutria-indesign --env COM_BRIDGE_ENABLED=true --env HTTP_BRIDGE_ENABLED=false --env LOG_LEVEL=error -- node (Join-Path $runtime 'dist/index.js')
codex mcp list
```

也可按客户端要求配置 stdio。Codex 的 `config.toml` 示例（路径需替换，不能原样照抄）：

```toml
[mcp_servers.nutria-indesign]
command = "node"
args = ["C:/path/to/AlbumGenie/.local/runtime/nutria-mcp/dist/index.js"]
startup_timeout_sec = 60
tool_timeout_sec = 120

[mcp_servers.nutria-indesign.env]
COM_BRIDGE_ENABLED = "true"
HTTP_BRIDGE_ENABLED = "false"
LOG_LEVEL = "error"
```

配置字段及CLI语法已对照 [OpenAI Docs：MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)及本机 `codex mcp add --help` 核对。只记录了配置不证明当前会话已经加载；按所用客户端重新连接或刷新后，再发现工具。stdio 服务交给客户端管理，不同时手动启动重复服务。不要为重连强制结束 InDesign 或关闭未保存文档。

## 连接成功后仍要检查能力

1. 在当前客户端发现工具 schema，调用只读 `document_listOpen`，记录成功或实际错误。仅本地脚本返回0不够。
2. 查询本机实际版本、字体、预设和打开文档归属；生产前保护用户现场。
3. 区分上游基础工具和 AlbumGenie 扩展。`album_environment`、`album_buildPage` 等 `album_*` 是历史本地扩展；干净上游基线缺少它们是已知边界，不能通过重复安装解决。
4. 若本次制作依赖这些扩展，先取得可移植实现或适配已有基础工具，在自有代表页验证后再生产。不把“上游安装成功”写成“旧画册生产脚本可以直接运行”。首个公开版尚未发布这套本地扩展。
5. 中文读写、原生重排、图片、续排与 IDML 往返按[排版技能](../.agents/skills/albumgenie-indesign-layout/SKILL.md)验证；技术连通不等于全部生产能力通过。

## 网络与常见故障

- 克隆或 npm 连接国际资源失败时，先检查网络和用户当前代理约定。本机采用 Clash Verge／Anycast 时先确认两者运行且健康，再按本机约定使用 Anycast SOCKS5 1080；工具明确要求HTTP才使用本机 mixed 端口。不要把某台机器的代理设为所有人的强制配置。
- `node` 找不到：检查客户端进程的PATH，必要时在本机配置中使用已核实的Node绝对路径。
- 找不到dist：区分源码未构建与客户端路径写错；不要重复下载整个仓库。
- MCP已注册但本会话没有工具：重新连接或刷新客户端，再查看启动日志，不据此认定服务未安装。
- 只读调用卡住：保留上次调用状态，检查弹窗与桥接，按[恢复说明](../.agents/skills/albumgenie-indesign-layout/references/windows-nutria.md)处理，不盲重试。
