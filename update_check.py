"""Explicit, read-only release checks; never sends personal configuration.

select() also says whether the newest release can be installed from the settings window
(online_update.py does the download).
"""

import json, re, time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import workflow
from version import parse

REPO = 'https://github.com/kongxiangruihello/KongFlow'
API = 'https://api.github.com/repos/kongxiangruihello/KongFlow/releases?per_page=100'
MAX_BYTES = 2 * 1024 * 1024
MAX_INSTALLER = 400 * 1024 * 1024
ARCHIVE = re.compile(r'(?:KongIME|KongFlow)-\d+\.\d+(?:\.\d+)?-Mac\.zip')
DMG = re.compile(r'KongFlow-\d+\.\d+(?:\.\d+)?\.dmg')


def version(value):
    return parse(value)


def installer(row, prefix):
    """The release's disk image, when it can be installed from the settings window.

    That needs a KongFlow-<version>.dmg whose size and SHA-256 GitHub reports (the `digest` field),
    so the download can be verified before it is opened.
    """
    for a in row.get('assets', []):
        if not isinstance(a, dict) or a.get('state') != 'uploaded':
            continue
        name, digest, size = a.get('name', ''), a.get('digest'), a.get('size')
        if (
            isinstance(name, str)
            and DMG.fullmatch(name)
            and a.get('browser_download_url') == prefix + name
            and type(size) is int
            and 0 < size <= MAX_INSTALLER
            and isinstance(digest, str)
            and re.fullmatch('sha256:[0-9a-f]{64}', digest)
        ):
            return {'name': name, 'size': size, 'sha256': digest[7:], 'url': prefix + name}
    return None


def select(rows, include_preview=False):
    if not isinstance(rows, list):
        raise ValueError('版本信息格式异常，请前往 GitHub 查看')
    candidates = []
    for row in rows:
        if not isinstance(row, dict) or row.get('draft') or (row.get('prerelease') and not include_preview):
            continue
        tag = row.get('tag_name')
        number = version(tag)
        if not number or row.get('html_url') != REPO + '/releases/tag/' + tag:
            continue
        prefix = REPO + '/releases/download/' + tag + '/'
        assets = [
            a
            for a in row.get('assets', [])
            if isinstance(a, dict)
            and a.get('state') == 'uploaded'
            and isinstance(a.get('name'), str)
            and (ARCHIVE.fullmatch(a['name']) or DMG.fullmatch(a['name']))
            and a.get('browser_download_url') == prefix + a['name']
            and a.get('size', 0) > 0
        ]
        if assets:
            candidates.append((number, row))
    current = version(workflow.VERSION)
    if not candidates:
        return {
            'current': workflow.VERSION,
            'available': False,
            'installable': False,
            'asset': None,
            'message': '暂未找到可下载的' + ('正式版或测试版' if include_preview else '正式版') + '。',
            'url': REPO + '/releases',
        }
    number, row = max(candidates, key=lambda x: x[0])
    new = number > current
    asset = installer(row, REPO + '/releases/download/' + row['tag_name'] + '/') if new else None
    return {
        # 可在设置里直接下载安装（有 DMG 且 GitHub 给出校验值）；否则只提供发布页链接。
        'installable': bool(asset),
        'asset': asset,
        'current': workflow.VERSION,
        'latest': row['tag_name'],
        'available': new,
        'prerelease': bool(row.get('prerelease')),
        'url': row['html_url'],
        'message': ('发现新版本：' if new else '当前版本已是所选范围内的最新版本；发布页版本：')
        + row['tag_name']
        + ('（测试版）' if row.get('prerelease') else ''),
    }


def check(include_preview=False):
    if type(include_preview) is not bool:
        raise ValueError('更新选项无效')
    request = Request(
        API,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'KongIME-update-check',
            'X-GitHub-Api-Version': '2022-11-28',
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('版本信息过大，请前往 GitHub 查看')
        result = select(json.loads(raw), include_preview)
    except HTTPError as e:
        raise ValueError('GitHub 暂时无法检查（HTTP %d），请稍后重试或打开发布页。' % e.code)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ValueError('无法连接 GitHub，请检查网络后重试，或打开发布页。')
    result['checked_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    return result
