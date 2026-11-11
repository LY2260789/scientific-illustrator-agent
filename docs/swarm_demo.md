# Illustrator 多光标集群演示

鼠标集群作为原技能的可选演示模式，通过 `examples/swarm_draw.py` 调用。原有 FigureSpec、渐进 SVG、直接生成及 GIF 回放仍使用各自入口。

新增入口将 SVG 图形或基础图元场景按空间位置分给 2–30 个彩色演示光标。每轮光标同时移动，随后提交这一轮的真实 Illustrator 矢量对象。基础图元模式中，光标沿对应元素的线条或轮廓移动，直接创建原生路径和文字。最终遮挡顺序由预先建立的空分组保留。

## 开始展示

在此技能目录运行以下命令。输出目录必须使用新名称。

先在桌面打开 Illustrator，再在普通终端运行演示命令。

```powershell
python examples/swarm_draw.py --output-dir outputs/swarm_01 --cursors 12 --duration 30
```

Illustrator 打开空白画板后，程序根据文档视图和原生画布坐标自动对齐，并在准备 3 秒后开始多光标绘图。需要让 Illustrator 位于前台。演示时保持窗口位置、缩放比例和画板位置固定。

录屏可以直接录制 Illustrator 所在屏幕。光标层支持鼠标穿透，切换到其他窗口时隐藏。按 Esc 停止，叠加层关闭后会等待正在执行的 COM 操作返回。

需要手动对齐时添加 `--manual-align`，然后在半透明对齐层上从画板左上角拖到右下角。手动对齐阶段默认在 180 秒后退出。

## 基础图元 COM 绘制

已有 `Artwork` 场景 JSON 时，使用以下入口。

```powershell
python examples/swarm_draw.py --scene-json "D:/artwork/scene.json" --output-dir outputs/native_01 --cursors 12 --duration 30
```

场景支持矩形、圆角矩形、椭圆、路径和可编辑文字。几何数据、文字及绘图函数在启动时一次载入 Illustrator，后续每轮只发送元素编号。结束时统一核对实际对象名称、数量、文字内容及栅格对象数量。

形状上的 `gradient` 字段创建原生线性渐变。渐变起止坐标使用场景坐标，单位为点，纵坐标向下。每条渐变色带作为一个完整路径提交，并核对其原生渐变填充与色标。示例如下。

```json
{
  "gradient": {
    "start": [0, 0],
    "end": [200, 0],
    "stops": [
      {"offset": 0, "color": "#BDD0DF"},
      {"offset": 50, "color": "#FFFFFF"},
      {"offset": 100, "color": "#BDD0DF"}
    ]
  }
}
```

输出中的 `commands.jsx` 可以通过 `Illustrator.Application.DoJavaScriptFile` 执行，在新文档中重建整幅图。Python 入口同时驱动桌面的光标动画。

## 自定义图形和速度

```powershell
python examples/swarm_draw.py --source-svg "D:/artwork/figure.svg" --output-dir outputs/custom_01 --cursors 20 --duration 45 --start-delay 5
```

SVG 顶层图形和分组决定任务粒度。完整图形若只有一个顶层分组，只会有一个光标获得任务。准备展示素材时，把各区域的背景、线条、图标和完整文字块拆成合理的顶层单元，使任务数超过光标数。文字块中的多行仍保持在同一文本对象中。SVG 输入限制沿用 `progressive_svg.py`。

`--duration` 为各轮动画时长总和，实际过程还包含 COM 复制和刷新时间。导入、对齐和最终保存也需要额外时间。实际绘制时间写入 `process.json`。

已知画板屏幕矩形时，可以指定坐标，单位是 Windows 物理像素。

```powershell
python examples/swarm_draw.py --output-dir outputs/aligned_01 --artboard-rect 120 150 1120 620
```

坐标表示屏幕上的左边界、上边界、宽和高。窗口、显示器或缩放变化后需要重新对齐。

## 输出与执行方式

- `swarm.ai` 保存真实、可编辑的 Illustrator 图形和文字。
- `final.png` 是 Illustrator 导出的完整画板预览。
- `process.json` 记录成功、失败或取消状态、每轮对象数量及实际时长。
- `process.log` 保存 COM 调用诊断。
- `prepared.svg` 是带有稳定分组名称的中间文件。
- 基础图元模式保存 `scene.json` 和可执行的 `commands.jsx`。

多光标是同步演示动画。实际对象创建由一个 COM 工作线程分轮执行，每轮统一刷新。界面中的 cursors 数值表示动画光标数量。系统鼠标输入仍由使用者控制。最终 AI 和 PNG 包含原图内容，录屏可以捕获桌面上的光标和进度条。

成功后叠加层会在 3 秒内关闭。失败或中途取消会保留本次创建的部分文档和日志，下一次运行应指定新的输出目录。
