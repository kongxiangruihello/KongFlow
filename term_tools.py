"""专业词库：从本机文稿中找出反复出现、但词库里还没有的词，并给出拼音供核对。

只读取所选文件夹中的 .txt、.md、.docx；全部在本机处理，不上传，不保存文稿内容。
"""
import collections, json, re, subprocess, zipfile
from pathlib import Path
import core

MAX_FILES = 2000
MAX_BYTES = 60 * 1024 * 1024
HAN = re.compile(r'[㐀-鿿\U00020000-\U000323af]+')
SUFFIXES = {'.txt', '.md', '.markdown', '.docx'}
_KNOWN = None
# Function characters that rarely begin or end a name or term.
EDGE_STOP = set('的了是在和与及也而之其于以为不有就都把被这那个们着过吗呢吧啊又或所则即乃且并从对向到给让使等')
_READINGS = None


def _dict_rows(path):
    """Yield (word, pinyin, weight) from a Rime .dict.yaml (after the '...' header)."""
    body = False
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not body:
                body = line.startswith('...')
                continue
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2:
                weight = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 0
                yield parts[0], parts[1], weight


def known_words():
    global _KNOWN
    if _KNOWN is None:
        words = set()
        base = core.ROOT / 'vendor/rime-ice/cn_dicts'
        for name in ('8105', 'base', 'ext', 'tencent'):
            path = base / f'{name}.dict.yaml'
            if path.exists():
                words.update(w for w, _, _ in _dict_rows(path))
        _KNOWN = words
    return _KNOWN


def compound(word, known):
    """True when the word is just two dictionary words of two or more characters (中国思想)."""
    return any(word[:i] in known and word[i:] in known for i in range(2, len(word) - 1))


def readings():
    """Most frequent reading of each character, from the 8105/41448 character tables."""
    global _READINGS
    if _READINGS is None:
        best = {}
        for name in ('41448', '8105'):  # 8105 last so common-character weights win
            path = core.ROOT / f'vendor/rime-ice/cn_dicts/{name}.dict.yaml'
            if not path.exists():
                continue
            for word, pinyin, weight in _dict_rows(path):
                if len(word) == 1 and (word not in best or weight >= best[word][1] or name == '8105' and best[word][2] != '8105'):
                    best[word] = (pinyin, weight, name)
        _READINGS = {k: v[0] for k, v in best.items()}
    return _READINGS


def pinyin_of(word):
    table = readings()
    parts = [table.get(ch) for ch in word]
    return ' '.join(parts) if all(parts) else ''


def read_text(path):
    if path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'ignore')
        xml = re.sub(r'</w:p>', '\n', xml)
        return re.sub(r'<[^>]+>', '', xml)
    raw = path.read_bytes()
    for encoding in ('utf-8', 'gb18030', 'utf-16'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('无法识别文字编码')


def files_in(folder):
    found = []
    for path in sorted(folder.rglob('*')):
        if any(part.startswith('.') for part in path.relative_to(folder).parts):
            continue
        if path.is_file() and path.suffix.lower() in SUFFIXES and not path.name.startswith('~$'):
            found.append(path)
            if len(found) >= MAX_FILES:
                break
    return found


def scan(folder, limit=300):
    import math
    folder = Path(str(folder)).expanduser()
    if not folder.is_dir():
        raise ValueError('文件夹不存在')
    texts = []
    skipped = total = 0
    for path in files_in(folder):
        try:
            size = path.stat().st_size
            if total + size > MAX_BYTES:
                break
            texts.append(read_text(path))
        except Exception:
            skipped += 1
            continue
        total += size
    runs = [m.group() for text in texts for m in HAN.finditer(text)]
    counts = collections.Counter()
    for run in runs:
        for n in range(1, 7):
            for i in range(len(run) - n + 1):
                counts[run[i:i + n]] += 1
    chars = sum(len(r) for r in runs) or 1
    known = known_words()
    mine = {r['word'] for r in core.state()['personal']}

    def cohesive(g):
        # Pointwise mutual information of the weakest split: a term's parts occur together far more than by chance.
        worst = min(counts[g[:i]] * counts[g[i:]] for i in range(1, len(g)))
        # Small collections cannot show strong association, so ask for less there.
        return math.log(chars * counts[g] / worst) >= (3.0 if chars > 20000 else 2.0)

    candidates = {g: c for g, c in counts.items()
                  if len(g) >= 2 and c >= (2 if len(g) >= 4 else 3) and g not in known and g not in mine
                  and g[0] not in EDGE_STOP and g[-1] not in EDGE_STOP and not compound(g, known) and cohesive(g)}
    # Second pass, candidates only: a term should be used in varied surroundings
    # (several different characters, or a text boundary, on each side).
    sides = {g: (set(), set()) for g in candidates}
    for run in runs:
        for n in range(2, 7):
            for i in range(len(run) - n + 1):
                g = run[i:i + n]
                if g in sides:
                    left, right = sides[g]
                    if len(left) < 3: left.add(run[i - 1] if i > 0 else '^')
                    if len(right) < 3: right.add(run[i + n] if i + n < len(run) else '$')
    free = {g: c for g, c in candidates.items() if len(sides[g][0]) >= 2 and len(sides[g][1]) >= 2}
    # Keep a phrase only when no kept longer phrase containing it occurs about as often
    # (so 王阳明 wins over 王阳 and 阳明 when they always appear together).
    kept, covered = [], {}
    for gram, count in sorted(free.items(), key=lambda x: -len(x[0])):
        if covered.get(gram, -10) + 1 >= count:
            continue
        kept.append((gram, count))
        for i in range(len(gram)):
            for j in range(i + 2, len(gram) + 1):
                sub = gram[i:j]
                if sub != gram:
                    covered[sub] = max(covered.get(sub, 0), count)
    kept.sort(key=lambda x: (-x[1] * len(x[0]), x[0]))
    contexts = {}
    wanted = {g for g, _ in kept[:limit]}
    for text in texts:
        for g in list(wanted - contexts.keys()):
            i = text.find(g)
            if i >= 0:
                contexts[g] = text[max(0, i - 12):i + len(g) + 12].replace('\n', ' ').strip()
    terms = [{'word': g, 'count': c, 'pinyin': pinyin_of(g), 'context': contexts.get(g, '')} for g, c in kept[:limit]]
    return {'files': len(texts), 'skipped': skipped, 'terms': terms}


def add(items):
    if not isinstance(items, list) or len(items) > 1000:
        raise ValueError('词语列表无效')
    s = core.state()
    existing = {(r['word'], r['pinyin']) for r in s['personal']}
    added = skipped = 0
    for item in items:
        row = core.normalize(item.get('word', ''), item.get('pinyin', ''), 1000)
        if (row['word'], row['pinyin']) in existing:
            skipped += 1
            continue
        s['personal'].append(row)
        existing.add((row['word'], row['pinyin']))
        added += 1
    if added:
        core.save(s)
    return {'added': added, 'skipped': skipped}


def pick():
    helper = core.ROOT / 'choose-folder'
    if not helper.exists():
        raise ValueError('请使用完整 Mac 应用选择文件夹，或在旁边输入文件夹路径')
    result = subprocess.run([str(helper), '选择文稿文件夹', '选择包含讲稿、文稿的文件夹（.txt、.md、.docx）。', '提取专业词'],
                            capture_output=True, text=True, timeout=300)
    if result.returncode == 2:
        return {'cancelled': True}
    if result.returncode:
        raise ValueError('文件夹选择未完成，请重试')
    return {'path': result.stdout.strip()}


def typing_stats(today=None):
    import datetime
    path = core.DATA / 'typing-stats.json'
    try:
        days = json.loads(path.read_text()).get('days', {})
    except (OSError, ValueError):
        days = {}
    today = today or datetime.date.today()
    def total(since):
        out = {'chars': 0, 'han': 0, 'commits': 0}
        for day, v in days.items():
            try:
                d = datetime.date.fromisoformat(day)
            except ValueError:
                continue
            if since is None or d > today - datetime.timedelta(days=since):
                for k in out:
                    out[k] += int(v.get(k, 0))
        return out
    return {'days': len(days), 'today': total(1), 'week': total(7), 'month': total(30), 'total': total(None)}
