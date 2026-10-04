# Contributing

Thanks for helping improve LaunchApp.

## Before opening a change

- For bug reports, include the LaunchApp release, MatrixOS version, Ableton Live version, device model, exact reproduction steps, and relevant logs with personal data removed.
- Keep changes focused. Do not combine unrelated protocol, behavior, and documentation changes.
- Add or update a meaningful test for behavior changes.
- Update both English and Simplified Chinese documentation when user-facing behavior or setup changes.
- Preserve the separation between V1 protocol v7 and V2 protocol v11. Never mix the two endpoints.
- Do not include firmware source, Live Sets, private device logs, personal library contents, generated archives, or credentials.

## Local checks

From the repository root, run:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/launch -q
    git diff --check

To create the paired 40 ms package:

    python3 Tools/package_launch.py --packet-gap-ms 40

The ZIP is generated under dist/ and is not installed automatically. Follow docs/VALIDATION.md for Live and hardware checks. Automated tests are not a substitute for physical-device acceptance.

## Pull requests

Describe the user-visible change, implementation area, automated checks, and any Live/device tests separately. State clearly when hardware acceptance has not been performed.

# 贡献指南

感谢你帮助改进 LaunchApp。

## 提交改动前

- 报告问题时，请提供 LaunchApp 发布版本、MatrixOS 版本、Ableton Live 版本、设备型号、准确复现步骤，并在移除个人信息后附上相关日志。
- 保持改动范围清晰，不要把无关的协议、行为和文档改动混在一起。
- 改变行为时添加或更新有意义的测试。
- 用户可见行为或安装方式改变时，同步更新英文和简体中文文档。
- 保持 V1 协议 v7 与 V2 协议 v11 分离，绝不混用两端。
- 不要提交固件源码、Live Set、私人设备日志、个人音乐库内容、生成的压缩包或凭据。

## 本地检查

在仓库根目录运行：

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/launch -q
    git diff --check

生成配套 40 ms 压缩包：

    python3 Tools/package_launch.py --packet-gap-ms 40

ZIP 会生成在 dist/，不会自动安装。Live 与实机测试请按 docs/VALIDATION.zh-CN.md 执行。自动化测试不能替代实机验收。

## Pull Request

说明用户能看到的变化、涉及的实现部分、自动化检查结果，并分别列出 Live 与设备实测。若未进行实机验收，请明确说明。
