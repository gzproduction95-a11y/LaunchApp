# Changelog / 更新记录

## V1 — Verified release / 已验收发布版本

English:

- Scene Stop no longer depends on an empty Stop Button Slot.
- Scene Stop captures active Clip identities in one Scene row and stops only still-matching target Tracks at the current bar boundary.
- Recording targets end at the boundary and remain in Live; no delete API is used.
- LED animation now shares one Live-anchored musical phase across Arm, Playing, queued states, Scene Launch, and Scene Stop.
- Protocol v7 carries BPM, four-beat position phase, and transport state in Live-to-device heartbeats.
- Manual acceptance passed on Ableton Live 12.4.6 and Mystrix Pro; planned core functions are implemented, with no material defect found so far.
- V1 is the baseline for all future changes and releases.

中文：

- Scene Stop 不再依赖空的 Stop Button Slot。
- Scene Stop 记录指定 Scene 行内活动 Clip 的身份，并在当前小节结束时只停止仍匹配的目标 Track。
- 正在录音的目标会在边界结束并保留在 Live 中；不会调用删除 API。
- Arm、Playing、各种队列、Scene Launch 与 Scene Stop 的灯光动画共享同一个以 Live 为基准的音乐相位。
- 协议 v7 的 Live→设备心跳包含 BPM、四拍循环位置相位与走带状态。
- 已在 Ableton Live 12.4.6 与 Mystrix Pro 完成人工验收；计划中的核心功能均已实现，目前暂未发现明显问题。
- V1 是之后所有修改和发布的基线。
