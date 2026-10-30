# 来源、许可与共享范围

本目录保留已有来源记录中的四个固定开源提交及完整许可文件：

| 来源 | 固定提交 | 原始许可文件 |
| --- | --- | --- |
| shadcn/ui | `02cad61166c4c20edbc8a3f71bd720eed4c1f49b` | [MIT](sources/shadcn/LICENSE.md) |
| Radix Themes | `1faff10ac26ae17f09944d418c6949b93fc6b566` | [MIT](sources/radix/LICENSE) |
| Mantine | 以 [manifest](sources/manifest.json) 中固定提交为准 | [MIT](sources/mantine/LICENSE) |
| daisyUI | 以 [manifest](sources/manifest.json) 中固定提交为准 | [MIT](sources/daisyui/LICENSE) |

源片段、提交、原始URL与SHA256见 [sources/manifest.json](sources/manifest.json)，共享组件记录实际参考的来源。本次按原已保存文件核验摘要，没有重新获取上游或把MIT扩展到其他素材。

预览沿用梦源SC W8／W12，但不分发字体二进制。首次预览时从固定官方版本下载，按[来源清单](foundations/fonts/manifest.json)验证后缓存；仅随源码保留 [OFL 与版权声明](foundations/fonts/DreamHanSans-OFL.txt)。[字体准备说明](foundations/fonts/README.md)包含离线和手动准备方法；实际排版仍按本册确认的字体与许可。

共享示例图片为本次编写的通用 SVG 占位，未包含客户照片；示例文案、数量和RGB配色不代表真实客户数据或印厂批准值。旧库的原图、用户截图、预览截图、检查日志、机器路径和复现资料均留在忽略的 `v1/`。

项目原创源码和组件采用根目录 [MIT 许可证](../LICENSE)；第三方源片段和字体仍保留上述原始许可，完整范围见[项目第三方声明](../THIRD_PARTY_NOTICES.md)。来自用户参考的12件组件不因已被改写就默认纳入公开分发，后续确认范围后再处理。
