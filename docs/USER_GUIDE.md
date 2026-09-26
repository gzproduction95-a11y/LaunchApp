# User Guide / 操作指南

## Coordinates / 坐标

English: On every 8×8 page, the top-left pad is the first visible Track and Scene. Columns move left to right through Tracks; rows move top to bottom through Scenes. The starting window is Track 1–8 and Scene 1–8.

中文：所有 8×8 页面中，左上角 Pad 对应当前可见的第一条 Track 和第一条 Scene。列从左到右对应 Track，行从上到下对应 Scene。初始窗口为 Track 1–8、Scene 1–8。

## Fn pages / Fn 页面

| Gesture / 手势 | Result / 结果 |
| --- | --- |
| One short Fn press on Session page / 在基础页单击 Fn | Open Track page / 进入 Track 页 |
| One short Fn press on Track or Scene page / 在 Track 或 Scene 页单击 Fn | Return to Session page / 返回基础页 |
| Second Fn press within 450 ms, with no pad press in between / 450 ms 内第二次点击 Fn，且中间无 Pad 操作 | Open Scene page / 进入 Scene 页 |
| Hold Fn for more than 3 seconds / 长按 Fn 超过 3 秒 | MatrixOS exits the App / MatrixOS 退出 App |

## Session page / 基础页面

| Live state / Live 状态 | Press result / 按下结果 |
| --- | --- |
| Armed Track + empty Slot / 已 Arm Track 的空 Slot | Start Session recording / 开始 Session 录音 |
| Unarmed Track + empty Slot + a playing Clip / 未 Arm Track 的空 Slot且同轨有播放 Clip | Stop the active Clip at the end of the current bar / 在当前小节结束时停止活动 Clip |
| Stopped Clip / 已停止 Clip | Launch using Live's Clip Launch Quantization / 使用 Live 的 Clip Launch Quantization 启动 |
| Recording Clip / 正在录音的 Clip | Queue Record End / 排队结束录音 |
| Playing looping Clip / 正在播放的循环 Clip | Stop at Loop End / 在 Loop End 停止 |
| Playing non-looping Clip / 正在播放的非循环 Clip | Stop at natural Clip End / 在自然 Clip End 停止 |

An unarmed empty Slot press flashes white once as immediate feedback. It does not arm the Track and does not start recording.

未 Arm Track 的空 Slot 按下会短暂白闪一次作为即时反馈。它不会 Arm Track，也不会开始录音。

## Track page / Track 页面

Rows 1–4 are the upper control area. The left four columns select recording length; the right four columns navigate the 8×8 window.

第 1–4 行为上半区控制。左侧四列选择录音长度；右侧四列移动 8×8 窗口。

| Area / 区域 | Action / 功能 |
| --- | --- |
| Rows 1–4, columns 1–4 / 第 1–4 行、第 1–4 列 | Unlimited, 1, 2, 4, 6, 8, 12 or 16 bar recording length / Unlimited、1、2、4、6、8、12 或 16 小节录音长度 |
| Rows 1–4, columns 5–8 / 第 1–4 行、第 5–8 列 | Up, Left, Home, Right, Down navigation / 上、左、Home、右、下导航 |
| Row 5 / 第 5 行 | Toggle Arm / 切换 Arm |
| Row 6 / 第 6 行 | Toggle Mute / 切换 Mute |
| Row 7 / 第 7 行 | Toggle Solo / 切换 Solo |
| Row 8 / 第 8 行 | Immediate Track Stop / 立即停止 Track |

Short navigation presses move one 8-cell window. Holding a direction performs one 8-cell jump. Home returns to Track 1 / Scene 1.

短按导航移动一个 8 格窗口。长按方向键执行一次 8 格跳转。Home 回到 Track 1 / Scene 1。

## Scene page / Scene 页面

The rightmost column launches the whole Live Scene. The column immediately to its left schedules a stop for active Clips in that Scene row at the end of the current bar. Other Scene rows keep playing.

最右列触发整条 Live Scene。其左侧一列会把该 Scene 行中活动的 Clip 排到当前小节结束时停止。其他 Scene 行会继续播放。

Scene Stop includes Tracks beyond the visible 8×8 window. A recording Clip ends at the boundary and remains in Live; LaunchApp does not delete it.

Scene Stop 同样作用于可见 8×8 窗口之外的 Track。正在录音的 Clip 会在边界结束并保留在 Live 中；LaunchApp 不会删除它。

## LED language / 灯光语言

| State / 状态 | LED / 灯光 |
| --- | --- |
| Empty, unarmed / 空 Slot，未 Arm | Dim Track colour / 暗 Track 颜色 |
| Empty, armed / 空 Slot，已 Arm | Breathes between off and dim Track colour every two beats / 每两拍在熄灭与暗 Track 颜色之间呼吸 |
| Stopped Clip / 已停止 Clip | Bright Track colour / 最亮 Track 颜色 |
| Playing Clip / 正在播放 Clip | Track colour breathing every beat / Track 颜色每拍呼吸 |
| Queued launch/stop/end / 等待启动、停止或结束 | Faster two-per-beat breathing / 每拍两次的快速呼吸 |
| Recording / 录音 | Solid red / 红色常亮 |
| Scene Launch / Scene Stop | Green / red with the matching shared phase / 绿色 / 红色，使用对应的统一相位 |

All animation uses one Live-anchored musical phase. Visual updates are capped at 25 fps, so exact sub-frame LED simultaneity is not guaranteed.

全部动画使用同一个以 Live 为基准的音乐相位。视觉刷新最高 25 fps，因此无法保证亚帧级的绝对同时变化。
