# ok-script

## 无界面、桌面与 Web 模式

自动化核心现已与 Qt 解耦。使用 `ok-script` 可无界面运行，使用
`ok-script[qt]` 启用原有桌面界面，或使用 `ok-script[web]` 启用 FastAPI
浏览器界面；对应命令为 `ok run_task`、`ok gui` 和 `ok web`。详见
[运行时架构](docs/architecture.md)。

[简体中文](README.md) | [English](README_en.md)

说出你想自动化的事。代理通过 MCP 观察 Windows 应用、游戏或安卓设备，编写 Python 任务，在真实目标上运行并修复失败。ok-script 把完成的任务连同桌面 GUI 打包成可分发的 Windows 安装包。打包后的程序在本地独立完成截图、识别和输入，无需代理保持连接，运行时不再消耗 token。

ok-script 支持 Windows 应用和游戏、安卓模拟器及 ADB 设备，提供模板匹配、OCR、目标支持时的后台输入、桌面界面和任务打包。鸣潮的 okww、异环的 oknte、二重螺旋的 okdna、明日方舟：终末地的 okef 等热门自动化项目都基于 ok-script 开发。

[MCP 快速开始](docs/quick_start/README.md) · [编程代理提示词](docs/agent-prompts.md) · [MCP 连接说明（英文）](docs/mcp.md) · [▶ 视频教程（B 站）](https://www.bilibili.com/video/BV1FEss6eEa1/)

## 两句提示词，做出一个扫雷程序

![ok-script 生成的程序运行“高级扫雷直到胜利”任务，几秒内通关高级扫雷](docs/ok_py/minesweeper_demo.gif)

[▶ 视频教程：ok-script MCP 开发 Python 脚本教程（B 站，3 分半）](https://www.bilibili.com/video/BV1FEss6eEa1/)

在 Codex（GPT 6.1 Sol，推理强度中等）里只说了两句话：

1. 在当前目录安装并配置 ok-script，用它来自动化当前打开的扫雷。
2. 用 ok-script 的 MCP 写一个任务，自动玩扫雷高级难度，直到胜利。

代理通过 MCP 截图识别棋盘，写出约束推理和概率选格的任务，在真实的扫雷窗口上反复运行、查看日志、修复问题，并把任务注册进 ok-script 桌面程序。上图就是这个生成的程序：选中任务，点击“运行任务”，不需要代理。

| 指标 | 结果 |
| --- | --- |
| Codex 工作时间 | 约 13 分钟（两次对话） |
| 模型花费 | ChatGPT Plus 每周额度约 2%（约 ¥0.71） |
| 连续运行 10 次 | 10/10 通关高级扫雷，平均 15.7 秒，最快 6 秒 |
| 之后每次运行 | 0 token，不调用模型 |

## 可以这样告诉编程代理

首次安装环境：

> 在当前项目中安装 ok-script 并配置运行环境。先读取 https://raw.githubusercontent.com/ok-oldking/ok-script/master/docs/agent-setup.md ，按照其中的安装技能操作，保留项目现有的依赖约束。

[代理安装指南（英文）](docs/agent-setup.md)提供可添加到应用项目 `AGENTS.md` 的简短指令，让后续安装请求也能找到这些技能，无需先安装包或启动 MCP。

开发自动化任务：

> 连接这个项目的 ok-script MCP 服务，读取开发技能。检查已安装的截图、匹配和输入 API，给出准确签名和源码位置。开发可复用 Python 任务：打开设置、启用“显示详情”、保存并验证结果。每次尝试前恢复并验证起始界面，测试重复运行，代码保存到项目中。使用 ok-script API 和 MCP，不使用 Computer Use 工具。最后给出不依赖代理或大模型调用的准确运行命令。

修复已有任务：

> 连接这个项目的 ok-script MCP 服务，读取 reload-tasks 技能。用 list_tasks 找到出错任务的源码，修改该文件，按任务 ID 重载并等待重载成功。恢复并验证起始界面，重复运行已注册的实现，并给出运行日志和截图中的证据。

## MCP 开发流程

代理用自己的工具编辑文件、读取日志；MCP 让它直接操作正在运行的应用：

1. **学习**：`list_skills` 和 `get_skill` 返回当前安装版本自带的开发、模板、测试和重载流程；代理从已安装包中读取准确的 Python 签名。
2. **观察**：`screenshot` 保存已配置窗口或设备的当前画面。
3. **运行**：`run_task` 在真实目标上执行 Python 任务文件。每次尝试先恢复并验证起始状态，再由 `run()` 执行并断言自动化结果。
4. **检查**：每次尝试写入 `logs/mcp/<run_id>/run.log`、`status.json` 和任务截图。`get_run_status` 报告进度和错误，`stop_task` 用于取消。
5. **修复**：`list_tasks` 返回已注册任务的源码路径；修改后用 `reload_tasks` 在运行中的进程里替换。无法重置时用 `exit_process` 结束运行时。
6. **交付**：在项目配置中注册任务，通过 GUI 或 `python -m ok run_task` 运行，并用 [PyAppify](https://github.com/ok-oldking/pyappify) 打包成 Windows 安装包。

## 特性

- 纯 Python 实现，免费开源，可直接使用 pip 生态中的第三方库
- 同一套任务代码可支持 Windows 客户端、安卓模拟器和 ADB 设备
- 支持 OCR、OpenCV 模板匹配以及 YOLO 等视觉方案
- 基于 COCO 标注管理模板素材，并根据屏幕分辨率自动缩放
- 内置截图、输入、设备控制和可视化调试工具
- 支持自动化测试、GitHub Actions 构建和安装包发布
- 支持多语言国际化和在线增量更新

## 快速安装

ok-script 支持 Python 3.11 及以上版本，推荐使用 Python 3.12。

```powershell
python -m pip install ok-script
```

只安装应用所需的依赖配置。`default` 为无界面模式，Web、Qt、ADB 和 OCR
能力分别按需安装：

```powershell
python -m pip install "ok-script[default]"
python -m pip install "ok-script[qt]"
python -m pip install "ok-script[web]"
python -m pip install "ok-script[adb]"
python -m pip install "ok-script[ocr]"
```

ok-script 不会自动选择 OpenCV。用户必须根据自己的应用选择版本，并且只安装
一个变体：`opencv-python`、`opencv-contrib-python`、`opencv-python-headless`
或 `opencv-contrib-python-headless`。

以无界面模式开发本仓库时，同时安装 `pyproject.toml` 中的 `default` 和 `dev`
依赖组；再根据需要添加 `--group web`、`--group qt`、`--group adb` 或
`--group ocr`：

```powershell
python -m pip install --editable . --group default --group dev
```

如果要创建完整的自动化项目，建议从 [`ok-script-app`](https://github.com/ok-oldking/ok-script-app) 模板开始，而不是直接在本仓库中编写业务脚本。

## 文档

从[文档中心](docs/index.md)选择适合你的阅读路径：

1. [游戏自动化入门](docs/intro_to_automation/README.md)：了解截图、识别、决策和输入的基本原理
2. [快速开始](docs/quick_start/README.md)：从模板仓库创建并运行第一个项目
3. [进阶指南](docs/after_quick_start/README.md)：模板匹配、国际化、测试和发布
4. [API 参考](docs/api_doc/README.md)：`Box`、`BaseTask` 及常用任务 API

想先体验完整工具链，也可以使用基于 ok-script 的按键精灵项目 [`ok-py`](https://github.com/ok-oldking/ok-py)。

## 界面预览

| 任务配置 | 截图与交互 |
| --- | --- |
| ![任务配置界面](docs/ok_py/image_tasks.png) | ![截图与交互界面](docs/ok_py/image_capture.png) |

| 脚本与 API | 模板管理 |
| --- | --- |
| ![脚本与 API 界面](docs/ok_py/image_scripting.png) | ![模板管理界面](docs/ok_py/image_template.png) |

[查看界面与开发工具完整说明](docs/interface.md)，包括模板识别调试浮层。

## 使用 ok-script 的项目

- [鸣潮 · okww](https://github.com/ok-oldking/ok-wuthering-waves)
- [异环 · oknte](https://github.com/BnanZ0/ok-nte)
- [二重螺旋 · okdna](https://github.com/BnanZ0/ok-duet-night-abyss)
- [明日方舟：终末地 · okef](https://github.com/AliceJump/ok-end-field)
- [少女前线 2](https://github.com/ok-oldking/ok-gf2)
- [崩坏：星穹铁道](https://github.com/Shasnow/ok-starrailassistant)
- [星痕共鸣](https://github.com/Sanheiii/ok-star-resonance)
- [二重螺旋](https://github.com/BnanZ0/ok-duet-night-abyss)
- [卡厄思梦境](https://github.com/baoxin1100/ok-kes)
- [阴阳师](https://github.com/YunLiuZ/ok-Onmyoji)
- [白荆回廊](https://github.com/ok-oldking/ok-baijing)（停止维护）

## 开发 ok-script

在本仓库中测试界面改动时，可以用 [main.py](main.py) 中的演示配置直接从源码启动 GUI：

```powershell
.\.venv\Scripts\python.exe main.py
```

它以记事本为目标窗口，无需游戏，并注册了一个演示一次性任务和一个触发任务，让任务、计划任务和模板页面都有内容。设置和日志保存在已被 git 忽略的 `configs/` 和 `logs/` 目录中。需要测试其他选项时，修改 `main.py` 中的 `config` 字典或演示任务即可。

## 社区与发布

- 开发者 QQ 群：938132715
- [Discord](https://discord.gg/vVyCatEBgA)
- [B 站视频教程](https://www.bilibili.com/video/BV1FEss6eEa1/)
- [PyPI](https://pypi.org/project/ok-script/)
- [GitHub](https://github.com/ok-oldking/ok-script)

## 致谢

ok-script 的开发离不开以下开源项目：

- [PyAppify](https://github.com/ok-oldking/pyappify)：用于应用更新和打包。
- [OnnxOCR](https://github.com/ok-oldking/OnnxOCR)：提供支持 Intel NPU 的 OCR，
  支持通过 OpenVINO 或 ONNX Runtime 推理，并使用 PaddleOCR v6 模型。
- [PySide6](https://wiki.qt.io/Qt_for_Python)：提供基于 Qt 的桌面界面绑定。
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)：Qt
  界面使用的 Fluent UI 组件。
- [OpenCV](https://opencv.org/)、[NumPy](https://numpy.org/) 和
  [Pillow](https://python-pillow.org/)：用于图像处理和计算机视觉。
- [FastAPI](https://fastapi.tiangolo.com/)、[Uvicorn](https://www.uvicorn.org/)
  和 [pywebview](https://pywebview.flowrl.com/)：用于 Web 界面支持。
- [adbutils](https://github.com/openatx/adbutils)：用于 Android 设备连接。

上述依赖均受其各自许可证约束，详情请参阅对应项目页面。

## 许可证

本项目采用 [Apache License 2.0 + Commons Clause 及附加条款](LICENSE.txt)。

允许的使用方式：

- 可用于闭源项目或商业项目。
- 可以 fork、本项目改进，并保持 fork 开源且免费。

限制：

- 禁止直接出售本项目，或仅改名、稍作修改后将其作为竞争产品出售或推广。
- 禁止将本项目用于黑客攻击、未授权访问、恶意软件、欺诈或其他违法活动。
- 任何使用 ok-script 的项目，都必须在项目网站、GitHub 或软件本身至少一处提及并链接 [ok-script.com](https://ok-script.com/) 或 [ok-script GitHub](https://github.com/ok-oldking/ok-script)。
- Qt UI 的使用还必须遵守 [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) 的许可证。
