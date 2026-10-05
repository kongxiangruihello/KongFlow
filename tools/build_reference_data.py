"""Build KongFlow's reference data (runtime/*.tsv) from public sources.

Sources (downloaded by this script):
- Four Books text: chinese-poetry/chinese-poetry (MIT), 论语/lunyu.json and 四书五经/{daxue,zhongyong,mengzi}.json.
  Chapter and paragraph numbering follow that data (论语 has 20 篇, 512 章, matching 杨伯峻《论语译注》).
- Era names: ytliu0/ChineseCalendar era_names.html (GPL-3.0), compiled from 萬國鼎《中國歷史紀年表》(中華書局, 1978).

Requires: pip install pypinyin opencc-python-reimplemented
Usage: python3 tools/build_reference_data.py [cache_dir]
"""
import html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path
import opencc
from pypinyin import lazy_pinyin, Style, load_phrases_dict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime'
POETRY = 'https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/'
ERAS = 'https://raw.githubusercontent.com/ytliu0/ChineseCalendar/master/era_names.html'
t2s = opencc.OpenCC('t2s')

# Readings that pypinyin gets wrong in these texts or era names.
load_phrases_dict({'不亦说乎': [['bù'], ['yì'], ['yuè'], ['hū']], '乾隆': [['qián'], ['lóng']], '乾德': [['qián'], ['dé']],
                   '乾元': [['qián'], ['yuán']], '乾封': [['qián'], ['fēng']], '乾符': [['qián'], ['fú']], '乾宁': [['qián'], ['níng']],
                   '乾化': [['qián'], ['huà']], '乾祐': [['qián'], ['yòu']], '乾亨': [['qián'], ['hēng']], '乾和': [['qián'], ['hé']],
                   '乾兴': [['qián'], ['xīng']], '乾道': [['qián'], ['dào']], '乾统': [['qián'], ['tǒng']], '乾贞': [['qián'], ['zhēn']]})

def to_simplified(text):
    # OpenCC turns 乾 into 干 in many era names (乾德, 乾祐…); keep 乾 as written.
    out = list(t2s.convert(text))
    for i, ch in enumerate(text):
        if ch == '乾' and i < len(out):
            out[i] = '乾'
    return ''.join(out)

def fetch(url, cache):
    path = Path(cache) / urllib.parse.quote(url, safe='')
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return path.read_text(encoding='utf-8')

def initials(text):
    han = ''.join(ch for ch in text if '㐀' <= ch <= '鿿' or '\U00020000' <= ch <= '\U0002ffff')
    return ''.join(p[0] for p in lazy_pinyin(han, style=Style.NORMAL, errors='ignore') if p)

def sentences(paragraph):
    """Split at sentence ends, keeping quotes balanced enough for quotation."""
    parts = re.findall(r'[^。！？]*[。！？][”’」』]*|[^。！？]+$', paragraph)
    return [p.strip() for p in parts if p.strip()]

def classics(cache):
    books = [('论语', '论语/lunyu.json'), ('大学', '四书五经/daxue.json'), ('中庸', '四书五经/zhongyong.json'), ('孟子', '四书五经/mengzi.json')]
    rows = []
    for book, path in books:
        data = json.loads(fetch(POETRY + urllib.parse.quote(path), cache))
        chapters = data if isinstance(data, list) else [data]
        for ci, chapter in enumerate(chapters, 1):
            name = t2s.convert(chapter['chapter']).removesuffix('篇')
            for pi, paragraph in enumerate(chapter['paragraphs'], 1):
                paragraph = t2s.convert(paragraph).replace('「', '“').replace('」', '”').replace('『', '‘').replace('』', '’')
                where = f'{book}·{name} {ci}.{pi}' if book in ('论语', '孟子') else f'{book} 第{pi}章'
                for text in sentences(paragraph):
                    # Index the sentence start and every clause start, so typing a quotation
                    # without its speaker (学而时习之 rather than 子曰) still finds it.
                    starts = [0] + [m.end() for m in re.finditer(r'[，；：、]', text)]
                    for rank, start in enumerate(starts):
                        piece = balance(text[start:])
                        code = initials(piece)
                        if len(code) >= 2:
                            rows.append((code, piece, where, 1 if rank == 0 else 2))
    seen, unique = set(), []
    for row in rows:
        if (row[0], row[1]) not in seen:
            seen.add((row[0], row[1])); unique.append(row)
    return unique

def balance(text):
    """Drop quotation marks left unpaired by cutting a sentence."""
    text = text.strip()
    for open_, close in (('“', '”'), ('‘', '’')):
        while text.startswith(open_) and close not in text: text = text[1:]
        while text.endswith(close) and open_ not in text: text = text[:-1]
        if text.count(open_) > text.count(close): text = text.replace(open_, '', text.count(open_) - text.count(close))
        if text.count(close) > text.count(open_): text = text[::-1].replace(close, '', text.count(close) - text.count(open_))[::-1]
    return text.strip()

def years(text):
    m = re.fullmatch(r'(前)?(\d+)(?:[–\-—](前)?(\d+))?', text.replace(' ', ''))
    if not m:
        return None
    start = -int(m[2]) if m[1] else int(m[2])
    end = start if not m[4] else (-int(m[4]) if m[3] else int(m[4]))
    return start, end

DYNASTY_NAMES = {'续唐年号': '唐', '武周年号': '武周', '南明和明郑': '南明', '契丹、辽': '辽', '蒙古、元': '元'}
# Headings that name a dynasty only by its own name; the span tells which one is meant.
SAME_NAME = {('宋', 420): '南朝宋', ('齐', 479): '南齐', ('梁', 502): '南梁', ('陈', 557): '陈',
             ('梁', 907): '后梁', ('唐', 923): '后唐', ('晋', 936): '后晋', ('汉', 947): '后汉', ('周', 951): '后周'}

def dynasty_name(heading, start):
    m = re.match(r'([^(（]+)(?:[(（](\d+))?', heading)
    base, first = m[1], int(m[2]) if m[2] else None
    if (base, first) in SAME_NAME:
        return SAME_NAME[(base, first)]
    if base == '满洲、后金、清':
        return '后金' if start < 1636 else '清'
    return DYNASTY_NAMES.get(base, base)

def eras(cache):
    page = fetch(ERAS, cache)
    rows, dynasty = [], ''
    for part in re.split(r'(<h[23][^>]*>.*?</h[23]>)', page, flags=re.S):
        head = re.match(r'<h[23][^>]*>(.*?)</h[23]>', part, re.S)
        if head:
            dynasty = re.sub(r'<[^>]+>|\s', '', html.unescape(head[1]))
            continue
        for table in re.findall(r'<table>(.*?)</table>', part, re.S):
            trs = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.S)
            if not trs or '年號' not in trs[0]:
                continue
            ruler = ''
            for tr in trs[1:]:
                cells = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', c))).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
                idx = next((i for i, c in enumerate(cells) if years(c)), None)
                if idx is None or idx == 0:
                    continue
                era = cells[idx - 1]
                if idx >= 2:
                    ruler = cells[idx - 2] or ruler
                start, end = years(cells[idx])
                # Forms in the table: 建元(6) · 弘光 (七個月) · 天福元至六年 · 顯德元年 (new era)
                # and 永曆十六至三十七年 · 天福七至九年 (an era continued under a later ruler).
                m = (re.fullmatch(r'([^\s(（]+?)\s*[(（][^)）]*[)）]', era) or re.fullmatch(r'(\S+?)元(?:[至、，]\S*)?年', era))
                if not m:
                    c = re.fullmatch(r'(\S+?)[一二三四五六七八九十]+(?:至\S+)?年', era)
                    if c:
                        cont = to_simplified(c[1])
                        for k in range(len(rows) - 1, -1, -1):
                            if rows[k][0] == cont:
                                rows[k] = (cont, rows[k][1], max(rows[k][2], end), rows[k][3], rows[k][4])
                                break
                    continue  # rulers without an era name
                name = to_simplified(m[1])
                dyn = dynasty_name(t2s.convert(dynasty), start)
                rows.append((name, start, end, dyn, t2s.convert(ruler)))
    # One era may be listed in pieces (天祐元年 then 天祐(4)); merge touching pieces.
    merged = []
    for row in rows:
        for k, old in enumerate(merged):
            if old[0] == row[0] and old[3] == row[3] and row[1] <= old[2] + 1 and old[1] <= row[2] + 1:
                merged[k] = (old[0], min(old[1], row[1]), max(old[2], row[2]), old[3], old[4])
                break
        else:
            merged.append(row)
    return merged

def main():
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/kongflow-data-cache')
    cache.mkdir(parents=True, exist_ok=True)
    cl = classics(cache)
    (OUT / 'kongflow_classics.tsv').write_text(''.join(f'{c}\t{t}\t{w}\t{r}\n' for c, t, w, r in cl), encoding='utf-8')
    er = eras(cache)
    lines = []
    for name, start, end, dyn, ruler in er:
        full = ''.join(lazy_pinyin(name, style=Style.NORMAL))
        lines.append(f'{full}\t{initials(name)}\t{name}\t{start}\t{end}\t{dyn}\t{ruler}\n')
    (OUT / 'kongflow_eras.tsv').write_text(''.join(lines), encoding='utf-8')
    print(len(cl), 'classic sentences;', len(er), 'era names')

if __name__ == '__main__':
    main()
