# LaunchApp

中文｜English

LaunchApp is a two-part Session View controller for **203 Systems Mystrix Pro** and **Ableton Live 12.4.6**. It contains a standalone MatrixOS 4.0 Python application for Mystrix and an Ableton MIDI Remote Script. The two parts communicate over USB MIDI SysEx and must always be installed as the same release.

LaunchApp 是为 **203 Systems Mystrix Pro** 与 **Ableton Live 12.4.6** 制作的双端 Session View 控制器。它包含一个独立的 MatrixOS 4.0 Python App 和一个 Ableton MIDI Remote Script；两端通过 USB MIDI SysEx 通信，必须始终成套安装同一版本。

**Author / 作者：GZ_Beatz**

## Status / 当前状态

LaunchApp V1 has passed local automated tests and manual acceptance on Ableton Live 12.4.6 with Mystrix Pro hardware. The planned core functions are implemented and no material defects have been found so far. Future work starts from this V1 baseline. This repository never installs itself into Live, User Library, a Live Set, or a device.

LaunchApp V1 已通过本地自动化测试，并已在 Ableton Live 12.4.6 与 Mystrix Pro 真机上完成人工验收。计划中的核心功能均已实现，目前暂未发现明显问题。之后的开发和更新都以 V1 为基线。本仓库不会自动安装、修改 Live、User Library、Live Set 或设备。

## What it does / 功能

- 8×8 Session grid with Track/Scene navigation and Live Session Highlight.
- Track page: recording length, navigation, Arm, Mute, Solo, and immediate Track Stop.
- Scene page: launch a full Live Scene and stop only the active clips in a selected Scene row at the end of the current bar.
- Live-synchronised LED states: Track colours, clip state, recording, queues, BPM, transport state, and a shared musical animation phase.
- Fn gestures: one press switches between Session and Track pages; a double press within 450 ms, with no intervening pad press, opens the Scene page.

- 8×8 Session 网格，支持 Track/Scene 导航及 Live Session Highlight。
- Track 页面：录音长度、导航、Arm、Mute、Solo 和立即停止 Track。
- Scene 页面：触发整条 Live Scene，并在当前小节结束时只停止指定 Scene 行中仍在活动的 Clip。
- 与 Live 同步的灯光：轨道颜色、Clip 状态、录音、队列、BPM、走带状态及统一音乐相位动画。
- Fn 手势：单击在基础页与 Track 页之间切换；450 ms 内双击且中间没有 Pad 操作时进入 Scene 页。

## Repository layout / 目录结构

| Path | English | 中文 |
| --- | --- | --- |
| `PythonApps/Launch/` | Mystrix MatrixOS Python App | Mystrix 的 MatrixOS Python App |
| `RemoteScripts/Launch/` | Ableton Live Remote Script | Ableton Live Remote Script |
| `RemoteScripts/LaunchHandshake/` | Read-only connection diagnostic Script | 只读连接诊断脚本 |
| `Tools/` | Local ZIP packaging tools | 本地 ZIP 打包工具 |
| `tests/launch/` | CPython unit tests and fake-Live tests | CPython 单元测试与模拟 Live 测试 |
| `docs/` | Bilingual product, setup, development and validation docs | 中英对照的产品、安装、开发与验收文档 |

## Start here / 从这里开始

1. Read [Installation Guide / 安装指南](docs/INSTALLATION.md).
2. Read [User Guide / 操作指南](docs/USER_GUIDE.md).
3. Read [Architecture / 架构说明](docs/ARCHITECTURE.md) before changing protocol or Live behaviour.
4. Run the local tests described in [Development Guide / 开发指南](docs/DEVELOPMENT.md).
5. Use [Validation Guide / 验收指南](docs/VALIDATION.md) for Live and Mystrix Pro testing.

## Compatibility / 兼容性

| Component | Required version | 中文 |
| --- | --- | --- |
| Controller | 203 Systems Mystrix Pro | 控制器：203 Systems Mystrix Pro |
| Firmware | MatrixOS 4.0 nightly | 固件：MatrixOS 4.0 nightly |
| DAW | Ableton Live 12.4.6 | 宿主：Ableton Live 12.4.6 |
| Protocol | Launch v7 on both sides | 协议：两端均为 Launch v7 |

English: **V1** is the public product release name. **v7** is the internal two-way SysEx protocol version and remains unchanged to preserve the verified App/Script compatibility.

中文：**V1** 是对外产品发布名称。**v7** 是内部双端 SysEx 协议版本，为保持已经验收的 App/Script 兼容性而不改变。

## Build a local release package / 构建本地发布包

```bash
python3 -m unittest discover -s tests/launch -q
python3 Tools/package_launch.py
python3 Tools/package_live_handshake_check.py
```

The generated files stay under `dist/` and are intentionally not tracked by Git. Installation remains a manual action by the user.

生成文件位于 `dist/`，不会被 Git 跟踪。安装必须由用户手动完成。

## Scope and safety / 范围与安全

LaunchApp is an application project, not a MatrixOS firmware fork. It does not alter MatrixOS core code. Use an isolated Live Set for validation, back up your existing app and Remote Script before replacing them, and stop testing if the controller restarts, MIDI disconnects, an unintended clip stops, or recording content is lost.

LaunchApp 是应用项目，不是 MatrixOS 固件 fork，也不修改 MatrixOS 核心代码。请使用隔离的 Live Set 验收；替换前备份现有 App 和 Remote Script。若设备重启、MIDI 断开、误停 Clip 或录音内容丢失，请停止测试。
