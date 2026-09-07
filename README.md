# scientific-illustrator-agent

通过 Python → Windows COM → `Illustrator.Application` → `DoJavaScript()` → ExtendScript 创建可编辑科研矢量图。

**两种模式的基础渲染已在 Illustrator 2022 / 26.3.1 实测通过。** 包括 FigureSpec、基础布局、新文档矢量绘制、完整文本块检查、AI 保存和 PNG 预览。参考图示例有 1 个可编辑文本框，PM2.5 流程图有 8 个，多行标签保持一个文本对象。首次渲染曾发生崩溃，简化文字属性设置并由用户重启应用后，两次端到端测试均成功；确切崩溃原因尚未确定。已提供根目录 SKILL.md，可作为 CLI Skill 安装；MCP 和完整 Visual QC 尚未实现。详见 [两种输入模式与完整文本块规则](docs/input_modes.md)。

## Requirements

- Windows 10/11，本机交互式桌面会话。
- Adobe Illustrator 2020（24.x）或 2022（26.x），正常安装并完成首次启动。
- Python 3.9+、pywin32。
- 本机已实测 Illustrator **2022 / 26.3.1** 和 Python **3.9.13**。
- 使用旧版 ExtendScript ES3 / 基础脚本 API；**尚未在 Illustrator 2020 实机验证**。不依赖 Adobe 新版 MCP。

## Installation

在项目根目录的 PowerShell 中运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

若 PowerShell 阻止激活，无需修改系统策略，直接执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe examples/hello_illustrator.py
```

命令行演示自行定位 `src`，不要求 editable install。需要在其他 Python 工程导入时可执行 `python -m pip install -e .`。后续 FigureSpec 使用 Pydantic（兼容 1.x 与 2.x 的 v1 API）；目前不需要 MCP SDK。

## Illustrator COM Test — Milestone 1

```powershell
python examples/hello_illustrator.py --connect-only
```

预期输出（版本以本机为准）：

```text
Illustrator version: 26.3.1
JSX version: 26.3.1
Illustrator connected successfully
```

该模式可启动 Illustrator，但不会创建或修改文档。COM 由系统 ProgID 决定使用哪个版本；多版本共存时必须检查打印的版本。

新增核心文件：`src/illustrator/__init__.py`、`src/illustrator/com_client.py`，以及 `requirements.txt`、`pyproject.toml`、`.gitignore`、`.env.example`。失败时先看下面的 COM 排查说明。

## Drawing Demo — Milestone 2

```powershell
python examples/hello_illustrator.py --debug
```

或指定尚不存在的路径：

```powershell
python examples/hello_illustrator.py --output "outputs/科研绘图测试.ai" --debug
```

预期 Illustrator 行为：

1. 新建 520 × 300 pt RGB 文档。
2. 创建 `SCI_DEMO` 图层。
3. 创建蓝色圆角矩形 `SCI_NODE_hello`。
4. 创建白色可编辑文字 `Scientific Illustrator Agent`，命名 `SCI_TEXT_hello`。
5. 创建 1 pt 蓝色线条 `SCI_EDGE_hello`。
6. 检查图层有 3 个对象，保存到 `outputs/hello_illustrator_<时间戳>.ai`，保留文档打开供检查。

新增文件：`examples/hello_illustrator.py`、`src/illustrator/jsx/hello.jsx`、`tests/test_illustrator_connection.py`、`tests/test_com_client.py`、`logs/.gitkeep`、`outputs/.gitkeep`、本文和 `docs/milestones.md`。

```powershell
# 不启动 Illustrator 的安全边界单元测试
python -m unittest discover -s tests -v

# 真实端到端测试：创建新文档并保存 AI
python tests/test_illustrator_connection.py --debug

# 只验证语法
python -m compileall -q src examples tests
```

普通 unittest discovery 不会启动 Illustrator。真实测试需要显式运行上述 smoke 脚本。失败时检查 `logs/illustrator.log`；`--debug` 记录生成的 JSX，默认 INFO 记录结果、时间和异常。日志可能包含路径或绘图文本，分享前自行检查。

## 两种输入模式的运行与验收

```powershell
# 不启动 Illustrator：校验规范与布局
python examples/render_spec.py examples/specs/reference_demo.json --validate-only
python examples/render_spec.py examples/specs/pm25_workflow.json --validate-only

# 各自新建 Illustrator 文档，保存 AI 和 PNG；默认使用唯一文件名
python examples/render_spec.py examples/specs/reference_demo.json
python examples/render_spec.py examples/specs/pm25_workflow.json
```

已生成的验收文件：`outputs/reference_reconstruction_v3.ai`、`outputs/reference_reconstruction_v3.png`、`outputs/pm25_workflow.ai`、`outputs/pm25_workflow.png`。对应 `.registry.json` 记录从真实文档读取的对象类型与文本框数量，`.jsx.log` 记录绘制步骤。

参考图应出现蓝色圆角矩形、一个白色标题文本框和蓝色横线；流程图应出现 7 个节点、6 个箭头及标题。两者均已查看 PNG，无可见文字溢出或节点重叠。当前 CLI 接收 Agent 编写的 JSON，不自带图像识别或自然语言模型。

## 当前客户端接口与边界

已实现 `connect()`、`disconnect()`、`get_version()`、`get_active_document()`、`create_document()`、`execute_jsx()`、`save_document()`、`health_check()`。

- `disconnect()` 只释放 COM 引用，不退出 Illustrator 或关闭文档。
- 绘制与保存前激活客户端持有的新文档；不会自动接管原有工作文档。
- `execute_jsx()` 只供可信内部开发代码使用，尚未暴露给 Agent。当前不提供任意脚本沙箱。
- JSON 数据以 ASCII Unicode 转义传入 JSX，不在 ExtendScript 内依赖 `JSON.parse`。路径用 `Path.resolve().as_posix()` 再编码。
- 基础坐标使用画板左上角为原点、x 向右、y 向下，映射到文档坐标 `[left + x, top - y]`；执行后恢复坐标系统。
- 保存拒绝覆盖文件，只接受 `.ai`，启用 PDF compatible 数据。未强制向旧版降级保存。
- 失败保留新文档供检查，不自动重试绘图，不强杀 Illustrator。**尚未实现事务回滚、快照或硬超时**。卡在 COM 调用时先检查 Illustrator 对话框。
- COM 引用仅限连接线程使用；MCP 阶段将单独处理 STA 工作线程和串行任务。
- 演示字体为 ArialMT，缺失时使用本机默认字体并记录实际选择。18 pt 是此连接演示的展示字号，后续科研样式再按论文最终尺寸设定。

## Common errors

| 现象 | 检查和处理 |
| --- | --- |
| `Illustrator.Application` 无法 Dispatch | 确認使用本机 Windows Python；先手动打开 Illustrator，完成登录、许可或首次启动提示。 |
| `0x80040154` / `0x800401F3`，COM 未注册 | 检查 Illustrator 是否安装；通过安装程序修复 COM 注册。不要从网上复制未知注册表。 |
| `0x80080005`，启动失败或 Illustrator 未启动 | 先在普通桌面 PowerShell 中运行；关闭启动提示。受限沙箱可能无法启动桌面 COM，本次即出现过；不代表未安装，也不意味着必须以管理员运行。 |
| Illustrator 忙、调用被拒绝 | 关闭模态对话框，等待应用空闲后重新运行；不要在调用过程中手动切换/关闭测试文档。 |
| `DoJavaScript` 不可用/失败 | 检查实际版本、脚本支持是否正常、日志中的 HRESULT 和 JSX 错误；修复 Illustrator 安装；不要假定每个版本都有相同 API。 |
| `0x80010105`，应用发生服务器异常 | 检查 Windows 应用事件日志和输出旁的 `.jsx.log`。若只读 `app.version` 也失败，先保存需要保留的文档并重启 Illustrator，再跑 `--connect-only`；不要反复重试绘图或自动强杀进程。 |
| 版本不符 | COM ProgID 可能绑定到另一安装版本；以 `get_version()` 为准，先处理安装注册问题。 |
| JSX syntax error | JSX 使用旧版 ES3，不能使用 `let`、箭头函数等现代语法；开启 `--debug` 查看真实脚本。 |
| Windows path escaping | CLI 路径用引号包裹；Python 传 `Path`，不要手写拼接 JSX 路径字符串。 |
| 中文乱码 | 日志文件为 UTF-8；PowerShell 显示有问题时可设 `$env:PYTHONIOENCODING = "utf-8"`；图中文字缺字需安装/指定支持中文的字体。演示的中文目录已真实保存成功。 |
| `saveAs` 出错 | 确认目录可写、后缀为 `.ai`、目标不存在，关闭保存/许可对话框；检查日志和 Illustrator 报错。 |
| `exportAs` 出错 | 当前里程碑未实现 exportAs；后续将对 PNG/SVG/PDF 的不同 API 与格式参数分别实测，不能将 PDF 当作普通 exportFile 格式。 |

## 后续路线


验收本阶段后，按用户指定里程碑扩展：客户端完善 → 基础图形工具 → FigureSpec + 布局 → Renderer → PM2.5 workflow → MCP → Scientific Skill → Visual QC。

已增加并实测 `models/`、`layout/`、`renderer/` 的最小链路；后续继续完善对象编辑、科研图元与样式、分支路由、PDF/SVG 导出，再接入 MCP、Skill 和完整 QC。

API 参考入口：[Adobe Illustrator scripting](https://helpx.adobe.com/illustrator/using/scripting.html)。本阶段 API 可用性以本机 Illustrator 26.3.1 的真实调用为验收依据。
