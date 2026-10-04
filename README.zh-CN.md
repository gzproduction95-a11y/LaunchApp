# LaunchApp

**面向 203 Systems Mystrix Pro 的 Ableton Live Session View 控制器。** LaunchApp 在 Mystrix 上保留独立 App 入口，由 Ableton Live 在电脑端负责控制逻辑、界面状态和 RGB 灯光计算。

[English](README.md) · [下载与发布版本](https://github.com/gzproduction95-a11y/LaunchApp/releases) · [报告问题](https://github.com/gzproduction95-a11y/LaunchApp/issues)

## 项目介绍

LaunchApp 由 Mystrix Pro 上独立运行的 MatrixOS Python App 和 Ableton Live Remote Script 组成，通过 USB MIDI 通信。设备转发 Pad 和 Fn 按键；电脑读取 Live 的 Session 状态、判断操作、渲染 8×8 RGB 灯光画面，再把颜色发回 Mystrix。

项目希望保留 V1 熟悉的演奏体验，同时把手势处理、Live 操作判断和灯光计算放到电脑端。

**当前版本：** V2.2.2 · **设备：** 203 Systems Mystrix Pro · **固件：** MatrixOS 4.0 或更新版本 · **宿主：** Ableton Live 12.4.6

V2.2.2 已通过项目的 187 项自动化测试，并完成用户在 Mystrix Pro 与 Live 上的实机验收。用户反馈首次录音的 Arm 空格倒数提示与 Fn 翻页响应有所改善，本轮未观察到明显问题。实际表现仍会受到电脑、Live 工程、USB MIDI 通道、固件版本和设备状态影响。

## 功能

- 8×8 Session 网格，支持 Track 与 Scene 导航。
- 与 Live 同步的 Clip 启动、排队停止、录音和状态反馈。
- Track 页面提供录音长度、Arm、Mute、Solo、导航和立即停止 Track。
- Scene 启动和当前小节 Scene Stop。Scene Stop 会作用于所选 Scene 行，包括当前窗口外的轨道，并保留 Live 中已录制的内容。
- Fn 页面手势：单击切换 Track/Session；无 Pad 操作插入时，在 450 毫秒内双击进入 Scene 页。
- 按 Track 颜色和格子状态显示空格、Arm、播放、排队、录音和 Scene 控件的 RGB 灯光。
- 电脑端渲染界面；协议 v11 提供确认反馈和受限灯光帧更新。

## 工作方式

    Mystrix LaunchApp  -- USB MIDI 按键事件 -->  Ableton Live Remote Script
    Mystrix 灯光       <-- USB MIDI RGB 灯光帧 -- Live 状态与电脑端渲染器

设备不判断页面、不解释 Clip，也不计算动画。Live 是状态来源。设备 App 和 Live 脚本必须来自同一个发布压缩包；V1 使用协议 v7，V2.2.2 使用协议 v11，不能混装。

## 下载与安装

1. 从 [GitHub Releases](https://github.com/gzproduction95-a11y/LaunchApp/releases) 下载 V2.2.2 配套压缩包。
2. 安装前阅读[安装指南](docs/INSTALLATION.zh-CN.md)。
3. 从同一个 ZIP 安装 Mystrix App 与 Ableton Remote Script。
4. 在 Live 中选择 Launch Control Surface，并选择 Mystrix Pro MIDI 输入和输出。
5. 使用隔离的 Live Set 开始测试，并按安装指南完成首次检查。

设备端 App 通过 MatrixOS Python App 的 USB 串口通道安装；MSC 挂载不是本项目支持的安装方式。安装会替换现有 Launch 文件夹；如需回退，请先保留可用版本的副本。

## 文档

- [安装指南](docs/INSTALLATION.zh-CN.md) · [操作指南](docs/USER_GUIDE.zh-CN.md)
- [架构说明](docs/ARCHITECTURE.zh-CN.md) · [开发指南](docs/DEVELOPMENT.zh-CN.md)
- [自动化与实机验收](docs/VALIDATION.zh-CN.md)
- [更新记录](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md) · [项目声明](NOTICE.md) · [许可证](LICENSE.zh-CN.md)

## 兼容性

| 组件 | 当前支持基线 |
| --- | --- |
| 控制器 | 203 Systems Mystrix Pro |
| 固件 | MatrixOS 4.0 或更新版本 |
| 宿主 | Ableton Live 12.4.6 |
| V2 协议 | 设备端与 Remote Script 均为 v11 |

其他 MatrixOS 和 Live 版本可能可用，但本项目没有宣称已对其完成验证。本项目不包含或修改 MatrixOS 固件。

## 参与和支持

欢迎通过 [GitHub Issues](https://github.com/gzproduction95-a11y/LaunchApp/issues) 提交问题或功能建议。请注明 App、固件和 Live 版本、复现步骤，并在移除私人信息后附上相关日志。提交改动前请阅读[贡献指南](CONTRIBUTING.md)。

## 许可证与商标

源代码按 MIT License 发布，详见 [LICENSE](LICENSE)。Mystrix、MatrixOS、Ableton 和 Live 属于各自权利人。LaunchApp 是独立项目，与 203 Systems 或 Ableton AG 无隶属、关联或认可关系。
