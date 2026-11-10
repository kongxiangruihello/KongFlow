# KongFlow 构建与维护说明

**KongFlow ---- 自由输入，专注表达。**

面向 macOS 的个人全拼输入法，基于 Rime／鼠须管与雾凇词库。开发者：孔祥瑞。支持 Apple Silicon Mac、macOS 13 及以上。

当前版本见 `version.py`；各版本的使用说明与验证记录在 [docs/releases/](docs/releases/)。项目曾先后名为「轻言」和 KongIME，为了原地升级，数据目录、应用标识和部分文件名（`QINGYAN_DATA`、`qingyan.schema.yaml`、`kongime_*.lua` 等）沿用旧名，不要改动。

## 项目结构

- `client/sources/`：原生输入法、候选窗口和系统菜单（Swift，基于鼠须管）。
- `app.py`、`web/`：设置窗口和它的本机接口。每个接口是 `app.py` 里 `GET_ROUTES`／`POST_ROUTES` 的一项。
- `core.py`、`runtime/`：词库、拼音规则和候选过滤。
- `complete_backup.py`、`learning.py`、`migration.py`：完整迁移、学习词频维护与换电脑迁移。
- `update_check.py`、`online_update.py`：检查更新与在线更新。
- `version.py`：版本号的唯一来源。
- `tests/`：回归测试。

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

产物位于 `release/KongFlow-<版本>/`，上级目录同时生成 `KongFlow-<版本>-Mac.zip` 与 `KongFlow-<版本>.dmg`。构建脚本要求输出目录尚不存在，避免覆盖已有交付物。未准备引擎依赖时，涉及真实引擎的测试不能运行。

开发设置界面可指定临时数据目录再启动 `app.py --no-open --port 0`；不要用开发测试覆盖真实输入法数据。

## 发布新版本

1. 改 `version.py` 里的 `VERSION`（只此一处），并新增 `docs/releases/README-<版本>.md`——它会作为安装包里的「开始使用.txt」。
2. 推送到 main，等 GitHub Actions 构建完成，从该次运行的 Artifacts 下载 DMG。
3. 在 GitHub 新建 Release：标签写版本号（如 `0.41` 或 `v0.41.0`），上传 `KongFlow-<版本>.dmg`，文件名不要改。

在线更新依赖第 3 步：它只认本仓库发布页上名为 `KongFlow-<版本>.dmg` 的文件，并用 GitHub 自动记录的 SHA-256 校验下载结果。标记为 Pre-release 的版本，只有勾选「包含测试版」的用户才会看到。

## 代码排版

Python 用 ruff，网页用 prettier，配置在 `pyproject.toml` 与 `.prettierrc.json`。提交前运行：

```sh
ruff format .
npx prettier@3.3.3 --write web
```

检查源码里是否含有某段代码的测试请用 `tests/source_text.py` 的 `Source`，它比较时忽略空白，不受排版影响。

## 上游与许可证

原生客户端基于鼠须管修改，保留 GPL-3.0 许可证。引擎接口头文件遵循 librime 自身许可证；雾凇和格式参考相关说明见 `licenses/`。仓库不包含个人输入内容、账户凭据或学习数据库。历史云服务原型保留在 `cloud/`，当前设置界面不提供云服务器入口。

## 自动构建（GitHub Actions）

`.github/workflows/build-dmg.yml` 在 GitHub 的 macOS 14（Apple Silicon）机器上完成上述全部步骤：按固定提交获取雾凇词库、下载鼠须管 1.1.2 并校验 SHA-256、编译、运行全部测试、打包。推送到 main、提交拉取请求，或在 Actions 页面点 **Run workflow** 即可触发；完成后在该次运行页面底部的 Artifacts 下载 DMG、zip 和 SHA256SUMS.txt，保留 30 天。产物同样为本地签名，未经 Apple 公证。

## 图标

应用图标的原图是 `branding/icon/KongFlow-icon-source.png`（白底方形图）。替换原图后运行 `python3 branding/icon/make_icons.py`（需 `pip install pillow numpy scipy cairosvg`）：脚本去掉白底、按 macOS 图标网格（1024 画布内 824 圆角方块）加阴影，生成 `branding/KongFlow.icns`；菜单栏单色模板图标在脚本内以 SVG 绘制，生成 `branding/rime.pdf`。再提交。构建时会把它们放入安装包。

## 换电脑迁移

`migration.py`：完整备份（kongime-complete-v1）加「我的典籍」与输入统计，写入 iCloud Drive / KongIME / Migration / <机器标识>/。机器标识取 IOPlatformUUID 的 SHA-256 前 16 位，重装系统后不变。手动备份经 `learning.request('migration-export')`，自动备份由客户端 `autoBackupIfDue()` 在键盘空闲时以 `learning.py … migration-auto` 运行；两者都在 Rime 暂停时读取学习词频。

## 参考数据

`runtime/kongflow_eras.tsv`（年号）与 `runtime/kongflow_classics.tsv`（四书）由 `tools/build_reference_data.py` 生成（需 `pip install pypinyin opencc-python-reimplemented`），来源与许可见脚本开头。修改脚本后重新运行并提交生成的文件。

农历月表 `runtime/kongflow_months.tsv` 由 `node tools/build_calendar_data.js <index_c.js 路径>` 生成，`index_c.js` 取自 https://github.com/ytliu0/ChineseCalendar （GPL-3.0）。
