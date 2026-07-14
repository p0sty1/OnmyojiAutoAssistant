# 开发说明

## 1. 兼容目标

项目壳于 2026-07-14 按 MaaFramework 当前 ProjectInterface V2 文档、MaaPracticeBoilerplate 与 MXU README 核对。PI 的数字主版本固定为 `2`。当前配置只使用 MXU 已支持的基础字段：controller、resource、agent、import、task 与 option；没有依赖较新的 setting、hotkey 等扩展。

支持范围：

- Windows；
- Android ADB controller；
- 16:9，短边不低于 720；
- 重点验收 1280×720 与 1920×1080；
- 首版以单个正在运行的模拟器为主，多设备由 MXU 选择。

## 2. 分辨率契约

`interface.json` 中的控制器设置：

```json
{
    "type": "Adb",
    "display_short_side": 720
}
```

因此业务资源只允许使用 1280×720 坐标系：

1. 1280×720 截图保持原尺寸；
2. 1920×1080 截图缩放成 1280×720 后识别；
3. Pipeline 的 ROI、目标点和模板全部按 1280×720 制作；
4. MaaFramework 将动作坐标映射回设备原始画面。

不要在 Pipeline 或 Agent 中再次乘以 `2/3` 或 `1.5`，也不要为 1080p 复制第二套任务。非 16:9、低于 720p、拉伸画面与游戏黑边暂不在首版承诺范围内。

## 3. 设备连接契约

项目只声明一个名为 `Android` 的 `Adb` controller，不保存以下内容：

- 模拟器安装目录；
- `adb.exe` 绝对路径；
- 固定端口或 serial；
- 截图与输入枚举值。

设备枚举交给 MXU 所集成的 MaaToolkit，截图和输入方式由 MaaFramework 探测。项目逻辑不得调用全局 `adb kill-server`。检测不到设备时，应提示用户启动模拟器、开启 ADB 或完成首次授权，而不是扫描全部盘符。

## 4. 稳定接口

任务和 Pipeline/Agent 之间的名称属于内部 API，修改时必须同时更新任务片段和校验：

| 任务 ID | Pipeline 入口 | 可由 PI 覆盖的节点 |
| --- | --- | --- |
| `yys_tower` | `Tower.Entry` | `Tower.Challenge.max_hit`、`Tower.Helper.enabled`、`Tower.Gold.enabled` |
| `yys_realm_raid` | `YYSRealmRaid` | 首版不暴露 UI override；固定策略由 Agent 管理 |

活动爬塔的“运行次数”通过 `Tower.Challenge.max_hit` 控制。Pipeline 必须在超出次数后进入停止节点，并在一次完整结算后才结束，不能用 GUI 睡眠或外部计数猜测。

个人突破的运行终点与卡死保护不是同一个概念。`stuck_start_limit` 与第九格前三次退出规则保持为 Agent 内部策略，首版不映射成通用“运行次数”。

## 5. ProjectInterface 拆分

根 `interface.json` 只负责项目、控制器、资源包与 Agent 声明。任务由 PI 的 `import` 字段按顺序加载：

```text
interface.json
  ├── tasks/tower.json
  └── tasks/realm_raid.json
```

任务 ID 使用稳定英文标识，`label` 使用面向用户的中文。添加第三个普通副本时：

1. 新增一个 Pipeline 文件与稳定入口；
2. 新增一个 `tasks/<module>.json`；
3. 把该片段加入 `interface.json#import`；
4. 运行校验。

不需要修改 ADB、分辨率、MXU 或个人突破 Agent。

## 6. Agent 与发布

PI 使用发布期入口：

```json
{
    "child_exec": "./agent/runtime/onmyoji_auto_assistant_agent.exe"
}
```

源码开发和单元测试可以直接运行 Python，但 MXU 发布包必须先由构建脚本生成该可执行入口。`-RequireRuntime` 会检查它是否已经落入发布目录。不要把开发机上的 Python 绝对路径写进 PI。

## 7. 验收清单

静态检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_project.ps1
```

发布包检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_project.ps1 -RequireRuntime
```

真机/模拟器验收至少覆盖：

- 1280×720 下两任务入口可识别；
- 1920×1080 下使用同一套模板与 ROI；
- 单模拟器启动后 10 秒内可在 MXU 中发现并连接；
- 多设备时不会静默连接错误实例；
- 点击停止后 2 秒内不再产生截图之外的业务动作；
- 活动爬塔 1、5、10 次均精确停止；
- 关闭“自动处理加成/弹窗”后对应节点确实禁用；
- 个人突破九宫格续位、第九格前三次退出及卡死保护符合旧脚本语义；
- 断线不会触发全局 `adb kill-server`。

## 8. 参考

- [ProjectInterface V2 协议](https://maafw.com/docs/3.3-ProjectInterfaceV2/)
- [控制方式说明](https://maafw.com/docs/2.4-ControlMethods/)
- [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate)
- [MXU README](https://github.com/MistEO/MXU)
