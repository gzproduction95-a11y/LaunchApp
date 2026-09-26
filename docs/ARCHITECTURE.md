# Architecture / 架构说明

## System model / 系统模型

```text
Mystrix Pro                                  Ableton Live 12.4.6
MatrixOS Python App                          MIDI Remote Script
input → controller → SysEx request    USB    SysEx request → Live operation
LED ← state mirror ← SysEx state       MIDI   Live state → snapshot/incremental update
```

English: Live is the sole authority for Tracks, Clips, Scenes, tempo, and transport. The device only sends requests and renders a validated state mirror. The device never guesses whether a Live operation succeeded.

中文：Live 是 Track、Clip、Scene、速度和走带状态的唯一真实来源。设备只发送请求并绘制经过验证的状态镜像，不会猜测 Live 操作是否成功。

## Components / 组件

| Component / 组件 | Responsibility / 职责 |
| --- | --- |
| `PythonApps/Launch/main.py` | MatrixOS event loop, USB MIDI input, rendering, full-sync lifecycle / MatrixOS 事件循环、USB MIDI 输入、渲染与完整同步生命周期 |
| `controller.py`, `gestures.py`, `navigation.py` | Fn gestures and local pad-to-action mapping / Fn 手势与本地 Pad 到操作的映射 |
| `state.py`, `phase.py`, `rendering.py` | Device state mirror, shared musical clock and LED colours / 设备状态镜像、统一音乐时钟与 LED 颜色 |
| `RemoteScripts/Launch/__init__.py` | Live Control Surface, Session Ring, command routing, polling and state updates / Live Control Surface、Session Ring、命令路由、轮询和状态更新 |
| `model.py`, `timing.py` | Pure Live model projection and musical-time calculations / 纯 Live 模型投影与音乐时间计算 |
| `protocol.py` on both sides | Versioned SysEx framing / 带版本的 SysEx 帧 |

## Protocol v7 / 协议 v7

Each application frame uses the internal `LA` prefix, protocol version, message type, sequence number, 7-bit payload, and 7-bit checksum. MatrixOS adds/removes its USB SysEx manufacturer header at the transport boundary.

每个应用帧使用内部 `LA` 前缀、协议版本、消息类型、序号、7-bit payload 和 7-bit checksum。MatrixOS 在传输层添加或移除 USB SysEx 厂商头。

| Direction / 方向 | Main messages / 主要消息 |
| --- | --- |
| App → Live / App 到 Live | `HELLO`, `REQUEST_FULL_SYNC`, `GRID_PRESS`, `TRACK_ACTION`, `SCENE_ACTION`, `NAVIGATION`, `REC_LENGTH`, `HEARTBEAT` |
| Live → App / Live 到 App | `HELLO_ACK`, sync transaction frames, Track/Slot/Scene increments, `WINDOW_META`, `REC_LENGTH_STATE`, `HEARTBEAT` |

The Live-to-App `HEARTBEAT` contains BPM × 10, a U14 phase for `current_song_time % 4 beats`, and a transport-running flag. The app extrapolates only this shared musical phase between heartbeats. It freezes the phase while transport is stopped and reanchors it after a position or tempo update.

Live 到 App 的 `HEARTBEAT` 含 BPM × 10、`current_song_time % 4 beats` 的 U14 相位和走带标志。App 只在相邻心跳间外推这一个统一音乐相位；走带停止时冻结，并在位置或速度更新后重新锚定。

## Synchronisation / 同步

English: Full Sync transfers 88 records: 8 Track colours, 8 Track flags, 64 Slot states, and 8 Scene states. The App stages the transaction and only replaces its display state after the complete transaction passes validation. Incremental updates are ignored during an in-flight full sync.

中文：完整同步传送 88 条记录：8 个 Track 颜色、8 个 Track 标志、64 个 Slot 状态和 8 个 Scene 状态。App 会暂存事务，只有完整事务通过验证后才替换显示状态。完整同步进行中会忽略增量更新。

## Scene Stop safety / Scene Stop 安全性

English: Scene Stop captures a Track, Slot, and Clip identity at request time. At each poll it verifies that the original Clip is still valid, still active, and still in the original location. It cancels when transport stops, time position jumps, the time signature changes, or the target is replaced. At the calculated current-bar boundary, it calls `stop_all_clips(False)` only on still-valid target Tracks.

中文：Scene Stop 在请求时记录 Track、Slot 和 Clip 身份。每次轮询都会验证原 Clip 仍有效、仍活动且仍在原位置。走带停止、播放位置跳转、拍号变化或目标被替换时会取消。在计算出的当前小节边界，只对仍有效的目标 Track 调用 `stop_all_clips(False)`。

Live scheduler timing and the real runtime semantics of this call have been manually accepted in Live 12.4.6. The unit tests remain a regression safety net and do not claim sample-accurate timing; any future change to this path requires renewed Live validation.

Live scheduler 时序和该调用在真实运行时的语义已在 Live 12.4.6 中完成人工验收。单元测试仍是回归保护，不宣称采样级精度；今后修改该路径时必须重新进行 Live 验证。
