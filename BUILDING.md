# KongIME

**KongIME ---- 自由输入，专注表达。**

面向 macOS 的个人全拼输入法，基于 Rime／鼠须管与雾凇词库。开发者：孔祥瑞。

当前版本：**0.28.0 测试版**。支持 Apple Silicon Mac、macOS 13 及以上。

## 本版功能

- 候选置顶、降权和屏蔽后提供即时撤销提示，也可在菜单撤销上次调整。
- 临时暂停词频学习，保留已有排序；可持续到手动恢复或本次输入法退出。
- 真实引擎验证暂停不改变学习数据，恢复后继续学习；旧配置缺少支持时明确提示应用新版。
- 本机原生候选布局检查通过；第三方应用完整实测按用户安排留到安装新版后进行。

[下载测试版安装包](https://github.com/kongxiangruihello/KongIME/releases) · [0.28 使用说明](README-0.28.md) · [验证记录](VALIDATION-0.28.md)

## 项目结构

- `client/sources/`：原生输入法、候选窗口和系统菜单。
- `web/`、`app.py`：集成设置窗口和本机管理接口。
- `core.py`、`runtime/`：词库、拼音规则和候选过滤。
- `complete_backup.py`、`learning.py`：完整迁移与暂停引擎后的学习数据库维护。
- `tests/`：回归与原生文本、候选窗口测试。

## 构建

需要 macOS、Xcode Command Line Tools 和 Python 3.9 或以上。此仓库不存放预编译客户端、用户词库和个人备份。

构建前准备两个依赖目录：

1. `vendor/rime-ice/`：雾凇拼音固定提交 `859e3b5300e0ea01334a627b15db101e94312a75` 的文件，来自 https://github.com/iDvel/rime-ice 。
2. `branding/payload/Squirrel.app`：鼠须管官方 **1.1.2** 应用（含 `librime.1.dylib`、`rime_deployer` 和 SharedSupport），来自 https://github.com/rime/squirrel/releases/tag/1.1.2 。只需解包，无需安装。将本仓库 `branding/BaseInfo.plist` 复制为这个构建副本的 `Contents/Info.plist`，以保持 KongIME 名称与输入源标识。

接口头文件已包含在 `client/librime/`，并保留上游许可证。

```sh
sh build_client.sh
python3 -B -m unittest discover -s tests -q
python3 -B build_integrated.py
```

产物位于 `release/KongIME-0.28/`，上级目录同时生成 `KongIME-0.28-Mac.zip`。构建脚本要求输出目录尚不存在，避免覆盖已有交付物。未准备引擎依赖时，涉及真实引擎的测试不能运行。

开发设置界面可指定临时数据目录再启动 `app.py --no-open --port 0`；不要用开发测试覆盖真实输入法数据。

## 验证范围

169 项 Python 回归：167 通过，2 项缺少外部词库样本而跳过。真实 Rime／LevelDB 回归通过；本版另外运行了本机一块物理屏幕的 15 项长候选与边缘布局检查。未将 0.28 安装到当前运行环境；第三方编辑器兼容性和两台物理 Mac 的完整迁移仍待现场验证。

## 上游与许可证

原生客户端基于鼠须管修改，保留 GPL-3.0 许可证。引擎接口头文件遵循 librime 自身许可证；雾凇和格式参考相关说明见 `licenses/`。仓库不包含个人输入内容、账户凭据或学习数据库。历史云服务原型保留在 `cloud/`，当前设置界面不提供云服务器入口。

## 自动构建（GitHub Actions）

`.github/workflows/build-dmg.yml` 在 GitHub 的 macOS 14（Apple Silicon）机器上完成上述全部步骤：按固定提交获取雾凇词库、下载鼠须管 1.1.2 并校验 SHA-256、编译、运行全部测试、打包。推送到 main 或在 Actions 页面点 **Run workflow** 即可触发；完成后在该次运行页面底部的 Artifacts 下载 DMG、zip 和 SHA256SUMS.txt，保留 30 天。产物同样为本地签名，未经 Apple 公证。

## 图标

应用图标的原图是 `branding/icon/KongFlow-icon-source.png`（白底方形图）。替换原图后运行 `python3 branding/icon/make_icons.py`（需 `pip install pillow numpy scipy cairosvg`）：脚本去掉白底、按 macOS 图标网格（1024 画布内 824 圆角方块）加阴影，生成 `branding/KongFlow.icns`；菜单栏单色模板图标在脚本内以 SVG 绘制，生成 `branding/rime.pdf`。再提交。构建时会把它们放入安装包。

## 换电脑迁移

`migration.py`：完整备份（kongime-complete-v1）加「我的典籍」与输入统计，写入 iCloud Drive / KongIME / Migration / <机器标识>/。机器标识取 IOPlatformUUID 的 SHA-256 前 16 位，重装系统后不变。手动备份经 `learning.request('migration-export')`，自动备份由客户端 `autoBackupIfDue()` 在键盘空闲时以 `learning.py … migration-auto` 运行；两者都在 Rime 暂停时读取学习词频。

## 参考数据

`runtime/kongflow_eras.tsv`（年号）与 `runtime/kongflow_classics.tsv`（四书）由 `tools/build_reference_data.py` 生成（需 `pip install pypinyin opencc-python-reimplemented`），来源与许可见脚本开头。修改脚本后重新运行并提交生成的文件。

农历月表 `runtime/kongflow_months.tsv` 由 `node tools/build_calendar_data.js <index_c.js 路径>` 生成，`index_c.js` 取自 https://github.com/ytliu0/ChineseCalendar （GPL-3.0）。
