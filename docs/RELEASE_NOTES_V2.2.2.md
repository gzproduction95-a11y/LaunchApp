# LaunchApp V2.2.2

V2.2.2 is the first public release of the host-rendered V2 architecture for Mystrix Pro and Ableton Live 12.4.6.

## Highlights

- Keep LaunchApp as a standalone MatrixOS app on Mystrix.
- Move Fn/page gestures, Live actions, state interpretation, and RGB animation rendering to the Live Remote Script on the computer.
- Use SysEx protocol v11 for raw inputs, sessions, bounded color-table updates, and acknowledged display frames.
- Improve the first armed-empty-slot count-in feedback while Live transport is stopped.
- Send incremental page changes against the acknowledged device color table.
- Preserve V1 musical actions and the user-facing control layout.

## Verification

The release worktree passes 187 automated tests. The user installed and tested the matched device/Live package on Mystrix Pro and Live 12.4.6. The latest reported round showed improved count-in indication and Fn page response with no obvious issue observed.

These observations describe that test setup only. They do not guarantee identical timing on every computer, firmware build, Live Set, or USB MIDI setup.

## Installation

Download LaunchApp-V2.2.2.zip and follow docs/INSTALLATION.md. Install both halves from this archive. Do not mix protocol-v7 V1 files with protocol-v11 V2.2.2 files.

---

# LaunchApp V2.2.2（简体中文）

V2.2.2 是面向 Mystrix Pro 和 Ableton Live 12.4.6 的首个公开版本，采用由电脑端渲染界面的 V2 架构。

## 更新内容

- LaunchApp 仍作为独立的 MatrixOS 应用运行在 Mystrix 上。
- Fn/页面手势、Live 操作、状态解析和 RGB 灯光动画渲染均由电脑端的 Live Remote Script 处理。
- 使用 SysEx v11 协议传输原始按键输入、会话状态、分批灯光表更新和带确认的显示帧。
- 改进了 Live 传输停止时，已 Arm 轨道上的首个空 Clip 槽位的录制倒计时灯光反馈。
- 页面切换时基于设备已确认的灯光表发送增量更新。
- 保留 V1 的音乐操作方式和用户可见的控制布局。

## 验证情况

发布工作区通过了 187 项自动化测试。用户已在 Mystrix Pro 和 Ableton Live 12.4.6 上安装并测试配套的设备端与 Live 端程序。最近一轮实机反馈显示，录制倒计时提示和 Fn 页面响应均有所改善，未观察到明显问题。

以上结果仅适用于该次测试所用的设备和软件环境，不保证所有电脑、固件版本、Live Set 或 USB MIDI 配置下的表现完全相同。

## 安装

下载 LaunchApp-V2.2.2.zip，并按照 docs/INSTALLATION.md 中的说明操作。请从同一个压缩包安装设备端和电脑端两部分。不要混用 protocol-v7 的 V1 文件与 protocol-v11 的 V2.2.2 文件。
