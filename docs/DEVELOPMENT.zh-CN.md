# 开发指南

## 环境要求

- 本地测试和打包需要 Python 3.9 或更新版本。
- 运行单元测试不需要安装 Ableton Live 或 MatrixOS；测试会提供相应 API 的替身。
- 实机验收需要 Mystrix Pro 和 README.zh-CN.md 中说明的 Live 环境。

## 自动化检查

在仓库根目录运行：

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/launch -q
    git diff --check

测试覆盖协议编解码、v11 主机/设备结果一致性、灯光帧暂存和确认、恢复流程、渲染与音乐相位、Live 替身操作以及运行时行为。

## 构建配套压缩包

    python3 Tools/package_launch.py --packet-gap-ms 40

输出为 dist/LaunchApp-V2.2.2-responsive-40ms.zip。打包器会把源文件映射到 MatrixOS 与 Ableton Live 需要的文件名；不会自动安装到设备、Live、User Library 或 Live Set。生成的 ZIP 不纳入 Git。

## 修改规则

- 保持 V1 v7 与 V2 v11 两套端点分别配对、独立可用。
- Live 始终作为状态来源。
- 设备端模块必须符合已测试的 MicroPython 内存限制。
- 不修改 MatrixOS 核心，也不在自动化开发中安装到用户环境。
- 同步维护英文和简体中文文档。
- 自动化测试、Live 日志和真机观察要分开记录，不能混为同一级证据。
