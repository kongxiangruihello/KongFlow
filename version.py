"""KongFlow 的版本号——全项目只在这里写一次。

管理端（workflow.VERSION）、完整备份、打包脚本（build_integrated.py）都从这里读取；
build_client.sh 在编译时把它写进客户端可执行文件（client/build/Version.swift）。
发新版只改下面这一行，并在 docs/releases/ 增加 README-<SHORT>.md。
"""

VERSION = '0.42.0'
SHORT = '.'.join(VERSION.split('.')[:2])  # 0.41：用于文件名与发布说明


def parse(value):
    """'0.41.0' / 'v0.41' → (0, 41, 0)；无法识别时返回 None。"""
    import re

    match = re.fullmatch(r'v?(\d{1,4})\.(\d{1,4})(?:\.(\d{1,4}))?', str(value))
    return tuple(int(x or 0) for x in match.groups()) if match else None


if __name__ == '__main__':
    print(VERSION)
