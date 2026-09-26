# Installation Guide / 安装指南

## Before you begin / 开始前

English:

- Use Mystrix Pro with MatrixOS 4.0 nightly and Ableton Live 12.4.6.
- Back up your existing `MatrixOS/Applications/Launch/` folder on the Micro SD card and any existing Live `Remote Scripts/Launch/` folder.
- Use an isolated Live Set. Do not begin with an important project or performance Set.
- The Mystrix App and the Live Remote Script must come from the same release archive. v7 cannot communicate with v6.

中文：

- 使用 Mystrix Pro、MatrixOS 4.0 nightly 与 Ableton Live 12.4.6。
- 备份 Micro SD 卡上的 `MatrixOS/Applications/Launch/`，以及 Live 中已有的 `Remote Scripts/Launch/` 文件夹。
- 使用隔离的 Live Set，不要从重要工程或演出 Set 开始。
- Mystrix App 与 Live Remote Script 必须来自同一发布压缩包。v7 不能与 v6 通信。

## Create the archives / 创建压缩包

From the repository root / 在仓库根目录运行：

```bash
python3 -m unittest discover -s tests/launch -q
python3 Tools/package_launch.py
python3 Tools/package_live_handshake_check.py
```

English: The main V1 archive is `dist/LaunchApp-V1.zip`. The optional diagnostic archive is `dist/LaunchApp-handshake-check.zip`.

中文：V1 主发布包为 `dist/LaunchApp-V1.zip`。可选的诊断包为 `dist/LaunchApp-handshake-check.zip`。

## Install the Mystrix App / 安装 Mystrix App

1. Extract the main archive.
2. Copy its `Mystrix-SD/MatrixOS/Applications/Launch/` folder to the same path on the Mystrix Micro SD card.
3. Safely eject the card, return it to Mystrix, then start Launch from the device application list.

1. 解压主发布包。
2. 将其中的 `Mystrix-SD/MatrixOS/Applications/Launch/` 复制到 Mystrix Micro SD 卡的同一路径。
3. 安全推出卡，装回 Mystrix，并从设备应用列表启动 Launch。

Do not format the card or overwrite unrelated MatrixOS folders.

不要格式化卡，也不要覆盖无关的 MatrixOS 文件夹。

## Install the Live Remote Script / 安装 Live Remote Script

1. Close Ableton Live.
2. Copy `Ableton-User-Library/Remote Scripts/Launch/` from the same archive to the `Remote Scripts` folder used by your Ableton User Library.
3. Start Live, open **Settings / Preferences → Link, Tempo & MIDI**.
4. In one Control Surface row, select **Launch**. Set both Input and Output to **Mystrix Pro (port 1)**.
5. Keep Track, Sync, and Remote options aligned with your existing MIDI workflow; the Control Surface row is the required connection for LaunchApp.

1. 关闭 Ableton Live。
2. 从同一压缩包中复制 `Ableton-User-Library/Remote Scripts/Launch/` 到 Ableton User Library 使用的 `Remote Scripts` 文件夹。
3. 启动 Live，打开 **设置 / 偏好设置 → Link、Tempo 与 MIDI**。
4. 在一个 Control Surface 行选择 **Launch**，Input 和 Output 都设为 **Mystrix Pro（端口 1）**。
5. Track、Sync 与 Remote 保持你既有 MIDI 工作流需要的状态；Control Surface 行是 LaunchApp 必需的连接。

## First connection check / 首次连接检查

English: Start Launch on Mystrix, then start Live. The device should log `HELLO_ACK received`, followed by `SYNC_BEGIN` and `SYNC_END ... complete=True`. Live should log `Launch Remote Script initialized` and `Launch received HELLO`.

中文：先在 Mystrix 启动 Launch，再启动 Live。设备日志应出现 `HELLO_ACK received`、`SYNC_BEGIN` 与 `SYNC_END ... complete=True`。Live 日志应出现 `Launch Remote Script initialized` 和 `Launch received HELLO`。

On macOS, Live's log is normally at:

```text
~/Library/Preferences/Ableton/Live 12.4.6/Log.txt
```

If the normal Script does not connect, use the optional `LaunchHandshake` archive first. It performs a read-only handshake test and does not control your Live Set.

如果正式 Script 无法连接，先使用可选的 `LaunchHandshake` 包。它只做只读握手测试，不控制 Live Set。

## Rollback / 回退

English: Close Live, restore the App and Remote Script folders you backed up, reopen Live, and restore your previous Control Surface selection.

中文：关闭 Live，恢复之前备份的 App 和 Remote Script 文件夹，重新打开 Live，并恢复原先的 Control Surface 选择。
