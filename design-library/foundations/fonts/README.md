# 预览字体：首次使用时下载

此目录只分发来源清单、许可文本和本文档，**不分发字体二进制**。`*.ttf`、`*.woff` 等字体格式由项目 `.gitignore` 排除。

首次执行 `python tools/design_library.py gallery` 时，工具从[梦源官方固定发布](https://github.com/Pal3love/dream-han-cjk/releases/tag/dream-3.01-sans-2.004-serif-2.002)获取 W8／W12，校验源数据及生成文件的 SHA256，提取 SC 字面后缓存到此目录。后续校验通过即直接复用，不重复联网。具体范围和摘要见 [manifest.json](manifest.json)。

下载使用正向 HTTP Range，只取官方压缩包中两个字重所需的约27.9 MiB数据，无需下载整个约376.5 MiB压缩包。提取过程仅复制字体表并重算文件校验和，不修改字形、字宽或字重。来源固定在3.01，避免无意升级预览效果。

```powershell
# 只查看本地状态，不联网
python tools/design_library.py fonts --status
# 提前下载／修复缓存；已有有效缓存不联网
python tools/design_library.py fonts
# 首次预览自动准备字体
python tools/design_library.py gallery
# 离线预览：缓存不存在时使用系统字体，并在目录中提示
python tools/design_library.py gallery --offline
# 纯静态检查不下载字体；生产检查可要求缓存完整
python tools/design_library.py check
python tools/design_library.py check --require-fonts
```

使用 Python 标准库下载；若环境变量指定 SOCKS 代理，则调用本机 `curl`，不修改系统代理。没有curl时可使用HTTP代理，或按下文离线准备。下载失败、范围不被服务器支持、大小或摘要不符时停止，不留下假成功缓存，也不会覆盖已有文件。

若服务器／代理不支持Range，可从上述官方发布自行下载完整 `DreamHanSans.zip`，然后：

```powershell
python tools/design_library.py fonts --archive 'C:\path\to\DreamHanSans.zip'
```

该方式读取指定成员并校验，不解压其他文件。原有其他版本的压缩包不能冒充此固定版本。缓存存在但摘要不符时，离线预览也会停止，需先修复，避免误用错误字体。字体仍适用 [SIL OFL-1.1](DreamHanSans-OFL.txt)，项目 MIT 许可证不替代字体许可。

这里只准备浏览器预览缓存，不安装系统字体。InDesign 生产需另行核对用户本册字体的安装、命名实例、范围和许可。直接打开组件 `preview.html` 不会运行下载器；缓存缺失时回退系统字体，应先运行上述命令再验证排版。
