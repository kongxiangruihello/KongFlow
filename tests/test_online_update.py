"""在线更新：版本选择、下载校验、打开安装程序、后台任务。全部离线，不访问网络。"""

import hashlib, io, plistlib, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core, jobs, online_update, update_check, version

PAYLOAD = b'KongFlow disk image ' * 4096
SHA = hashlib.sha256(PAYLOAD).hexdigest()


def release(tag='0.50', name='KongFlow-0.50.dmg', digest='sha256:' + SHA, size=len(PAYLOAD), preview=False):
    """Shaped like GitHub's releases API (the real 0.39 release has tag "0.39" and one DMG asset)."""
    return {
        'tag_name': tag,
        'draft': False,
        'prerelease': preview,
        'html_url': update_check.REPO + '/releases/tag/' + tag,
        'assets': [
            {
                'state': 'uploaded',
                'name': name,
                'size': size,
                'digest': digest,
                'browser_download_url': update_check.REPO + '/releases/download/' + tag + '/' + name,
            }
        ],
    }


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Opener:
    def __init__(self, data=PAYLOAD):
        self.data, self.requests = data, []

    def open(self, request, timeout=None):
        self.requests.append(request.full_url)
        return Response(self.data)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = core.DATA
        core.DATA = Path(self.tmp.name) / 'data'
        self.version_patch = patch.object(update_check.workflow, 'VERSION', '0.40.0')
        self.version_patch.start()
        self.asset = update_check.select([release()])['asset']

    def tearDown(self):
        self.version_patch.stop()
        core.DATA = self.old
        self.tmp.cleanup()


class SelectTests(Base):
    def test_dmg_only_release_is_found_and_installable(self):
        r = update_check.select([release()])
        self.assertTrue(r['available'])
        self.assertTrue(r['installable'])
        self.assertEqual(
            r['asset'],
            {
                'name': 'KongFlow-0.50.dmg',
                'size': len(PAYLOAD),
                'sha256': SHA,
                'url': update_check.REPO + '/releases/download/0.50/KongFlow-0.50.dmg',
            },
        )

    def test_zip_only_release_is_available_but_not_installable(self):
        r = update_check.select([release('v0.50.0', 'KongFlow-0.50-Mac.zip')])
        self.assertTrue(r['available'])
        self.assertFalse(r['installable'])
        self.assertIsNone(r['asset'])

    def test_not_installable_without_a_usable_checksum_or_size(self):
        for kind, row in {
            'no digest': release(digest=None),
            'short digest': release(digest='sha256:abc'),
            'other algorithm': release(digest='md5:' + '0' * 32),
            'too large': release(size=update_check.MAX_INSTALLER + 1),
        }.items():
            r = update_check.select([row])
            self.assertTrue(r['available'], kind)
            self.assertFalse(r['installable'], kind)

    def test_current_or_older_release_offers_nothing(self):
        for tag in ('0.40', '0.39'):
            r = update_check.select([release(tag, 'KongFlow-%s.dmg' % tag)])
            self.assertFalse(r['available'])
            self.assertFalse(r['installable'])
        self.assertFalse(update_check.select([])['installable'])

    def test_foreign_asset_link_is_ignored(self):
        row = release()
        row['assets'][0]['browser_download_url'] = 'https://example.com/KongFlow-0.50.dmg'
        self.assertFalse(update_check.select([row])['available'])

    def test_version_parsing_is_shared(self):
        self.assertEqual(version.parse('v0.41'), (0, 41, 0))
        self.assertEqual(version.parse('0.41.2'), (0, 41, 2))
        self.assertIsNone(version.parse('0.41/../x'))
        self.assertEqual(version.parse(version.VERSION)[:2], version.parse(version.SHORT)[:2])


class DownloadTests(Base):
    def test_download_is_verified_and_kept(self):
        seen = []
        opener = Opener()
        path = online_update.download(self.asset, lambda done, total: seen.append((done, total)), opener)
        self.assertEqual(path, core.DATA / 'updates' / 'KongFlow-0.50.dmg')
        self.assertEqual(path.read_bytes(), PAYLOAD)
        self.assertEqual(opener.requests, [self.asset['url']])
        self.assertEqual(seen[-1], (len(PAYLOAD), len(PAYLOAD)))
        self.assertEqual([p.name for p in path.parent.iterdir()], ['KongFlow-0.50.dmg'])

    def test_verified_download_is_reused(self):
        online_update.download(self.asset, opener=Opener())
        again = Opener()
        online_update.download(self.asset, opener=again)
        self.assertEqual(again.requests, [])

    def test_wrong_content_is_rejected_and_removed(self):
        for kind, data in {
            'altered': PAYLOAD[:-1] + b'!',
            'truncated': PAYLOAD[:-100],
            'longer': PAYLOAD + b'extra',
        }.items():
            with self.assertRaises(ValueError, msg=kind):
                online_update.download(self.asset, opener=Opener(data))
            self.assertEqual(list((core.DATA / 'updates').iterdir()), [], kind)

    def test_stale_file_with_the_same_name_is_replaced(self):
        folder = core.DATA / 'updates'
        folder.mkdir(parents=True)
        (folder / 'KongFlow-0.50.dmg').write_bytes(b'left over from an interrupted or older download')
        (folder / 'KongFlow-0.49.dmg').write_bytes(b'previous version')
        path = online_update.download(self.asset, opener=Opener())
        self.assertEqual(path.read_bytes(), PAYLOAD)
        self.assertEqual([p.name for p in folder.iterdir()], ['KongFlow-0.50.dmg'])

    def test_only_github_hosts_and_expected_names(self):
        self.assertTrue(online_update.allowed('https://github.com/kongxiangruihello/KongFlow/releases/download/x/y'))
        self.assertTrue(online_update.allowed('https://release-assets.githubusercontent.com/a?b=c'))
        for url in (
            'http://github.com/x',
            'https://github.com.example.com/x',
            'https://examplegithubusercontent.com/x',
            'https://example.com/x',
            'file:///etc/hosts',
        ):
            self.assertFalse(online_update.allowed(url), url)
        with self.assertRaises(ValueError):
            online_update.GitHubOnly().redirect_request(None, None, 302, 'Found', {}, 'https://example.com/a.dmg')
        for bad in (dict(self.asset, url='https://example.com/a.dmg'), dict(self.asset, name='../evil.dmg')):
            opener = Opener()
            with self.assertRaises(ValueError):
                online_update.download(bad, opener=opener)
            self.assertEqual(opener.requests, [])

    def test_network_failure_is_reported_plainly(self):
        from urllib.error import URLError

        class Offline:
            def open(self, request, timeout=None):
                raise URLError('offline')

        with self.assertRaisesRegex(ValueError, '下载未完成'):
            online_update.download(self.asset, opener=Offline())
        self.assertEqual(list((core.DATA / 'updates').iterdir()), [])


class InstallerTests(Base):
    def volume(self, names=('安装KongFlow.pkg', '开始使用.txt')):
        mount = Path(self.tmp.name) / 'volume'
        mount.mkdir(exist_ok=True)
        for name in names:
            (mount / name).write_text('x')
        return mount

    def runner(self, mount, attach_code=0, fail_open_for=()):
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            if args[0].endswith('hdiutil'):
                out = plistlib.dumps({'system-entities': [{'dev-entry': '/dev/disk9'}, {'mount-point': str(mount)}]})
                return subprocess.CompletedProcess(args, attach_code, out, b'')
            if args[1].endswith(tuple(fail_open_for)) and fail_open_for:
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0, b'', b'')

        return run, calls

    def test_opens_the_package_inside_the_image(self):
        mount = self.volume()
        run, calls = self.runner(mount)
        message = online_update.open_installer(Path('/tmp/KongFlow-0.50.dmg'), run)
        self.assertEqual(calls[0][:4], ['/usr/bin/hdiutil', 'attach', '-readonly', '-plist'])
        self.assertEqual(calls[1], ['/usr/bin/open', str(mount / '安装KongFlow.pkg')])
        self.assertIn('安装程序已打开', message)

    def test_falls_back_to_showing_the_image(self):
        image = Path('/tmp/KongFlow-0.50.dmg')
        for kind, (mount, code) in {
            'attach failed': (self.volume(), 1),
            'no package': (self.volume(names=('开始使用.txt',)), 0),
        }.items():
            if kind == 'no package':
                (mount / '安装KongFlow.pkg').unlink()
            run, calls = self.runner(mount, code)
            message = online_update.open_installer(image, run)
            self.assertEqual(calls[-1], ['/usr/bin/open', str(image)], kind)
            self.assertIn('访达', message)

    def test_reports_the_path_when_nothing_can_be_opened(self):
        run, _ = self.runner(self.volume(), 1, fail_open_for=('.dmg',))
        with self.assertRaisesRegex(ValueError, 'KongFlow-0.50.dmg'):
            online_update.open_installer(Path('/tmp/KongFlow-0.50.dmg'), run)


class RunTests(Base):
    def test_full_flow_reports_progress(self):
        stages = []
        mount = Path(self.tmp.name) / 'volume'
        mount.mkdir()
        (mount / '安装KongFlow.pkg').write_text('x')

        def run(args, **kwargs):
            out = plistlib.dumps({'system-entities': [{'mount-point': str(mount)}]})
            return subprocess.CompletedProcess(args, 0, out, b'')

        info = dict(update_check.select([release()]), checked_at='now')
        with patch.object(update_check, 'check', return_value=info) as check:
            result = online_update.run(lambda stage, detail=None: stages.append((stage, detail)), True, Opener(), run)
        check.assert_called_once_with(True)
        self.assertEqual(result['version'], '0.50')
        self.assertEqual(Path(result['file']).read_bytes(), PAYLOAD)
        self.assertEqual(stages[0], ('update-check', None))
        self.assertIn(('update-download', 100), stages)
        self.assertEqual(stages[-1], ('update-open', None))

    def test_refuses_when_there_is_nothing_to_install(self):
        current = update_check.select([release('0.40', 'KongFlow-0.40.dmg')])
        archive = update_check.select([release('v0.50.0', 'KongFlow-0.50-Mac.zip')])
        for info, pattern in ((current, '最新版本'), (archive, '发布页')):
            opener = Opener()
            with patch.object(update_check, 'check', return_value=info):
                with self.assertRaisesRegex(ValueError, pattern):
                    online_update.run(opener=opener)
            self.assertEqual(opener.requests, [])

    def test_background_job_carries_result_and_errors(self):
        def wait():
            for _ in range(200):
                status = jobs.status()
                if not status['running']:
                    return status
                time.sleep(0.01)
            self.fail('job did not finish')

        with patch.object(online_update, 'run', return_value={'message': 'done'}) as run:
            started = jobs.start('update', include_preview=True)
            self.assertEqual(started['kind'], 'update')
            done = wait()
        self.assertEqual(run.call_args.kwargs, {'include_preview': True})
        self.assertEqual((done['stage'], done['result']), ('done', {'message': 'done'}))
        with patch.object(online_update, 'run', side_effect=ValueError('校验未通过')):
            jobs.start('update')
            failed = wait()
        self.assertEqual((failed['stage'], failed['error']), ('failed', '校验未通过'))


class PackagingTests(unittest.TestCase):
    def test_modules_ship_with_the_settings_app(self):
        source = (core.ROOT / 'build_integrated.py').read_text()
        for name in ('version.py', 'update_check.py', 'online_update.py'):
            self.assertIn("'%s'," % name, source)
        for path in core.ROOT.glob('*.py'):
            if path.name not in ('build_integrated.py', 'build_installer.py'):
                self.assertIn("'%s'," % path.name, source, '%s is not packaged' % path.name)

    def test_release_notes_exist_for_this_version(self):
        self.assertTrue((core.ROOT / 'docs/releases' / ('README-%s.md' % version.SHORT)).is_file())


if __name__ == '__main__':
    unittest.main()


class MenuTests(Base):
    """输入法菜单里的「检查更新…」与「有新版本…」（0.43）。"""

    def test_check_leaves_a_note_for_the_menu(self):
        import json

        body = json.dumps([release()]).encode()
        with patch.object(update_check, 'urlopen', lambda request, timeout=None: Response(body)):
            result = update_check.check()
        note = json.loads((core.DATA / 'update-status.json').read_text())
        self.assertEqual((note['available'], note['latest']), (True, '0.50'))
        self.assertEqual(note['checked_at'], result['checked_at'])

    def test_note_is_cleared_when_up_to_date(self):
        import json

        update_check.remember({'available': False, 'latest': version.SHORT, 'checked_at': 'now'})
        self.assertFalse(json.loads((core.DATA / 'update-status.json').read_text())['available'])

    def test_menu_and_settings_are_wired(self):
        from source_text import Source

        menu = Source(core.ROOT / 'client/sources/SquirrelInputController.swift')
        self.assertIn('NSMenuItem(title: "检查更新…", action: #selector(openUpdate)', menu)
        self.assertIn('openKongIMEManager(page: "update")', menu)
        # 「有新版本」排在菜单最前；「检查更新…」紧跟「设置…」。
        self.assertLess(menu.index('if let latest = pendingUpdate()'), menu.index('"输入状态：待确认"'))
        self.assertLess(menu.index('title: "设置…"'), menu.index('title: "检查更新…"'))
        self.assertLess(menu.index('title: "检查更新…"'), menu.index('title: "撤销上次候选调整"'))
        self.assertIn('"update"].contains(page)', Source(core.ROOT / 'Launcher.swift'))
        script = Source(core.ROOT / 'web/app.js')
        self.assertIn('window.openUpdateCheck = async () =>', script)
        self.assertIn("if (location.hash === '#update') await window.openUpdateCheck();", script)
