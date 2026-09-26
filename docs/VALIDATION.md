# Validation Guide / 验收指南

## Evidence levels / 证据等级

| Level / 等级 | Meaning / 含义 |
| --- | --- |
| Local automated / 本地自动化 | CPython tests with fake MatrixOS and Live objects / 使用模拟 MatrixOS 和 Live 对象的 CPython 测试 |
| Simulator / 模拟器 | MystrixSim or MatrixOS simulation result / MystrixSim 或 MatrixOS 模拟结果 |
| Live manual / Live 手测 | User verifies behaviour in an isolated Live 12.4.6 Set / 用户在隔离 Live 12.4.6 Set 中验证 |
| Device manual / 真机手测 | User verifies Mystrix Pro hardware, LEDs, USB MIDI and stability / 用户验证 Mystrix Pro 硬件、灯光、USB MIDI 与稳定性 |

Do not present a lower evidence level as a higher one.

不得将较低等级的证据表述为较高等级。

## Verified manual coverage / 已验证的手动覆盖范围

English: The following areas have been manually accepted with Ableton Live 12.4.6 and Mystrix Pro. Repeat them for a future release whenever the related code changes.

中文：以下范围已经在 Ableton Live 12.4.6 与 Mystrix Pro 上完成人工验收。今后相关代码变化时，应重新执行对应测试。

1. Connection: verify the HELLO/HELLO_ACK handshake, complete initial sync, and two-way state updates.
2. Stability: leave Live and Launch connected for at least two minutes; add several Tracks quickly and watch for device restarts or lost sync.
3. Page behaviour: verify Fn single/double press, navigation, recording length, Track controls, and Scene controls.
4. Session behaviour: verify Clip launch, record end, Loop End Stop, non-loop Clip End Stop, and unarmed empty-Slot current-bar stop.
5. Scene Stop: use a Scene with active Clips on visible and Track 9+ positions, including a Track with no empty Stop Button Slot. Confirm only that row stops at the current bar boundary.
6. Recording: Scene Stop and Track Stop must leave the resulting recorded Clip in Live.
7. Safety: test stop transport, seek, time-signature change, Set switch, Clip replacement, and new Clip launch after a queue request. No old request may stop the new Clip.
8. LEDs: observe Arm Empty, Playing, queued states, Scene Launch and Scene Stop together; change tempo, stop/start transport and seek. They should follow the shared Live phase at their specified rates.

1. 连接：确认 HELLO/HELLO_ACK 握手、完整初始同步和双向状态更新。
2. 稳定性：让 Live 与 Launch 保持连接至少两分钟；快速新建多条 Track，观察是否设备重启或同步丢失。
3. 页面行为：验证 Fn 单击/双击、导航、录音长度、Track 控制和 Scene 控制。
4. Session 行为：验证 Clip 启动、结束录音、Loop End Stop、非循环 Clip End Stop 与未 Arm 空 Slot 的当前小节停止。
5. Scene Stop：使用可见窗口和 Track 9+ 都有活动 Clip 的 Scene，包括没有空 Stop Button Slot 的 Track。确认只有该行在当前小节边界停止。
6. 录音：Scene Stop 和 Track Stop 都必须保留 Live 中生成的录音 Clip。
7. 安全：测试停止走带、seek、拍号变化、切换 Set、替换 Clip 和队列请求后启动新 Clip。旧请求不得停止新 Clip。
8. 灯光：同时观察 Arm Empty、Playing、队列状态、Scene Launch 和 Scene Stop；改变速度、停止/启动走带并 seek。它们应按指定倍率共同跟随 Live 相位。

## Stop conditions / 停止条件

English: For a future regression test, stop immediately and preserve Live Log.txt, Mystrix serial output, version information, and a short reproduction video if the controller restarts, MIDI disconnects, the wrong Clip stops, a recording disappears, or Scene Stop misses its expected boundary by a musically obvious amount.

中文：未来回归测试中，若设备重启、MIDI 断开、误停 Clip、录音消失，或 Scene Stop 在音乐上明显错过预期边界，请立即停止测试，并保留 Live Log.txt、Mystrix 串口日志、版本信息和简短复现视频。
