# Launch V2 link-only diagnostic / V2 仅握手诊断

This is a controlled test for the Mystrix reboot observed on 2026-10-01. It sends only a v9 handshake acknowledgement and a reply to each device heartbeat. It sends **no LED frames** and performs **no Live actions**. The Mystrix Launch App is expected to show black LEDs.

这是针对 2026-10-01 Mystrix 重启现象的单项排查。脚本只回复 V2 握手和设备心跳，**不发送灯光画面**，也**不操作 Live**。Mystrix 上的 Launch 灯光应保持全黑。

1. Keep the V2 device Launch App installed. Close Ableton Live.
2. Extract this ZIP. Copy `Ableton-User-Library/Remote Scripts/LaunchLinkOnly/` into the same `Remote Scripts` location as the existing `Launch/` script. The two folders have different names; do not replace `Launch/`.
3. Open Live with a disposable Set. In **Settings/Preferences → Link, Tempo & MIDI**, select **LaunchLinkOnly** for the Control Surface and **Mystrix Pro (port 1)** for both Input and Output.
4. Open Launch on Mystrix once. Watch for `Launch link-only acknowledged` in Live `Log.txt`; leave it for 30 seconds only if the device stays stable. If the device restarts, stop immediately and report the time.
5. Quit Live after the test. Re-select **Launch** only after a corrected V2 candidate is ready.

1. 保持设备上的 V2 Launch App，关闭 Ableton Live。
2. 解压本包，将 `Ableton-User-Library/Remote Scripts/LaunchLinkOnly/` 复制到现有 `Launch/` 脚本同级目录。文件夹名称不同，不要覆盖 `Launch/`。
3. 用临时 Live Set 启动 Live。在 **设置 → Link、Tempo 与 MIDI** 中将 Control Surface 设为 **LaunchLinkOnly**，Input 和 Output 均设为 **Mystrix Pro（端口 1）**。
4. 在 Mystrix 上只打开一次 Launch。如果设备保持稳定，可等待 30 秒。Live 的 `Log.txt` 应出现 `Launch link-only acknowledged`。如设备再次重启，立即停止并记录时间。
5. 测试结束后退出 Live。等修正后的 V2 候选包准备好，再切回 **Launch**。

A stable result narrows the fault to traffic sent after the acknowledgement. A restart means the fault is earlier, or comes from another Live/USB source. The result alone does not prove a firmware cause.

若设备稳定，问题范围可缩小到握手确认之后的通信；若仍重启，则需检查更早的握手或其他 Live/USB 输入。单次结果不能直接证明固件根因。
