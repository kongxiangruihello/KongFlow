# KongIME

**KongIME ---- 自由输入，专注表达。**

面向 macOS 的个人全拼输入法，基于 Rime／鼠须管与雾凇词库。开发者：孔祥瑞。

当前版本：**0.27.0 测试版**。支持 Apple Silicon Mac、macOS 13 及以上。

## 本版功能

- 候选屏蔽可选当前拼音或所有拼音，支持确认后切换范围、取消和撤销。
- 为 Word、Chrome 等应用单独设置候选间距，或跟随全局间距。
- 新增设置参与备份恢复与差异预览；旧版全局屏蔽规则保持原有范围。
- 增加真实引擎边界检查与应用兼容实测清单，第三方应用实测仍待安装后完成。

[下载测试版安装包](https://github.com/kongxiangruihello/KongIME/releases) · [0.27 使用说明](README-0.27.md) · [验证记录](VALIDATION-0.27.md)

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

产物位于 `release/KongIME-0.27/`，上级目录同时生成 `KongIME-0.27-Mac.zip`。构建脚本要求输出目录尚不存在，避免覆盖已有交付物。未准备引擎依赖时，涉及真实引擎的测试不能运行。

开发设置界面可指定临时数据目录再启动 `app.py --no-open --port 0`；不要用开发测试覆盖真实输入法数据。

## 验证范围

165 项 Python 回归：163 通过，2 项缺少外部词库样本而跳过。真实 Rime／LevelDB 回归通过；本版另外运行了 198 项候选几何模拟检查。未将 0.27 安装到当前运行环境；第三方编辑器兼容性和两台物理 Mac 的完整迁移仍待现场验证。

## 上游与许可证

原生客户端基于鼠须管修改，保留 GPL-3.0 许可证。引擎接口头文件遵循 librime 自身许可证；雾凇和格式参考相关说明见 `licenses/`。仓库不包含个人输入内容、账户凭据或学习数据库。历史云服务原型保留在 `cloud/`，当前设置界面不提供云服务器入口。
