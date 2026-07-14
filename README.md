# Onmyoji Auto Assistant

这是一个基于 MaaFramework ProjectInterface V2 的 Windows 阴阳师自动化项目。首版提供两个相互独立、共享同一套设备连接与资源加载机制的任务：

- `yys_tower`：活动爬塔，由 JSON Pipeline 完成识别、点击、结算循环与安全停止。
- `yys_realm_raid`：个人突破，由 Pipeline 处理常规界面，由 Agent 保存九宫格进度和第九格特殊规则。

项目面向 16:9 安卓画面。`interface.json` 将截图短边统一为 720，因此 1280×720 直接使用标准资源，1920×1080 会缩放到 1280×720 识别，点击坐标由 MaaFramework 映射回设备原始分辨率。

## 直接使用

当前工作区已经装好 MaaFramework v5.12.1、MXU v2.3.0 和独立 Agent。启动模拟器后，双击 `Start Onmyoji Auto Assistant.cmd`（或 `启动助手.cmd`），勾选任务并点击开始即可。每次启动会自动检查 GitHub Release；网络不可用或没有新版本时会直接进入 MXU。首次点击开始时，MXU 会自动扫描 ADB；没有历史设备时会连接扫描结果中的第一台，以后按已保存的设备名重连。

如果同时运行多台模拟器，请第一次先在连接面板选对设备再启动任务。模拟器未开启 ADB、真机尚未完成首次授权或游戏画面不是 16:9 时，程序无法代替系统完成这些前置条件。

## 当前目录

```text
.
├── interface.json                 # MXU / ProjectInterface V2 入口
├── tasks/                         # 拆分的任务与界面选项
├── resource_pack/base/
│   ├── pipeline/                  # MaaFramework Pipeline
│   └── image/                     # 720p 标准模板
├── agent/                         # 个人突破状态 Agent 与构建入口
├── tools/                         # 校验、运行时安装与发布脚本
└── docs/development.md            # 架构、契约与验收说明
```

根目录现有的旧 PNG 和 `adbver.exe` 仅作为迁移基线保留，不是 MaaFramework 运行资源；项目不会执行该旧程序。

## 开发校验

首次从源码准备环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-dev.txt
.\tools\install_runtime.ps1
.\tools\build_agent.ps1
```

`install_runtime.ps1` 固定下载 MaaFramework v5.12.1 与 MXU v2.3.0，并在解压前校验 SHA-256；不会执行全局 `adb kill-server`。

在 Windows PowerShell 中运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_project.ps1
```

校验脚本会检查 PI 必填字段、导入文件、任务/选项引用、Android 720p 控制器约束，以及任务入口和 option override 是否对应到实际 Pipeline 节点。发布目录校验可额外要求运行时文件存在：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_project.ps1 -RequireRuntime
```

VS Code 打开项目后会使用 MaaFramework 官方 schema 校验 `interface.json`、任务片段和 Pipeline。

生成可直接解压使用的 Windows 包：

```powershell
.\tools\build_release.ps1 -Version 0.1.0
```

产物位于 `release/OnmyojiAutoAssistant-win-x64-v0.1.0.zip`。构建会依次执行官方 schema、离线识别、状态机、MaaFramework 资源加载以及打包 Agent 握手测试。

## 使用 MXU

发布包中应包含：

```text
mxu.exe
maafw/MaaFramework.dll
maafw/MaaToolkit.dll
interface.json
resource_pack/base/
agent/runtime/onmyoji_auto_assistant_agent.exe
```

启动模拟器后运行启动脚本或 `mxu.exe`。MXU 根据 `type: "Adb"` 调用 MaaToolkit 发现设备；本项目不硬编码模拟器安装目录、ADB 路径或 serial。多台设备时在 MXU 中选择目标实例，手动 ADB 地址只作为客户端的高级兜底。

任务默认均不勾选，避免连接成功后误运行。活动爬塔可选择运行轮数，并可关闭助战/金币等弹窗处理；个人突破首版固定使用经旧脚本验证的九宫格策略，不把卡死次数伪装成“运行次数”。

## 自动更新

发布包在每次启动时都会检查 GitHub Releases。检测到新版本后，用户可以选择下载并立即安装；更新器在启动 MXU 前校验下载包的 SHA-256、保留上一版本备份，并保留 `config`、`debug` 与 `cache` 目录。网络错误、用户跳过或校验失败均不会阻止启动当前版本。

发布正式版时推送 `vX.Y.Z` 标签。GitHub Actions 会构建完整包、生成 `update.json` 元数据并创建 GitHub Release；打包时会自动写入对应仓库地址，因此终端用户不需要配置更新服务器。

详细开发约定与验收步骤见 [开发文档](docs/development.md)。

## 上游资料

- [MaaFramework ProjectInterface V2](https://maafw.com/docs/3.3-ProjectInterfaceV2/)
- [MaaFramework 快速开始](https://maafw.com/docs/1.1-QuickStarted/)
- [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate)
- [MXU](https://github.com/MistEO/MXU)

本项目不会代替用户完成游戏授权、模拟器 ADB 开关或真机首次调试授权。请仅在你有权控制的设备和账号上使用。
