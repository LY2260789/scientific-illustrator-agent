# Milestones 1–2 验收记录

日期：2026-09-07。本项目直接建立在现有空 Git 仓库根目录，未额外嵌套同名目录。

## 环境

- Windows，本机 Python 3.9.13，现有 pywin32 可导入。
- `Illustrator.Application` 已注册至 Adobe Illustrator 2022。
- 实际应用版本和 JSX `app.version` 均返回 `26.3.1`。
- 第一次沙箱内 Dispatch 返回 `0x80080005`。经授权切换到可访问本机桌面的执行环境后，同一 Dispatch + JSX 探针成功。

## 已执行

1. 真实 `win32com.client.Dispatch("Illustrator.Application")`、COM Version、JSX version 探针成功。
2. `python examples/hello_illustrator.py --debug` 退出码 0。
3. 新建 520 × 300 pt RGB 文档，创建 `SCI_DEMO` 图层及圆角矩形、可编辑文字、线条。
4. JSX 回报字体为 `ArialMT`，`SCI_DEMO.pageItems.length` 为 3。
5. `saveAs` 成功，Python 验证输出存在且非空；保存目录包含中文。
6. `python -m unittest discover -s tests -v`：4 项测试通过，覆盖 Unicode 编码、文档所有权保护、非法尺寸及拒绝覆盖。
7. `python -m compileall -q src examples tests`：通过。

本次输出：`outputs/hello_illustrator_20260907_073502_406202.ai`。

## 用户目视验收

在 Illustrator 中检查打开的测试文档：蓝色圆角矩形内有居中的白色文字，下方一条蓝线。用选择工具分别选取三个对象，用文字工具编辑文字；检查图层名称。当前只完成对象数量和保存的自动验收，视觉居中效果由用户检查；未实施 Visual QC。

## 尚未验证

- Illustrator 2020 实机兼容性。
- PDF/SVG/PNG 独立导出、关闭后重新打开的往返检查。
- 多文档并发、MCP 线程调度、事务回滚、超时恢复和中文字体渲染。
- 新建虚拟环境安装（本次利用本机现有 Python/pywin32 验证）。

用户随后提供成功截图，确认 Milestone 1、2，并补充“参考图复刻”“自然语言创作”两种入口及整段文字必须保持一个可编辑对象的要求。

## 后续基础扩展：测试与恢复记录

新增文件：

- `src/models/figure_spec.py`：Pydantic 数据契约，两种模式及完整文本块。
- `src/layout/base.py`：横向／纵向顺序布局、参考图比例换算、边界检查。
- `src/illustrator/jsx_builder.py`、`src/illustrator/jsx/render_scene.jsx`：安全传参和固定渲染模板。
- `src/renderer/illustrator_renderer.py`：新文档渲染、文本完整性读回检查、对象名称映射、AI 保存及 PNG 预览代码。
- `examples/render_spec.py`、`examples/specs/reference_demo.json`、`examples/specs/pm25_workflow.json`：统一 CLI 及两个入口示例。
- `tests/test_figure_spec.py`、`tests/test_layout.py`、`docs/input_modes.md`：测试和两种输入模式说明。

运行及预期行为见 `docs/input_modes.md`。14 项离线测试与语法编译通过；Pydantic 1.10.12 实测，2.x 兼容分支尚未单独安装验证。

真实参考图重建在 07:45:16 触发 Illustrator 26.3.1 的原生异常 `0xc0000005`（Windows Application 事件 1000），COM 回报 `0x80010105`。随后只读 `app.version` 也无法执行，因此不能把本次新增渲染功能标为成功，未生成可交付的新 AI/PNG。

已在代码中移除复用文字属性引用及额外行距／段落对齐设置，增加逐步骤落盘日志和 JSX 错误返回，作为待验证的简化方案；**尚不能确定原生崩溃的具体原因，也不能声称已经修复**。已请用户保存需要保留的文档并重启 Illustrator，之后应先跑连接探针，再使用新的输出路径验证参考图和 PM2.5 多行文本。未强制结束 Illustrator 进程。

### 重启后的实测结果（2026-09-07 07:54–07:55）

用户确认已重启。只读连接测试成功，COM 与 JSX 均返回 `26.3.1`。

执行命令：

```powershell
python examples/hello_illustrator.py --connect-only
python examples/render_spec.py examples/specs/reference_demo.json --output outputs/reference_reconstruction_v3.ai
python examples/render_spec.py examples/specs/pm25_workflow.json --output outputs/pm25_workflow.ai
```

三条命令退出码均为 0。

- 参考复刻：3 个叶对象（矩形、文字、线），1 个 `TextFrame`，AI 与 PNG 保存成功，无字体警告。
- PM2.5：7 个节点、6 条带可编辑三角形箭头的连接，共 27 个叶对象；8 个 `TextFrame`（7 个标签及标题）。输入节点的两行内容经真实 `frame.contents` 比较保持在同一个文本框内。AI 与 PNG 保存成功，无字体警告。
- 已查看两张导出的 PNG：参考图文字居中，流程图节点排列整齐，箭头方向正确，无可见文字溢出或节点重叠。尚未实现自动视觉 QC 模型。
- 简化后的路径在本次两次完整渲染中未复现崩溃；不能据此断言已确定原生崩溃原因或所有绘图情形均稳定。

当前可交付输出为 `outputs/reference_reconstruction_v3.ai` 和 `outputs/pm25_workflow.ai`，及对应 PNG、spec、registry 与步骤日志。命令再次运行应省略 `--output` 或选择新的文件名，因为保存默认禁止覆盖。
