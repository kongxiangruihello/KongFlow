#!/usr/bin/env python3
"""Loopback-only management app with session-bound mutation protection.

Every endpoint is one entry in GET_ROUTES or POST_ROUTES below. A handler returns the value to send
as JSON, a Download for files, or (POST only) nothing for a plain {"ok": true}.
"""

import argparse
import base64
import io
import json
import mimetypes
import secrets
import subprocess
import sys
import tempfile
import threading
import traceback
import webbrowser
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import cloud_client
import complete_backup
import core
import jobs
import learning
import library_tools
import local_snapshots
import migration
import personal_data
import phrase_tools
import profile_backup
import quick
import restore_review
import term_tools
import update_check
import upgrade_check
import workflow

TOKEN = secrets.token_urlsafe(32)
PENDING = {}
JSON = 'application/json; charset=utf-8'
STATIC = {'/': 'index.html', '/app.js': 'app.js', '/close-flow.js': 'close-flow.js', '/style.css': 'style.css'}
MAX_BODY = 46 * 1024 * 1024


class Download:
    """A response the settings window saves as a file."""

    def __init__(self, data, filename, kind=JSON):
        self.data, self.filename, self.kind = data, filename, kind


def arg(query, name, default=''):
    return parse_qs(query).get(name, [default])[0]


# ---- GET ----


def get_state(query):
    s = core.state()
    installed = any(
        p.exists()
        for p in [Path('/Library/Input Methods/Squirrel.app'), Path.home() / 'Library/Input Methods/Squirrel.app']
    )
    s.update(
        {
            'token': TOKEN,
            'installed': installed,
            'ready': (core.ROOT / 'vendor/rime-ice/rime_ice.schema.yaml').exists(),
            'data_path': str(core.DATA),
            'rime_path': str(core.RIME),
        }
    )
    return s


def get_history(query):
    rows = []
    revision = core.state()['revision']
    for kind, entries in [('settings', core.change_history()), ('quick', quick.read(core.RIME)[1])]:
        for i, x in enumerate(entries):
            last = i == len(entries) - 1
            rows.append(
                {
                    'kind': kind,
                    'id': x['id'],
                    'time': x['time'],
                    'label': x['label'],
                    'can_undo': last and (kind == 'quick' or x['revision'] == revision),
                }
            )
    return sorted(rows, key=lambda x: x['time'], reverse=True)


def get_import_backup(query):
    receipt = next((x for x in core.state()['imports'] if x['id'] == arg(query, 'id')), None)
    if not receipt or not receipt.get('backup'):
        raise ValueError('这份导入前备份不在当前设备上')
    name = Path(receipt['backup']).name
    data = (core.DATA / 'import-backups' / name).read_bytes()
    return Download(data, 'KongIME-before-import.json', 'application/json')


def get_words(query):
    return core.search_words(
        core.state(),
        arg(query, 'q'),
        arg(query, 'scope', 'all'),
        arg(query, 'order', 'pinyin'),
        arg(query, 'page', '0'),
    )


def get_export(query):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / 'Rime'
        core.make_bundle(root, core.state())
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in root.rglob('*'):
                if p.is_file():
                    z.write(p, 'Rime/' + str(p.relative_to(root)))
    return Download(buf.getvalue(), 'Qingyan-Rime.zip', 'application/zip')


def get_phrases_export(query):
    group = parse_qs(query, keep_blank_values=True).get('group', [None])[0]
    return Download(phrase_tools.export(group), 'KongIME-phrases.json')


def get_sync_status(query):
    return {
        'connected': False,
        'can_rollback': (core.DATA / 'before-profile.json').exists(),
        'learning_included': False,
    }


GET_ROUTES = {
    '/api/phrases-export': get_phrases_export,
    '/api/profile-backup': lambda q: Download(profile_backup.snapshot(), 'KongIME-profile.json'),
    '/api/restore-report': lambda q: {'report': restore_review.last_report()},
    '/api/upgrade-check': lambda q: upgrade_check.read(),
    '/api/snapshots': lambda q: local_snapshots.list_snapshots(),
    '/api/complete-status': lambda q: complete_backup.status(),
    '/api/complete-download': lambda q: Download(complete_backup.value(), 'KongIME-complete.json'),
    '/api/complete-before': lambda q: Download(complete_backup.value(before=True), 'KongIME-before-restore.json'),
    '/api/learning-status': lambda q: learning.status(),
    '/api/typing-stats': lambda q: term_tools.typing_stats(),
    '/api/classics-user': lambda q: term_tools.classics_summary(),
    '/api/fonts': lambda q: {'installed': core.installed_fallback_fonts()},
    '/api/names': lambda q: {'names': core.state()['names']},
    '/api/learning-download': lambda q: Download(learning.export_value(), 'KongIME-learning.json'),
    '/api/diagnostics': lambda q: personal_data.diagnostics(),
    '/api/icloud': lambda q: personal_data.icloud_status(),
    '/api/migration': lambda q: migration.status(),
    '/api/library-content': lambda q: library_tools.content(arg(q, 'id')),
    '/api/library-export': lambda q: Download(
        library_tools.export(arg(q, 'id')), 'KongIME-dictionary.txt', 'text/plain; charset=utf-8'
    ),
    '/api/cloud-status': lambda q: cloud_client.client.status(),
    '/api/cloud-versions': lambda q: cloud_client.client.versions(),
    '/api/sync-status': get_sync_status,
    '/api/state': get_state,
    '/api/quick-preferences': lambda q: quick.read(core.RIME)[0],
    '/api/quick-backup': lambda q: Download(
        {'format': 'kongime-quick-v1', 'preferences': quick.read(core.RIME)[0]}, 'KongIME-quick-backup.json'
    ),
    '/api/history': get_history,
    '/api/apps': lambda q: workflow.installed_apps(),
    '/api/job': lambda q: jobs.status(),
    '/api/status': lambda q: workflow.status(),
    '/api/migrations': lambda q: workflow.legacy_candidates(),
    '/api/review': lambda q: core.review_rows(core.state()),
    '/api/import-backup': get_import_backup,
    '/api/words': get_words,
    '/api/export': get_export,
    '/api/backup': lambda q: Download(
        json.dumps(core.backup_value(), ensure_ascii=False), 'Qingyan-backup.json', 'application/json'
    ),
}


# ---- POST ----


def post_preview(data):
    raw = base64.b64decode(data['data'], validate=True)
    rows, duplicates = core.parse_import(raw, data['name'])
    pid = secrets.token_hex(12)
    PENDING.clear()
    PENDING[pid] = (raw, data['name'])
    return {
        'id': pid,
        'count': len(rows),
        'duplicates': duplicates,
        'rows': rows[:8],
        'scel': core.is_scel(raw, data['name']),
        'sgpu': raw.startswith(b'SGPU'),
        'conflicts': personal_data.conflicts(rows),
        'review': sum(core.needs_review(r) for r in rows),
    }


def post_import(data):
    if data['id'] not in PENDING:
        raise ValueError('预览已过期，请重新选择文件')
    raw, name = PENDING[data['id']]
    return core.import_library(raw, name, data.get('policy', 'higher'))


def post_library(data):
    s = core.state()
    lib = next((x for x in s['libraries'] if x['id'] == data['id']), None)
    if not lib:
        raise ValueError('词库不存在')
    if data.get('delete'):
        personal_data.discard(s, 'library', lib)
        s['libraries'].remove(lib)
    else:
        lib['enabled'] = bool(data['enabled'])
    core.save(s)


def post_word(data):
    s = core.state()
    r = core.normalize(data['word'], data['pinyin'], data['weight'])
    r['pinned'] = bool(data.get('pinned'))
    code = r['pinyin'].replace(' ', '').lower()
    if r['pinned'] and core.needs_review(r):
        raise ValueError('请先在待处理页面修正拼音')
    if r['pinned'] and any(x.get('enabled', True) and x['code'] == code for x in s['phrases']):
        raise ValueError('该拼音与常用短语缩写冲突，请先修改短语缩写')
    old = data.get('old') or {'word': r['word'], 'pinyin': r['pinyin']}
    old_key = (old['word'], old['pinyin'])
    if data.get('delete'):
        for item in s['personal']:
            if (item['word'], item['pinyin']) == old_key:
                personal_data.discard(s, 'word', item)
    s['personal'] = [x for x in s['personal'] if (x['word'], x['pinyin']) not in (old_key, (r['word'], r['pinyin']))]
    if not data.get('delete'):
        if r['pinned']:
            for x in s['personal']:
                if x['pinyin'].replace(' ', '').lower() == code:
                    x['pinned'] = False
        s['personal'].append(r)
    core.save(s)


def post_open_icloud(data):
    root = personal_data.icloud_root().parent
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(['/usr/bin/open', str(root)], check=True, timeout=10)
    return {'ok': True}


def post_learning_preview(data):
    rows = learning.validate(data['backup'])
    return {'count': len(rows), 'rows': rows[:8]}


def post_configuration(data):
    s = core.state()
    preferences = core.normalize_settings(data['settings'])
    appearance = core.normalize_appearance(data['appearance'])
    fuzzy = core.normalize_fuzzy(data['fuzzy'])
    changed = s['settings'] != preferences or s['appearance'] != appearance or s['fuzzy'] != fuzzy
    if changed:
        s.update(settings=preferences, appearance=appearance, fuzzy=fuzzy)
        core.save(s)
    return {'ok': True, 'changed': changed}


def post_settings(data):
    s = core.state()
    count = int(data['page_size'])
    if count not in (3, 5, 7, 9):
        raise ValueError('候选数量须为 3、5、7 或 9')
    s['settings'].update(page_size=count, learning=bool(data['learning']))
    for key in ('folded_count', 'expand_total'):
        if key in data:
            s['settings'][key] = data[key]
    s['settings'] = core.normalize_settings(s['settings'])
    core.save(s)


def post_quick_restore(data):
    backup = data['backup']
    if not isinstance(backup, dict) or backup.get('format') != 'kongime-quick-v1':
        raise ValueError('请选择快捷排序备份文件')
    return quick.change('restore', root=core.RIME, replacement=backup.get('preferences'))


def post_undo_change(data):
    if data['kind'] == 'quick':
        return quick.change('undo', root=core.RIME, event=data['id'])
    return core.undo_change(data['id'])


def post_fuzzy(data):
    s = core.state()
    s['fuzzy'] = core.normalize_fuzzy(data['fuzzy'])
    core.save(s)


def post_appearance(data):
    s = core.state()
    s['appearance'] = core.normalize_appearance(data)
    core.save(s)


def post_app_preference(data):
    s = core.state()
    pref = core.normalize_app_preference(data)
    s['app_preferences'] = [x for x in s['app_preferences'] if x['id'] != pref['id']]
    if not data.get('delete'):
        s['app_preferences'].append(pref)
    core.save(s)


def post_restore(data):
    """Restore a 轻言 backup (qingyan-backup-v1). Validation is shared with the unified restore."""
    before = core.backup_value()
    s, libraries = profile_backup.prepare(data['backup'])
    core.atomic_json(core.DATA / 'before-restore.json', before)
    for lid, rows in libraries:
        core.atomic_json(core.DATA / 'libraries' / (lid + '.json'), rows)
    core.save(s)


POST_ROUTES = {
    '/api/terms-pick': lambda d: term_tools.pick(),
    '/api/classics-import': lambda d: term_tools.import_classics(d['path']),
    '/api/classics-remove': lambda d: term_tools.remove_classic(d['name']),
    '/api/names-import': lambda d: term_tools.import_names(d['text']),
    '/api/names-clear': lambda d: term_tools.clear_names(),
    '/api/terms-scan': lambda d: term_tools.scan(d['path']),
    '/api/terms-add': lambda d: term_tools.add(d['items']),
    '/api/check-update': lambda d: update_check.check(d.get('include_preview', False)),
    '/api/update-install': lambda d: jobs.start('update', include_preview=d.get('include_preview', False)),
    '/api/abbreviation-check': lambda d: jobs.start('abbreviation-check'),
    '/api/phrase-group': phrase_tools.group_update,
    '/api/phrase-organize': phrase_tools.organize,
    '/api/phrase-check': phrase_tools.check_code,
    '/api/phrase-candidate': phrase_tools.candidate,
    '/api/phrases-preview': lambda d: phrase_tools.preview(d['backup']),
    '/api/phrases-import': phrase_tools.confirm,
    '/api/phrase-toggle': phrase_tools.toggle,
    '/api/preview': post_preview,
    '/api/import': post_import,
    '/api/library': post_library,
    '/api/word': post_word,
    '/api/trash-restore': lambda d: personal_data.restore(d['id']),
    '/api/scene': personal_data.scene,
    '/api/open-icloud': post_open_icloud,
    '/api/restore-preview': restore_review.preview,
    '/api/restore-confirm': lambda d: restore_review.confirm(d['id']),
    '/api/upgrade-check': lambda d: upgrade_check.retry(workflow.VERSION),
    '/api/snapshot-create': lambda d: local_snapshots.create('手动保存'),
    '/api/snapshot-restore': lambda d: local_snapshots.restore(d['name']),
    '/api/complete-before-preview': lambda d: complete_backup.preview(complete_backup.value(before=True)),
    '/api/complete-preview': lambda d: complete_backup.preview(d['backup']),
    '/api/complete-export': lambda d: learning.request('complete-export'),
    '/api/complete-restore': lambda d: complete_backup.confirm(d['id']),
    '/api/learning-preview': post_learning_preview,
    '/api/learning-export': lambda d: learning.request('export'),
    '/api/learning-restore': lambda d: learning.request('restore', d['backup']),
    '/api/learning-rollback': lambda d: learning.request('rollback'),
    '/api/icloud-save': lambda d: personal_data.icloud_save(),
    '/api/migration-backup': lambda d: learning.request('migration-export'),
    '/api/migration-restore': lambda d: migration.restore(d['machine'], d['file']),
    '/api/migration-auto': lambda d: migration.set_auto(d['auto']),
    '/api/migration-dismiss': lambda d: migration.dismiss(),
    '/api/icloud-restore': lambda d: personal_data.icloud_restore(d['name']),
    '/api/manual-library': library_tools.save,
    '/api/configuration': post_configuration,
    '/api/settings': post_settings,
    '/api/apply': lambda d: jobs.start('deploy'),
    '/api/recover': lambda d: jobs.start('recover'),
    '/api/quick-preference': lambda d: quick.change(d['action'], d['code'], d['word'], root=core.RIME),
    '/api/quick-restore': post_quick_restore,
    '/api/undo-change': post_undo_change,
    '/api/fuzzy': post_fuzzy,
    '/api/appearance': post_appearance,
    '/api/app-preference': post_app_preference,
    '/api/phrase-preview': core.phrase_preview,
    '/api/phrase': core.save_phrase,
    '/api/pick-directory': lambda d: jobs.start('pick'),
    '/api/inspect-directory': lambda d: workflow.select_directory(d['path']),
    '/api/undo-import': lambda d: core.undo_import(d['id']),
    '/api/resolve': core.resolve_word,
    '/api/setup': lambda d: workflow.setup(d['action']),
    '/api/migrate': lambda d: workflow.migrate(d['id']),
    '/api/cloud-configure': lambda d: cloud_client.client.configure(d['url']),
    '/api/cloud-code': lambda d: cloud_client.client.send_code(d['email']),
    '/api/cloud-login': lambda d: cloud_client.client.login(d['email'], d['code']),
    '/api/cloud-logout': lambda d: cloud_client.client.logout(),
    '/api/cloud-upload': lambda d: cloud_client.client.upload(d['revision']),
    '/api/cloud-restore': lambda d: cloud_client.client.restore(d['revision']),
    '/api/profile-restore': lambda d: profile_backup.restore(d['backup']),
    '/api/profile-rollback': lambda d: profile_backup.rollback(),
    '/api/restore': post_restore,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, data, kind=JSON, filename=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False).encode()
        if isinstance(data, str):
            data = data.encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="%s"' % filename)
        self.end_headers()
        self.wfile.write(data)

    def send_result(self, result):
        if isinstance(result, Download):
            return self.send(200, result.data, result.kind, result.filename)
        self.send(200, {'ok': True} if result is None else result)

    def send_failure(self, error):
        """400 for a request that cannot be carried out as asked; 500 (with a traceback on stderr) for the rest."""
        if isinstance(error, ValueError):
            return self.send(400, {'error': str(error)})
        traceback.print_exc(file=sys.stderr)
        if isinstance(error, (KeyError, TypeError, AttributeError, IndexError)):
            return self.send(400, {'error': '请求内容不完整或格式无效（%s）' % error})
        self.send(500, {'error': '内部错误：%s' % (str(error) or type(error).__name__)})

    def host_ok(self):
        return self.headers.get('Host') == '127.0.0.1:%d' % self.server.server_port

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {'error': 'Host rejected'})
        u = urlparse(self.path)
        try:
            profile_backup.recover()
            if u.path in GET_ROUTES:
                return self.send_result(GET_ROUTES[u.path](u.query))
            name = STATIC.get(u.path)
            if name:
                kind = mimetypes.guess_type(name)[0] + '; charset=utf-8'
                return self.send(200, (core.ROOT / 'web' / name).read_bytes(), kind)
            self.send(404, {'error': 'Not found'})
        except Exception as e:
            self.send_failure(e)

    def do_POST(self):
        origin = self.headers.get('Origin')
        expected = 'http://127.0.0.1:%d' % self.server.server_port
        if not self.host_ok() or self.headers.get('X-Qingyan-Token') != TOKEN or (origin and origin != expected):
            return self.send(403, {'error': '请刷新本地管理页后重试'})
        path = urlparse(self.path).path
        try:
            n = int(self.headers.get('Content-Length', '0'))
            limit = complete_backup.MAX_BYTES + 4096 if path == '/api/complete-preview' else MAX_BODY
            if n <= 0 or n > limit:
                raise ValueError('文件超过大小限制')
            data = json.loads(self.rfile.read(n))
            if jobs.status()['running']:
                raise ValueError('正在处理配置或选择文件夹，请等待完成后再修改')
            profile_backup.recover()
            if path == '/api/quit':
                self.send(200, {'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path not in POST_ROUTES:
                return self.send(404, {'error': 'Not found'})
            self.send_result(POST_ROUTES[path](data))
        except Exception as e:
            self.send_failure(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18761)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    profile_backup.recover()
    local_snapshots.on_upgrade(workflow.VERSION)
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    url = 'http://127.0.0.1:%d' % server.server_port
    print(url, flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
