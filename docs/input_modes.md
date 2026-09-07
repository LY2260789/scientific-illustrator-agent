# 两个入口，一个可编辑绘图引擎

## 参考图复刻

Agent 查看用户提供的参考图，识别形状、文本块、箭头及相对关系，记录不确定之处，然后生成 `mode: reconstruct` 的 FigureSpec。

位置与尺寸采用相对于整个画布的 0–1 比例，由 Python 换算为 pt；字体大小和线宽仍为最终输出的 pt。第一版支持矩形、圆角矩形、椭圆、独立文本、折线及三角形箭头。照片、复杂插画、曲线、纹理和富文本公式尚未支持；不能把整张图片嵌入 AI 文件后声称已完成可编辑重建。

**文字完整性是默认要求：**

- 原图的一段标题、段落或标签，映射为一个 `NodeSpec.label`，最终只有一个 `TextFrame`。
- 多行内容使用字符串内部换行，不能拆成每行一个 NodeSpec，更不能按字生成文本框。
- 参考模式保持识别到的原始换行，关闭自动折行；单个文本块统一字体、字号和颜色。
- 不对文字创建轮廓，不将文字栅格化。文字与背景可以编组，但编组不能代替单一文本框。
- 仅将原图中独立的标签分为不同对象。识别不清的文字记录疑点，不擅自补写科研结论。
- 当前为一个可编辑的点文本对象，支持内部换行；尚非可拖动文本区域后自动重排的 area text。
- 当前统一左对齐多行内容，再把整个文字对象置于节点中央；混合字体、上下标、逐段对齐和段落重排留待后续。

渲染器会读回 Illustrator 的 `textFrames`，逐一核对名称、完整内容和数量。参考图文字块数量应与生成的文本框数量一致。

示例：

```json
{
  "id": "method_description",
  "shape": "text",
  "label": "Data preprocessing\nQuality control and aggregation",
  "position": {"x": 0.1, "y": 0.2},
  "width": 0.8,
  "height": 0.2
}
```

以上是一个节点、一个文本对象、两行文字。

## 自然语言创作

Agent 从用户的想法中提取核心概念、数据流与因果关系，写成 `mode: create` 的 FigureSpec。输入只含语义节点、连接、样式及布局选择，Python 计算具体坐标。

第一版自动布局仅支持按 nodes 顺序的横向／纵向流程，连接限相邻节点。复杂分支、环路和跳跃连接明确报错，防止画出穿过节点的错误线路。机制图需要后续补齐路由与科学图元。

同一节点即使自动折成多行，也保持一个完整可编辑文本框。

## 当前入口与未来 MCP

```text
参考图 ── Agent 视觉理解 ── reconstruct FigureSpec ─┐
                                                  ├─ Python layout → JSX → Illustrator
自然语言 ── Agent 语义理解 ── create FigureSpec ────┘
```

当前 `examples/render_spec.py` 是可供 Agent 调用的 CLI，**不会自行调用模型来识图或解析自然语言**。两个示例 JSON 是本次由 Agent 根据用户输入编写的。未来 Skill 负责理解／设计规则，MCP 封装相同的 `render_figure_spec()`，无需重写绘图引擎。

运行：

```powershell
python -m pip install -r requirements.txt
python examples/render_spec.py examples/specs/reference_demo.json --validate-only
python examples/render_spec.py examples/specs/pm25_workflow.json --validate-only
python examples/render_spec.py examples/specs/reference_demo.json
python examples/render_spec.py examples/specs/pm25_workflow.json
python -m unittest discover -s tests -v
```

预期每次创建新文档，生成 AI、PNG、输入 spec、对象 registry 和 JSX 步骤日志。输出使用唯一文件名；任何目标已存在就拒绝覆盖。报错时检查 `logs/illustrator.log` 及输出旁的 `.jsx.log`。宿主崩溃不是 JSX try/catch 可以回滚的，必须先保存需要保留的文档并恢复 Illustrator，再重新运行到新的路径。

当前对象 registry 是从实际文档读回并保存的名称映射；尚未提供跨会话的对象修改接口。
