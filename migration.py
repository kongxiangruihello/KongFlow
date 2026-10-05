"""换电脑一键迁移（0.38）。

每台 Mac 把一份完整备份写到 iCloud Drive / KongIME / Migration / <这台 Mac 的标识>/：
配置、词库、短语、候选偏好、字号表、学习词频（复用完整迁移格式 kongime-complete-v1），
另加「我的典籍」与本地输入统计。新 Mac 打开设置即可列出各台 Mac 的最新备份并一键恢复。

- 自动备份由输入法客户端在键盘空闲时每天触发一次（需短暂停用 Rime 才能读出学习词频）。
- 手动「立即备份」与恢复都经由客户端执行（learning.request），与完整迁移相同。
- 自动备份只保留每台 Mac 最近 AUTO_KEEP 份；手动备份不自动删除。
"""
import json, os, re, subprocess, time, uuid
from pathlib import Path
import core, complete_backup, personal_data, profile_backup, restore_review

FORMAT = 'kongflow-migration-v1'
AUTO_KEEP = 10
MAX_BYTES = 80 * 1024 * 1024
FILE = re.compile(r'KongFlow-(\d{8})-(\d{6})-(auto|manual)\.json')
MACHINE = re.compile(r'[a-f0-9]{16}')


def root():
    return personal_data.icloud_root().parent / 'Migration'


def settings():
    try:
        value = json.loads((core.DATA / 'migration-settings.json').read_text())
    except (OSError, ValueError):
        value = {}
    return {'auto': value.get('auto', True) is not False}


def set_auto(enabled):
    if type(enabled) is not bool:
        raise ValueError('设置无效')
    core.atomic_json(core.DATA / 'migration-settings.json', {'auto': enabled})
    return settings()


def _status_record():
    try:
        return json.loads((core.DATA / 'migration-status.json').read_text())
    except (OSError, ValueError):
        return {}


def _record(**changes):
    record = _status_record()
    record.update(changes)
    core.atomic_json(core.DATA / 'migration-status.json', record)


def _run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def machine():
    """Hardware-based id (stays the same after reinstalling macOS) and the computer name."""
    import hashlib
    found = re.search(r'"IOPlatformUUID" = "([^"]+)"', _run(['/usr/sbin/ioreg', '-rd1', '-c', 'IOPlatformExpertDevice']))
    if found:
        ident = hashlib.sha256(found.group(1).encode()).hexdigest()[:16]
    else:
        path = core.DATA / 'machine-id.json'
        try:
            ident = json.loads(path.read_text())['id']
            if not MACHINE.fullmatch(ident):
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError):
            ident = uuid.uuid4().hex[:16]
            core.atomic_json(path, {'id': ident})
    name = _run(['/usr/sbin/scutil', '--get', 'ComputerName']).strip() or os.uname().nodename
    return {'id': ident, 'name': name[:80]}


# ---- 内容 ----

def _classics():
    try:
        books = json.loads((core.DATA / 'classics_user.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return books if isinstance(books, list) else []


def _typing_stats():
    try:
        days = json.loads((core.DATA / 'typing-stats.json').read_text()).get('days', {})
    except (OSError, ValueError, AttributeError):
        return {}
    return days if isinstance(days, dict) else {}


def validate_extras(extras):
    if not isinstance(extras, dict):
        raise ValueError('迁移备份格式无效')
    books = extras.get('classics', [])
    if not isinstance(books, list) or len(books) > 500:
        raise ValueError('「我的典籍」格式无效')
    for book in books:
        if not isinstance(book, dict) or not isinstance(book.get('name'), str) or not book['name'] or len(book['name']) > 40 or not isinstance(book.get('chapters'), list):
            raise ValueError('「我的典籍」格式无效')
        for chapter in book['chapters']:
            if not isinstance(chapter, dict) or not isinstance(chapter.get('name'), str) or not isinstance(chapter.get('paragraphs'), list) or not all(isinstance(x, str) for x in chapter['paragraphs']):
                raise ValueError('「我的典籍」格式无效')
    days = extras.get('typing_stats', {})
    if not isinstance(days, dict) or len(days) > 1000:
        raise ValueError('输入统计格式无效')
    for day, entry in days.items():
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(day)) or not isinstance(entry, dict) or not all(k in ('chars', 'han', 'commits') and type(v) is int and 0 <= v < 2**40 for k, v in entry.items()):
            raise ValueError('输入统计格式无效')
    return {'classics': books, 'typing_stats': days}


def summary(complete, extras):
    state = complete['profile']['manager']['state']
    return {'libraries': len(state.get('libraries', [])), 'personal': len(state.get('personal', [])),
            'phrases': len(state.get('phrases', [])), 'names': len(state.get('names', [])),
            'learning': len(complete['learning']['rows']), 'classics': len(extras['classics']),
            'typed': sum(int(x.get('chars', 0)) for x in extras['typing_stats'].values())}


def empty(info):
    return not any(info[k] for k in ('libraries', 'personal', 'phrases', 'names', 'learning', 'classics'))


def validate(bundle):
    if not isinstance(bundle, dict) or bundle.get('format') != FORMAT:
        raise ValueError('不是 KongFlow 迁移备份')
    complete_backup.validate(bundle['complete'])
    extras = validate_extras(bundle.get('extras', {}))
    if bundle.get('checksum') != restore_review.fingerprint({'complete': bundle['complete'], 'extras': bundle['extras']}):
        raise ValueError('迁移备份校验失败，文件可能不完整（iCloud 可能仍在同步），请稍后再试')
    return extras


# ---- 备份（在客户端暂停 Rime 时由 learning.worker 调用） ----

def export(tool, library, temp, auto=False):
    if auto and not settings()['auto']:
        return {'skipped': True, 'message': '自动备份已关闭'}
    try:
        folder = root()
        with profile_backup.locked():
            profile = profile_backup.snapshot()
        complete = complete_backup.pack(profile, complete_backup.export_learning(tool, library, temp))
        extras = {'classics': _classics(), 'typing_stats': _typing_stats()}
        validate_extras(extras)
        info = summary(complete, extras)
        if auto and empty(info):
            _record(last_auto_skip=time.strftime('%Y-%m-%d %H:%M:%S'))
            return {'skipped': True, 'message': '本机还没有个人数据，未备份'}
        me = machine()
        bundle = {'format': FORMAT, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'version': complete['version'],
                  'machine': me, 'kind': 'auto' if auto else 'manual', 'summary': info, 'complete': complete, 'extras': extras}
        bundle['checksum'] = restore_review.fingerprint({'complete': complete, 'extras': extras})
        encoded = json.dumps(bundle, ensure_ascii=False).encode()
        if len(encoded) > MAX_BYTES:
            raise ValueError('迁移备份超过 80 MB，未保存')
        target = folder / me['id']
        target.mkdir(parents=True, exist_ok=True)
        name = 'KongFlow-%s-%s.json' % (time.strftime('%Y%m%d-%H%M%S'), bundle['kind'])
        profile_backup.write_bytes(target / name, encoded)
        meta = {'id': me['id'], 'name': me['name'], 'latest': {'file': name, 'created': bundle['created'], 'kind': bundle['kind'], 'version': bundle['version'], 'summary': info}}
        profile_backup.write_bytes(target / 'machine.json', json.dumps(meta, ensure_ascii=False).encode())
        _prune(target)
        _record(last_backup=bundle['created'], last_kind=bundle['kind'], last_error=None)
        return {'ok': True, 'file': name, 'summary': info, 'message': '已备份到 iCloud Drive（%s）' % me['name']}
    except Exception as e:
        _record(last_error=str(e), last_error_time=time.strftime('%Y-%m-%d %H:%M:%S'))
        raise


def _files(folder):
    """(name, downloaded) for backups in one machine folder, newest first; includes iCloud placeholders."""
    found = {}
    for p in folder.iterdir():
        name = p.name
        if name.startswith('.') and name.endswith('.icloud'):
            name = name[1:-len('.icloud')]
        if FILE.fullmatch(name) and not p.is_symlink():
            found[name] = found.get(name, False) or p.name == name
    return sorted(found.items(), key=lambda x: FILE.fullmatch(x[0]).group(1, 2), reverse=True)


def _prune(folder):
    autos = [name for name, _ in _files(folder) if name.endswith('-auto.json')]
    for name in autos[AUTO_KEEP:]:
        for p in (folder / name, folder / ('.' + name + '.icloud')):
            try:
                p.unlink()
            except FileNotFoundError:
                pass


# ---- 列表与状态 ----

def _local_fresh():
    s = core.state()
    if s.get('libraries') or s.get('personal') or s.get('phrases') or s.get('names') or _classics():
        return False
    return True


def status():
    record = _status_record()
    result = {'auto': settings()['auto'], 'last_backup': record.get('last_backup'), 'last_kind': record.get('last_kind'),
              'last_error': record.get('last_error'), 'last_restore': record.get('last_restore'), 'machines': [], 'suggest': False}
    try:
        folder = root()
    except ValueError as e:
        result.update(available=False, message=str(e))
        return result
    me = machine()
    result.update(available=True, me=me, message='备份位置：iCloud Drive / KongIME / Migration。上传由 macOS 完成。')
    if folder.is_dir():
        for sub in folder.iterdir():
            if not sub.is_dir() or sub.is_symlink() or not MACHINE.fullmatch(sub.name):
                continue
            files = _files(sub)
            if not files:
                continue
            try:
                meta = json.loads((sub / 'machine.json').read_text())
            except (OSError, ValueError):
                meta = {}
            latest_name, downloaded = files[0]
            m = FILE.fullmatch(latest_name)
            latest = meta.get('latest') if isinstance(meta.get('latest'), dict) and meta['latest'].get('file') == latest_name else {}
            result['machines'].append({
                'id': sub.name, 'name': str(meta.get('name') or '未知 Mac')[:80], 'mine': sub.name == me['id'],
                'file': latest_name, 'downloaded': downloaded, 'count': len(files),
                'created': latest.get('created') or '%s-%s-%s %s:%s' % (m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:], m.group(2)[:2], m.group(2)[2:4]),
                'kind': m.group(3), 'version': latest.get('version'), 'summary': latest.get('summary')})
    result['machines'].sort(key=lambda x: x['created'], reverse=True)
    result['suggest'] = bool(result['machines']) and not record.get('dismissed') and not record.get('last_restore') and _local_fresh()
    return result


def dismiss():
    _record(dismissed=True)
    return {'ok': True}


# ---- 恢复 ----

def _load(machine_id, name):
    if not isinstance(machine_id, str) or not MACHINE.fullmatch(machine_id) or not isinstance(name, str) or not FILE.fullmatch(name):
        raise ValueError('备份名称无效')
    path = root() / machine_id / name
    if path.is_symlink():
        raise ValueError('备份文件无效')
    if not path.is_file():
        # Ask iCloud to download an evicted file, then wait for it.
        _run(['/usr/bin/brctl', 'download', str(path)])
        for _ in range(120):
            if path.is_file():
                break
            time.sleep(0.5)
        else:
            raise ValueError('iCloud 还没有把这份备份下载到本机，请稍候再试，或在访达中打开 iCloud Drive / KongIME / Migration 手动下载')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('备份过大')
    for attempt in range(3):
        try:
            return json.loads(path.read_text())
        except ValueError:
            if attempt == 2:
                raise ValueError('备份文件不完整，iCloud 可能仍在同步，请稍后再试')
            time.sleep(2)


def restore(machine_id, name):
    """Replace this Mac's KongFlow data with a migration backup. The caller then applies (deploys)."""
    bundle = _load(machine_id, name)
    extras = validate(bundle)
    preview = complete_backup.preview(bundle['complete'])
    try:
        result = complete_backup.confirm(preview['id'])
    except ValueError as e:
        raise ValueError(str(e) + '（请确认已在「系统设置 › 键盘 › 输入法」添加 KongFlow，并已切换到它一次）')
    # 我的典籍：恢复前的版本另存一份。
    current = core.DATA / 'classics_user.json'
    if current.exists():
        profile_backup.write_bytes(core.DATA / 'classics_user.before-migration.json', current.read_bytes())
    import term_tools
    term_tools._save_books(extras['classics'])
    # 输入统计：按日合并，同一天取较大值，避免重复累加。
    days = _typing_stats()
    for day, entry in extras['typing_stats'].items():
        mine = days.get(day, {})
        days[day] = {k: max(int(mine.get(k, 0)), int(entry.get(k, 0))) for k in ('chars', 'han', 'commits')}
    core.atomic_json(core.DATA / 'typing-stats.json', {'version': 1, 'days': days})
    source = (bundle.get('machine') or {}).get('name') or '另一台 Mac'
    _record(last_restore={'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'from': source, 'created': bundle.get('created')})
    info = bundle.get('summary') or {}
    return {'ok': True, 'verified': result.get('verified', False),
            'message': '已从「%s」%s 的备份恢复：设置、词库、短语、字号表、学习词频 %s 条、我的典籍 %d 部、输入统计。正在应用到输入法…' % (
                source, bundle.get('created', ''), info.get('learning', len(bundle['complete']['learning']['rows'])), len(extras['classics']))}
