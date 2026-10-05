# KongFlow 0.32 验证记录

## 已完成

- 成对标点与中英文状态：真实 Rime 引擎（librime 1.10，Linux）配合雾凇 `ascii_composer` 设置与 `select_character` 处理器运行 `tests/ShiftPairToggleSmoke.cpp`，17 项通过：中英文状态下 Shift+( " < { 均保持原状态且不产生文字，单按 Shift 仍切换。修复前同一序列会把中文切成英文。
- 候选折叠：以用户实际词库配置在真实引擎上输入 zgd，每页 9 个候选、引擎报告非最后一页，展开条件成立；`tests/test_v032.py` 检查底栏背景与「更多 ▾／收起 ▴」标签。
- 构建：在 Apple Silicon Mac 上运行 build_client.sh、全部 unittest 与 build_integrated.py，生成 KongFlow-0.32.dmg 并安装运行（runtime 版本 0.32.0）。
- 收起后候选窗口错位（第一行被裁、下方空白）：前两轮修复安装后仍复现。第三版（背景按整个视图绘制、切换时重置滚动与画布）安装后，用临时尺寸日志记录 31 次展开／收起：收起后窗口 623×80、可视区 623×56、文字区 28 高，与展开前完全一致，未再出现错位。日志功能已在 0.33 移除。

## 待现场验证

- 在 macOS 上安装 0.32 后，于备忘录、Word、Chrome、微信草稿中实测成对标点与中英文状态。
- 候选窗口底栏在浅色、深色主题和屏幕边缘的外观。
