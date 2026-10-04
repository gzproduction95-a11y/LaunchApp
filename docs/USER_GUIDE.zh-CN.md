# 操作指南

## 网格坐标

每个 8×8 页面显示八条 Track 和八个 Scene。左上角 Pad 对应当前可见的第一条 Track、第一行 Scene。列从左到右对应 Track，行从上到下对应 Scene。初始窗口显示 Track 1–8 和 Scene 1–8。

## Fn 页面

| 手势 | 操作结果 |
| --- | --- |
| Session 页短按 Fn | 进入 Track 页 |
| Track 或 Scene 页短按 Fn | 返回 Session 页 |
| 450 毫秒内再次按 Fn，期间没有按 Pad | 进入 Scene 页 |
| Fn 按住超过 3 秒 | MatrixOS 退出当前 App |

## Session 页面

| 格子状态 | 按下后的操作 |
| --- | --- |
| 已 Arm Track 上的空格 | 根据 Live 的倒数/量化设置开始 Session 录音 |
| 未 Arm Track 上的空格，且同轨有其他 Clip 正在播放 | 将活动 Clip 排队到当前小节结束时停止 |
| 已停止的 Clip | 按 Live Clip Launch Quantization 启动 |
| 正在录音的 Clip | 排队结束录音 |
| 正在播放的循环 Clip | 排队到 Loop End 停止 |
| 正在播放的非循环 Clip | 在 Clip 自然结束时停止 |

未 Arm Track 上的空格按下后会短暂白闪，作为操作提示；不会自动 Arm，也不会开始录音。

## Track 页面

第 1–4 行是控制区域。

| 按键区域 | 操作 |
| --- | --- |
| 第 1–4 行、第 1–4 列 | 设置录音长度：Unlimited、1、2、4、6、8、12 或 16 小节 |
| 第 1–4 行、第 5–8 列 | 上、左、Home、右、下导航 |
| 第 5 行 | 切换 Arm |
| 第 6 行 | 切换 Mute |
| 第 7 行 | 切换 Solo |
| 第 8 行 | 立即停止 Track |

短按导航将可见窗口移动八格。按住方向键会执行一次八格跳转。Home 回到 Track 1 / Scene 1。

## Scene 页面

最右侧一列启动整条 Live Scene。其左侧一列会将该 Scene 行中正在活动的 Clip 排到当前小节结束时停止。其他 Scene 行继续播放。

Scene Stop 同样会作用于当前 8×8 窗口以外的 Track。正在录音的 Clip 会在小节边界结束并保留在 Live；LaunchApp 不会删除它。

## 灯光状态

| Live 状态 | 设备灯光 |
| --- | --- |
| 空格、未 Arm | 暗 Track 颜色 |
| 空格、已 Arm | 每两拍在熄灭与暗 Track 颜色之间平滑呼吸 |
| 已停止 Clip | 最亮 Track 颜色 |
| 正在播放 Clip | Track 颜色按每拍一次的速度呼吸 |
| 等待启动/停止/结束 | 较快呼吸，每拍两次 |
| 正在录音 | 节拍上显示红色，反拍显示 Track 颜色 |
| Scene 启动/停止 | 按统一音乐相位显示绿色/红色 |

播放动画跟随 Live 的音乐相位。Live 停止时，已 Arm 空格根据最近一次有效速度使用电脑时钟继续呼吸；播放后重新跟随 Live。渲染目标最高为每秒 25 帧；不能保证所有灯光达到亚帧级同步。

## 使用建议

- Mystrix App 与 Live Remote Script 必须使用同一发布版本。
- Session 网格控制 Live Clip，不会编辑或删除 Clip 内容。
- 首次验收建议使用已备份或可丢弃的 Live Set。
