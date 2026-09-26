# Development Guide / 开发指南

## Local setup / 本地环境

English: No MatrixOS firmware checkout is required to run the CPython test suite. The tests provide MatrixOS and Live doubles where necessary. Use Python 3.9 or newer.

中文：运行 CPython 测试不需要 MatrixOS 固件源码。测试会在需要时提供 MatrixOS 与 Live 的替身对象。使用 Python 3.9 或更新版本。

```bash
python3 -m unittest discover -s tests/launch -q
```

Expected result / 预期结果：all tests pass / 所有测试通过。

## Package commands / 打包命令

```bash
python3 Tools/package_launch.py
python3 Tools/package_live_handshake_check.py
shasum -a 256 dist/LaunchApp-V1.zip
```

English: Packaging only creates local ZIP archives under `dist/`. It does not access a device, Live, User Library, or any Live Set.

中文：打包只会在 `dist/` 创建本地 ZIP，不会访问设备、Live、User Library 或任何 Live Set。

## Change discipline / 修改原则

1. Update both protocol implementations together. A protocol version change requires updating the App, Remote Script, handshake Script, tests, package metadata, and documentation.
2. Keep Live as the state authority. Device code must render a mirror and must not manufacture Clip or Track state.
3. Keep external-change protection for every queued action. If target identity cannot be proved, cancel rather than act.
4. Do not modify MatrixOS core to solve an App-layer issue.
5. Do not install or test against a user's working Live environment without their explicit manual action.

1. 同时更新两端协议实现。协议版本变化必须同步更新 App、Remote Script、握手 Script、测试、包元数据和文档。
2. 保持 Live 是状态权威。设备代码只能绘制镜像，不得自行制造 Clip 或 Track 状态。
3. 每个排队操作都必须保留外部变化保护。无法证明目标身份时应取消，不能猜测执行。
4. 不要为解决 App 层问题而修改 MatrixOS 核心。
5. 未经用户明确的手动操作，不得安装或在用户工作中的 Live 环境测试。

## Pull request checklist / 合并请求清单

- [ ] Local tests pass / 本地测试通过。
- [ ] `git diff --check` passes / `git diff --check` 通过。
- [ ] App and Remote Script protocol versions match / App 与 Remote Script 协议版本一致。
- [ ] User-facing documentation has Chinese and English text / 面向用户的文档具有中英文内容。
- [ ] No generated archive, log, hardware dump, Live Set, or User Library file is tracked / 未跟踪生成包、日志、硬件转储、Live Set 或 User Library 文件。
