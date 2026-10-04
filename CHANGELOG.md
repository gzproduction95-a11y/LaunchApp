# Changelog

This project follows a release-oriented changelog. Version numbers describe the paired device App and Live Remote Script package. The MatrixOS AppInfo version is an internal platform field and is not the LaunchApp release number.

## V2.2.2 — 2026-10-04

V2.2.2 is the first public V2 release. It moves page/action decisions and RGB rendering to the computer-side Live Remote Script while keeping LaunchApp as a standalone Mystrix app.

- Count-in: preserve the queued state for a triggered empty slot while Live transport has not started; advance its pulse from a tempo-based phase during the count-in.
- Page response: reuse the acknowledged color table and send incremental page updates instead of forcing a full table transfer.
- Protocol v11: bounded color-table and mapping updates, acknowledged frames, session identity, and raw input events.
- Device footprint: use a small bootstrap and v11-only display receiver to stay within the observed MicroPython memory constraints.
- Safety: keep Live as the source of track/clip state and retain V1 Live action rules.
- Verification: 187 automated tests passed; user-run Mystrix Pro and Live acceptance reported improved first-recording count-in indication and Fn response, with no obvious issue observed.

V2.2.2 requires the matching device App and Remote Script from one archive. It is not compatible with the V1 protocol-v7 half.

## V1.0.0 — 2026-09-26

- First verified public release for Mystrix Pro and Ableton Live 12.4.6.
- Includes 8×8 Session control, Track and Scene pages, musical LED feedback, and Scene Stop at the current bar boundary.
- Uses protocol v7 and remains available as a rollback release.

# 更新记录

本项目按配套设备 App 与 Live Remote Script 的发布版本记录。MatrixOS AppInfo 中的版本字段是平台内部版本号，不是 LaunchApp 发布版本号。

## V2.2.2 — 2026-10-04

V2.2.2 是首个公开发布的 V2 版本。页面与操作判断、RGB 灯光渲染由电脑端 Ableton Live Remote Script 完成；Mystrix 上仍以独立 LaunchApp 运行。

- 首次录音倒数：即使 Live 走带尚未开始，已触发的空格也保留排队状态；倒数灯光使用按速度推进的动画相位。
- 翻页响应：复用设备已确认的颜色表，发送增量页面更新，不再强制传输整张颜色表。
- 协议 v11：限制颜色表与映射更新规模，确认灯光帧，标记会话身份，并转发原始按键事件。
- 设备内存：使用精简启动入口和仅支持 v11 的灯光接收器，以符合已观察到的 MicroPython 内存限制。
- 安全规则：Live 继续作为轨道和 Clip 状态来源，并保留 V1 Live 操作规则。
- 验证：187 项自动化测试通过；用户在 Mystrix Pro 和 Live 上实测，首次录音倒数灯效与 Fn 响应有所改善，本轮未观察到明显问题。

V2.2.2 必须从同一压缩包安装匹配的设备 App 和 Remote Script；不能与 V1 的 v7 协议组件混装。

## V1.0.0 — 2026-09-26

- 面向 Mystrix Pro 与 Ableton Live 12.4.6 的首个已验收公开版本。
- 包含 8×8 Session 控制、Track 与 Scene 页面、音乐同步灯光和当前小节 Scene Stop。
- 使用协议 v7，可作为回退版本。
