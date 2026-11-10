"""在线更新：下载新版安装包，校验后打开安装程序。

只在用户点「下载并安装」时运行（jobs.start('update')），不在后台自动联网。步骤：

1. 重新向 GitHub 查询最新版本（update_check.check），不信任页面传来的任何地址；
2. 只从本项目发布页下载 KongFlow-<版本>.dmg，跳转只允许到 GitHub 自己的下载域名；
3. 核对文件大小与 GitHub 给出的 SHA-256，不一致就删除并报错；
4. 挂载磁盘映像，打开其中的安装程序。之后的管理员授权与安装由 macOS 安装器完成。

安装包目前是本地签名、未经 Apple 公证的；这里的校验保证的是「与发布页上的文件一致」。
"""

import hashlib
import os
import plistlib
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import core
import update_check

CHUNK = 256 * 1024
FAILED = '下载未完成，请检查网络后重试，或打开发布页手动下载。'


def allowed(url):
    """Downloads start at github.com and may only be redirected to GitHub's own asset hosts."""
    parts = urlsplit(url)
    host = parts.hostname or ''
    return parts.scheme == 'https' and (host == 'github.com' or host.endswith('.githubusercontent.com'))


class GitHubOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('下载地址被重定向到 GitHub 以外的站点，已停止')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def folder():
    return core.DATA / 'updates'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def verified(path, asset):
    return (
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == asset['size']
        and digest(path) == asset['sha256']
    )


def download(asset, progress=lambda done, total: None, opener=None):
    """Fetch the asset into the updates folder and return its path. Nothing unverified is left behind."""
    if not update_check.DMG.fullmatch(asset['name']) or not allowed(asset['url']):
        raise ValueError('安装包信息无效')
    target = folder() / asset['name']
    if verified(target, asset):
        return target
    folder().mkdir(parents=True, exist_ok=True)
    opener = opener or build_opener(GitHubOnly())
    request = Request(asset['url'], headers={'User-Agent': 'KongFlow-update', 'Accept': 'application/octet-stream'})
    fd, temp = tempfile.mkstemp(dir=str(folder()), prefix='.download-')
    try:
        h = hashlib.sha256()
        done = 0
        with os.fdopen(fd, 'wb') as out:
            try:
                with opener.open(request, timeout=30) as response:
                    while True:
                        block = response.read(CHUNK)
                        if not block:
                            break
                        done += len(block)
                        if done > asset['size']:
                            raise ValueError('下载的文件比发布页记录的大，已停止')
                        h.update(block)
                        out.write(block)
                        progress(done, asset['size'])
            except HTTPError as e:
                raise ValueError('GitHub 暂时无法下载（HTTP %d）。%s' % (e.code, FAILED))
            except (URLError, TimeoutError, OSError):
                raise ValueError(FAILED)
            out.flush()
            os.fsync(out.fileno())
        if done != asset['size'] or h.hexdigest() != asset['sha256']:
            raise ValueError('安装包校验未通过（大小或 SHA-256 与发布页不一致），已删除，请重试')
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    for old in folder().iterdir():  # keep only the installer just verified
        if old != target and old.is_file():
            old.unlink()
    return target


def open_installer(image, run=subprocess.run):
    """Mount the disk image and open its installer package; fall back to showing the image in Finder."""
    try:
        attached = run(
            ['/usr/bin/hdiutil', 'attach', '-readonly', '-plist', str(image)], capture_output=True, timeout=120
        )
        if attached.returncode:
            raise ValueError('磁盘映像无法挂载')
        entities = plistlib.loads(attached.stdout).get('system-entities', [])
        mount = next((Path(e['mount-point']) for e in entities if isinstance(e, dict) and e.get('mount-point')), None)
        packages = (
            sorted(p for p in mount.iterdir() if p.suffix == '.pkg' and not p.name.startswith('.')) if mount else []
        )
        if len(packages) != 1:
            raise ValueError('磁盘映像中没有找到安装程序')
        run(['/usr/bin/open', str(packages[0])], check=True, timeout=15)
        return '安装程序已打开，请按提示完成安装（需要管理员授权）。安装后请保存工作，注销并重新登录。'
    except (OSError, ValueError, subprocess.SubprocessError, plistlib.InvalidFileException):
        try:
            run(['/usr/bin/open', str(image)], check=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            raise ValueError('安装包已下载并校验，但未能自动打开。请在访达中打开：%s' % image)
        return '安装包已下载并校验，已在访达中打开。请双击其中的安装程序；安装后注销并重新登录。'


def run(progress=lambda stage, detail=None: None, include_preview=False, opener=None, runner=subprocess.run):
    progress('update-check')
    info = update_check.check(include_preview)
    asset = info.get('asset')
    if not info.get('available'):
        raise ValueError(info['message'])
    if not asset:
        raise ValueError('这个版本不能在设置里直接安装（发布页没有可校验的 DMG），请打开发布页下载。')
    progress('update-download', 0)
    last = [-1]

    def report(done, total):
        percent = done * 100 // total
        if percent != last[0]:
            last[0] = percent
            progress('update-download', percent)

    image = download(asset, report, opener)
    progress('update-open')
    message = open_installer(image, runner)
    return {'message': message, 'version': info['latest'], 'file': str(image)}
