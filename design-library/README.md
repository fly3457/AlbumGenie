# AlbumGenie 设计组件库

把可复用的设计关系与客户案例分开保存。当前共享索引有28件修订2组件；本机旧库40件完整保留在忽略的v1目录，其中12件用户参考转化组件暂留本地。共享组件用通用SVG占位代替客户照片，保留完整HTML/CSS/SVG及来源许可。

| 层 | 位置 | 内容 |
| --- | --- | --- |
| 共用基础 | [foundations](foundations/) | 字体来源清单、色板、间距、图形与通用图片占位；字体二进制首次使用时下载，不自动成为品牌规范 |
| 用途索引 | [registry.json](registry.json) | 导航、标题、重点元素、信息组织、数据／关系图、照片、整页／跨页七类 |
| 组件本体 | [components](components/) | 按稳定ID分目录，源码、元数据与独立预览 |
| 来源证据 | [sources](sources/) | 固定上游片段、摘要及原始许可；见[来源说明](THIRD_PARTY_NOTICES.md) |
| 本册适配与验证 | `.local/albums/<album-id>/` | 本册文案、色板、字体、几何、裁切、选用理由及验证，不进Git |
| 本地旧库 | `v1/` | 原40件、用户参考、客户照片和历史检查，保留不变且不进Git |

## 选型与实际排版

先确认信息角色与层级、语种、完整字数、条目数、照片主体／比例／质量和本册可用宽度，再检索候选；读取候选的容量、插槽、几何与原生映射边界。组件可选，不为套模板删字、补译或随机更换同级标题。

```powershell
python tools/design_library.py list
python tools/design_library.py select --category photography --items 4 --width-mm 125
python tools/design_library.py select --category information --query 清单 --include-local
python tools/design_library.py select --category diagrams --subtype concept-relation
python tools/design_library.py show P01
python tools/design_library.py show I07 --include-local
python tools/design_library.py gallery
python tools/design_library.py gallery --offline
python tools/design_library.py fonts --status
python tools/design_library.py check
```

命令从项目根运行；也可从其他目录调用脚本完整路径。`--language zh`或`bilingual`筛选已说明的语种，`--native-verified`仅保留明确verified的组件；本次共享修订均未做原生验证，所以该过滤结果为空。未知数量／语种不按已支持返回。`--width-mm`给出适配提示，演示宽度不是可直接套用的容量限制。

`gallery`首次需要时从固定官方来源下载预览字体，校验后缓存，随后在`.local/previews/component-catalog.html`生成预览与源码／元数据入口；加`--include-local`包含本地独有组件。`--offline`不下载，缺少缓存时使用系统字体并提示。字体不在源码或发布包中，具体见[首次字体准备](foundations/fonts/README.md)。`list`／`select`／`show`／`check`不触发下载。

生成物默认不进Git，生成过程不启动浏览器，尚未宣称浏览器交互或视觉检查通过。直接打开选定组件的preview.html不会运行下载器，建议先运行gallery或fonts命令；浏览器限制file资源时，可在本地静态服务下查看。

候选选中后复制到本册工作目录，替换全部插槽与演示样式；按实际宽度重排并看图，再原生重建和验证编辑／IDML及真实跨页。把ID、revision、选型理由、内容来源、字体／色板／裁切变化与四类验收状态记入[本册使用记录模板](../docs/templates/component-usage.json)。容量不适合时选择其他组件或原创版式，不追求使用数量。

字段及入库方法见[组件约定](CONTRACT.md)。新组件来源、可分享性、浏览器检查、Agent视觉、用户认可和原生验证分别记录。本次共享修订不继承原库的浏览器几何／视觉结论；check只做静态资源与摘要检查。
