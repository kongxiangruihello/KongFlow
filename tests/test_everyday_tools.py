"""日常工具（0.42）：英文单词候选、错音错字提示、数字与金额大写、Unicode 码位输入。

前半部分检查生成的配置；RealEngineTests 用真实的 Rime 引擎读候选（macOS 用安装包里的 librime，
Linux 用系统的 librime），找不到引擎或编译器时跳过。
"""

import ctypes.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core, profile_backup

KEYS = ('english_words', 'correction_hints', 'number_capitals', 'unicode_input')
READY = (core.ROOT / 'vendor/rime-ice/rime_ice.schema.yaml').exists()


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = core.DATA, core.RIME
        self.root = Path(self.tmp.name)
        core.DATA = self.root / 'data'
        core.RIME = self.root / 'rime'

    def tearDown(self):
        core.DATA, core.RIME = self.old
        self.tmp.cleanup()

    def generated(self, **settings):
        s = core.state()
        s['settings'].update(settings)
        target = self.root / 'generated'
        core.generate(target, s)
        return target


class SettingsTests(Sandbox):
    def test_defaults_on_and_validated(self):
        s = core.normalize_settings({})
        self.assertEqual([s[k] for k in KEYS], [True] * 4)
        for key in KEYS:
            with self.assertRaises(ValueError):
                core.normalize_settings({key: 'yes'})

    def test_survive_backup_and_restore(self):
        s = core.state()
        s['settings'].update(english_words=False, unicode_input=False)
        core.save(s)
        profile_backup.restore(profile_backup.snapshot())
        restored = core.state()['settings']
        self.assertEqual([restored[k] for k in KEYS], [False, True, True, False])

    def test_settings_page_has_the_four_switches(self):
        html = (core.ROOT / 'web/index.html').read_text(encoding='utf-8')
        script = (core.ROOT / 'web/app.js').read_text(encoding='utf-8')
        for key in KEYS:
            control = key.replace('_', '-')
            self.assertIn('id="%s"' % control, html)
            self.assertIn("%s: $('#%s').checked" % (key, control), script)  # 保存
            self.assertIn("$('#%s').checked = v.%s !== false" % (control, key), script)  # 读取
            self.assertIn('#' + control + ',', script)  # 改动后自动保存


class SchemaTests(Sandbox):
    def schema(self, **settings):
        return (self.generated(**settings) / 'qingyan.schema.yaml').read_text(encoding='utf-8')

    def test_all_on(self):
        target = self.generated()
        schema = (target / 'qingyan.schema.yaml').read_text(encoding='utf-8')
        translators = next(x for x in schema.splitlines() if x.startswith('  translators:'))
        filters = next(x for x in schema.splitlines() if x.startswith('  filters:'))
        for name in ('table_translator@melt_eng', 'table_translator@cn_en', '*unicode', '*number_translator'):
            self.assertIn(name, translators)
        # 拼音在英文之前；纠错最先看到带拼音的注释；压低短英文词在简繁转换之前。
        self.assertLess(translators.index('script_translator'), translators.index('table_translator@melt_eng'))
        self.assertTrue(filters.startswith('  filters: [lua_filter@*corrector, '))
        self.assertLess(filters.index('*reduce_english_filter'), filters.index('simplifier@traditionalize'))
        self.assertIn('dependencies: [melt_eng, radical_pinyin]', schema)
        self.assertIn('translator:\n  dictionary: qingyan\n  initial_quality: 1.2\n', schema)
        self.assertIn('    number: "^R[0-9]+[.]?[0-9]*$"\n    unicode: "^U[a-f0-9]+$"\n', schema)
        self.assertIn('  - cn_dicts/others\n', (target / 'qingyan.dict.yaml').read_text(encoding='utf-8'))

    def test_all_off_leaves_no_trace(self):
        target = self.generated(**{k: False for k in KEYS})
        schema = (target / 'qingyan.schema.yaml').read_text(encoding='utf-8')
        for text in ('melt_eng', 'cn_en', 'corrector', 'reduce_english', 'unicode', 'number', 'initial_quality: 1.2'):
            self.assertNotIn(text, schema)
        self.assertNotIn('others', (target / 'qingyan.dict.yaml').read_text(encoding='utf-8'))

    def test_each_switch_alone(self):
        marks = {
            'english_words': 'table_translator@melt_eng',
            'correction_hints': 'lua_filter@*corrector',
            'number_capitals': 'lua_translator@*number_translator',
            'unicode_input': 'lua_translator@*unicode',
        }
        for key in KEYS:
            schema = self.schema(**{k: k == key for k in KEYS})
            for other, mark in marks.items():
                (self.assertIn if other == key else self.assertNotIn)(mark, schema, key)

    def test_english_without_radical_lookup(self):
        self.assertIn('dependencies: [melt_eng]', self.schema(radical_lookup=False))

    def test_correction_keeps_the_pinyin_setting(self):
        shown = self.schema(show_pinyin=True)
        self.assertIn('spelling_hints: 99', shown)
        self.assertIn('keep_comments: true', shown)
        target = self.generated(show_pinyin=False)
        hidden = (target / 'qingyan.schema.yaml').read_text(encoding='utf-8')
        self.assertIn('spelling_hints: 8', hidden)
        self.assertIn('keep_comments: false', hidden)
        self.assertNotIn('xform/.*//"]', hidden)
        # 不显示拼音时，注释位置仍留给纠正提示。
        self.assertIn('[comment]', (target / 'squirrel.custom.yaml').read_text(encoding='utf-8'))

    def test_reference_tools_outrank_english(self):
        for name in ('kongflow_era.lua', 'kongflow_classics.lua'):
            self.assertIn('cand.quality = 2', (core.ROOT / 'runtime' / name).read_text(encoding='utf-8'))


def engine():
    """(compiler command, librime path), or None when a real engine is not available here."""
    payload = core.ROOT / 'branding/payload/Squirrel.app/Contents/Frameworks/librime.1.dylib'
    if sys.platform == 'darwin' and payload.exists() and shutil.which('xcrun'):
        return ['xcrun', 'clang++'], str(payload)
    name = ctypes.util.find_library('rime')
    if sys.platform.startswith('linux') and name and shutil.which('g++') and shutil.which('rime_deployer'):
        return ['g++'], name
    return None


@unittest.skipUnless(READY and engine(), '需要雾凇词库与可用的 Rime 引擎')
class RealEngineTests(Sandbox):
    DICT = (
        '---\nname: qingyan\nversion: "1.0"\nsort: by_weight\n...\n'
        '你好\tni hao\t100\n你\tni\t100\n好\thao\t100\n我们\two men\t100\n我\two\t50\n们\tmen\t50\n'
        '按耐\tan nai\t100\n按\tan\t50\n给予\tgei yu\t100\n给\tgei\t50\n思想\tsi xiang\t100\n'
    )
    INPUTS = ['nihao', 'women', 'hello', 'github', 'annai', 'geiyu', 'R123', 'U62fc', 'is', 'ikx20', 'vxesx']

    def candidates(self, **settings):
        compiler, library = engine()
        tool = self.root / 'everyday-smoke'
        if not tool.exists():
            subprocess.run(
                compiler
                + ['-std=c++17', '-O2', '-I', str(core.ROOT / 'client/librime/src')]
                + [str(core.ROOT / 'tests/EverydaySmoke.cpp'), '-o', str(tool)]
                + ([] if sys.platform == 'darwin' else ['-ldl']),
                check=True,
                capture_output=True,
            )
        s = core.state()
        s['settings'].update(settings)
        target = self.root / ('rime-%d' % len(list(self.root.glob('rime-*'))))
        core.make_bundle(target, s)
        (target / 'qingyan.dict.yaml').write_text(self.DICT, encoding='utf-8')
        result = subprocess.run(
            [str(tool), library, str(target)] + self.INPUTS, capture_output=True, text=True, timeout=300
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = {}
        for line in result.stdout.splitlines():
            code, *cells = line.split('\t')
            rows[code] = [tuple(c.split('|', 1)) for c in cells]
        self.assertEqual(sorted(rows), sorted(self.INPUTS), result.stdout)
        return rows

    def test_tools_on(self):
        c = self.candidates()
        self.assertEqual(c['nihao'][0], ('你好', 'ni hao'))  # 拼音与注释照旧
        self.assertEqual(c['women'][0][0], '我们')  # 中文在同码英文之前
        self.assertIn('women', [text for text, _ in c['women']])
        self.assertEqual(c['hello'][0][0], 'hello')
        self.assertEqual(c['github'][0][0], 'GitHub')
        self.assertEqual(c['annai'][0][0], '按耐')
        self.assertIn('按捺', c['annai'][0][1])  # 错字提示
        self.assertEqual(c['geiyu'][0], ('给予', 'jǐ yǔ'))  # 错音提示
        self.assertEqual(c['R123'][0][0], '一百二十三')
        self.assertIn('壹佰贰拾叁元整', [text for text, _ in c['R123']])
        self.assertEqual(c['U62fc'][0][0], '拼')
        # 学术前缀不被英文单词抢先：is 仍先列年号（始元），其后才是英文 is。
        self.assertEqual(c['is'][0][0], '始元')
        self.assertTrue(c['ikx20'][0][0].startswith('康熙二十年'))
        self.assertTrue(c['vxesx'][0][0].startswith('学而时习之'))

    def test_tools_off(self):
        c = self.candidates(**{k: False for k in KEYS})
        self.assertEqual(c['nihao'][0], ('你好', 'ni hao'))
        self.assertNotIn('hello', [text for text, _ in c['hello']])
        self.assertNotIn('按捺', c['annai'][0][1])
        self.assertEqual(c['geiyu'][0], ('给予', 'gei yu'))
        self.assertEqual(c['R123'], [])
        self.assertEqual(c['U62fc'], [])
        self.assertEqual(c['is'][0][0], '始元')

    def test_hints_without_pinyin_display(self):
        c = self.candidates(show_pinyin=False)
        self.assertEqual(c['nihao'][0], ('你好', ''))  # 拼音不显示
        self.assertIn('按捺', c['annai'][0][1])  # 提示仍在
        self.assertEqual(c['geiyu'][0], ('给予', 'jǐ yǔ'))


if __name__ == '__main__':
    unittest.main()
