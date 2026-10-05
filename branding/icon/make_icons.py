"""Generate KongFlow icons from SVG: app icon (.icns + PNG) and the menu bar template (rime.pdf).

Design "光标 K": the K's stem is a text cursor (I-beam), with a flowing line beneath,
on the blue base shared by the Kong app family. Requires: pip install cairosvg pillow
Usage: python3 branding/icon/make_icons.py
"""
from pathlib import Path
import io
import cairosvg
from PIL import Image

HERE = Path(__file__).resolve().parent
BRANDING = HERE.parent

APP_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4C82F2"/><stop offset="1" stop-color="#2F63DE"/></linearGradient>
<filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#0b1f4d" flood-opacity="0.28"/></filter></defs>
<rect x="100" y="100" width="824" height="824" rx="186" fill="url(#g)" filter="url(#s)"/>
<g fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round" stroke-width="56">
<path d="M330 290 H414 M372 290 V650 M330 650 H414"/>
<path d="M660 290 L372 520"/>
<path d="M468 443 L660 640"/>
<path d="M300 760 C390 715, 470 715, 560 760 S730 805, 820 760" stroke-width="40" opacity="0.85"/>
</g></svg>'''

# Menu bar input-source icon: 18x18 pt template (black on transparent; macOS tints it).
# Same cursor-K, without the wave so it stays legible at menu bar size.
MENU_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="18pt" height="18pt" viewBox="0 0 18 18">
<g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8">
<path d="M2.6 2.4 H6.8 M4.7 2.4 V15.6 M2.6 15.6 H6.8"/>
<path d="M15.2 2.4 L4.9 10.6"/>
<path d="M8.6 7.7 L15.4 15.6"/>
</g></svg>'''

def png(svg, size):
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size))).convert('RGBA')

def main():
    (HERE / 'KongFlow-icon.svg').write_text(APP_SVG)
    (HERE / 'KongFlow-menubar.svg').write_text(MENU_SVG)
    big = png(APP_SVG, 1024)
    big.save(HERE / 'KongFlow-icon-1024.png')
    big.save(BRANDING / 'KongFlow.icns', sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    cairosvg.svg2pdf(bytestring=MENU_SVG.encode(), write_to=str(BRANDING / 'rime.pdf'))
    png(MENU_SVG, 36).save(HERE / 'KongFlow-menubar@2x.png')

if __name__ == '__main__':
    main()
