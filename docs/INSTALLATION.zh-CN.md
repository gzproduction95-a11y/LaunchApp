# 安装指南

## 需要准备

- 运行 MatrixOS 4.0 或更新版本的 203 Systems Mystrix Pro。
- Ableton Live 12.4.6。
- Mystrix 与电脑之间的 USB MIDI 连接。
- 从 GitHub Releases 下载的 LaunchApp V2.2.2 压缩包。

Mystrix App 和 Live Remote Script 必须从同一个 ZIP 安装。V1 使用协议 v7，V2.2.2 使用协议 v11；混装后两端无法连接。

## 1. 准备工作

1. 退出 Ableton Live。
2. 下载并解压 V2.2.2 ZIP。
3. 如果需要回退，请单独保留 V1 App 和 Remote Script。
4. 确认 Live 当前使用的 Ableton User Library。Remote Scripts 文件夹位于 User Library/Remote Scripts。

压缩包包含两个安装目录：
- Mystrix-SD/MatrixOS/Applications/Launch/
- Ableton-User-Library/Remote Scripts/Launch/

## 2. 安装 Mystrix App

目前已验证的方式是使用 MatrixOS 内置 Python App，通过 USB 串口文件写入入口安装。当前设备环境不支持把 MSC 挂载作为安装方式。

1. 通过 USB 连接 Mystrix，并打开内置 Python App。
2. 使用已验证的串口文件写入入口，将压缩包 Mystrix-SD 目录中的文件写入 rootfs:/MatrixOS/Applications/Launch/。
3. 该目录应包含 AppInfo.json、main.py、main_v2.py、protocol_v2.py、input_events.py 和 display_receiver.py。
4. 从设备读回文件，与压缩包逐项核对；六个文件名和内容都匹配后再启动。
5. 退出 Python，并从 MatrixOS App 菜单打开 Launch。

安装会替换现有 Launch 应用目录中的文件。如需回退，请在其他位置保留 V1 文件。如果串口入口不可用或读回校验不一致，请停止，不要启动。

## 3. 安装 Live Remote Script

1. 将压缩包 Ableton-User-Library/Remote Scripts/ 下的 Launch 文件夹复制到 Live 当前配置的 User Library/Remote Scripts/ 中。
2. 若目标位置已存在 Launch 文件夹，请用本压缩包中的文件夹完整替换；不要把不同版本的文件合并。
3. 启动 Live。
4. 打开 设置/偏好设置 → Link、Tempo 与 MIDI。
5. 在一个 Control Surface 行选择 Launch，并将 Input 和 Output 都设为 Mystrix Pro（port 1）。

## 4. 首次连接检查

1. 打开一个可丢弃或已备份的 Live Set。
2. 在 Mystrix 上打开 Launch。
3. 查看 Live 日志，确认 Launch v11 已连接且初始灯光帧收到确认。
4. 先肉眼确认 8×8 Pad 位置正确，再测试控制。
5. 按下一个确定的空格或停止状态 Clip，确认 Live 只有对应格子响应。
6. 测试 Fn 翻页，并确认设备保持稳定。

如果 App 退出或设备重启、设备断连、错误 Clip 响应，或 Live 持续出现 NACK/超时，请停止测试。

## 回退

退出 Live。从同一 V1 发布包恢复 Mystrix Launch 文件夹和 Live Remote Scripts/Launch 文件夹。重启 Live 并选择 V1 Launch Control Surface。不能把 V1 设备端和 V2 电脑端配在一起。

## 卸载

退出 Live，取消 Launch Control Surface 选择，并通过已验证的设备文件管理方式删除 Live User Library 和 Mystrix Applications 目录中的 Launch 文件夹。不要删除 MatrixOS 的其他应用。
