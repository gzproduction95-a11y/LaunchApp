# Launch V2 paced-frame diagnostic / V2 分包灯光诊断

This controlled test follows a stable result with `LaunchLinkOnly`. It uses the same V2 device Launch App. The Live script sends one v9 handshake acknowledgement immediately, then sends one packet of a single full LED frame per Live scheduler tick. The expected display is **one violet cell** after the frame completes. It performs no Live control actions.

本测试用于接续 `LaunchLinkOnly` 的稳定结果。设备端继续使用同一个 V2 Launch App。Live 脚本立即确认握手，随后每个 Live 调度周期只发送一个灯光数据包。完整画面收到后，设备应显示**一个紫色格子**。脚本不会操作 Live。

1. Close Ableton Live. Keep the V2 device Launch App installed.
2. Extract this ZIP. Copy `Ableton-User-Library/Remote Scripts/LaunchHandshake/` into the same `Remote Scripts` location as `Launch/` and `LaunchLinkOnly/`. These are separate folders.
3. Open Live with a disposable Set. In **Settings/Preferences → Link, Tempo & MIDI**, select **LaunchHandshake** for the Control Surface and **Mystrix Pro (port 1)** for both Input and Output.
4. Open Launch on Mystrix once. A single violet cell should appear after several Live scheduler ticks. Live `Log.txt` should contain `Launch v9 test frame acknowledged status=1`.
5. If Mystrix restarts, stop immediately and report the time. If stable, leave it for 30 seconds and report whether the violet cell remains visible.

1. 关闭 Ableton Live，保持设备上的 V2 Launch App。
2. 解压，将 `Ableton-User-Library/Remote Scripts/LaunchHandshake/` 复制到已有 `Launch/` 和 `LaunchLinkOnly/` 同级的 `Remote Scripts` 目录。三个文件夹互不覆盖。
3. 用临时 Live Set 启动 Live。在 **设置 → Link、Tempo 与 MIDI** 中，将 Control Surface 设为 **LaunchHandshake**，Input 和 Output 都设为 **Mystrix Pro（端口 1）**。
4. 在 Mystrix 上只打开一次 Launch。经过几个 Live 调度周期后，应出现一个紫色格子。Live 的 `Log.txt` 应有 `Launch v9 test frame acknowledged status=1`。
5. 如果设备重启，立即停止并报告时间。如保持稳定，观察 30 秒并报告紫色格子是否持续显示。

This isolates paced LED-frame transfer. A stable result does not yet validate the full V2 renderer, animation speed, or V1 behavior parity.

本测试只验证分包灯光传输。即使稳定，也尚未验证完整 V2 渲染、动画速度或 V1 操作体验一致性。
