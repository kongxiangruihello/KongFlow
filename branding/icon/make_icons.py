"""Generate KongFlow icons: app icon (.icns + PNG) and the menu bar template (rime.pdf).

App icon (0.37): the raster artwork in KongFlow-icon-source.png (blue rounded tile, a ribbon
"K" with speed lines over a keyboard). This script cuts the tile out of its white
background, fits it to the macOS icon grid (824 px tile on a 1024 px canvas) and adds the
standard soft shadow. The menu bar icon is a monochrome template drawn to match it.
Requires: pip install pillow numpy scipy cairosvg
Usage: python3 branding/icon/make_icons.py
"""
from pathlib import Path
import io
import cairosvg
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

HERE = Path(__file__).resolve().parent
BRANDING = HERE.parent
SOURCE = HERE / 'KongFlow-icon-source.png'

# Menu bar input-source icon: 18x18 pt template (black on transparent; macOS tints it).
# The same K with two speed lines; the keyboard is left out so it stays legible.
MENU_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="18pt" height="18pt" viewBox="0 0 18 18">
<rect x="2.2" y="2.2" width="3.4" height="13.6" rx="1.2" fill="#000"/>
<g fill="none" stroke="#000" stroke-linecap="round" stroke-width="2.4">
<path d="M12.6 3.2 L6.4 9.6"/>
<path d="M8.4 8.9 L13 14.8"/>
</g>
<g fill="none" stroke="#000" stroke-linecap="round" stroke-width="1.3">
<path d="M11.6 7.6 H16.6"/>
<path d="M12.6 10 H15.6"/>
</g></svg>'''


def cut_out(path):
    """Return the tile as RGBA, with the white page around it made transparent."""
    a = np.array(Image.open(path).convert('RGB')).astype(float)
    labels, _ = ndimage.label(a.min(axis=2) > 200)
    edge = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    edge.discard(0)
    inside = ~np.isin(labels, list(edge))
    # Anti-aliased rim: estimate coverage from how far the pixel is blended toward white.
    band = ndimage.binary_dilation(inside, iterations=3) & ~ndimage.binary_erosion(inside, iterations=3)
    alpha = inside.astype(float)
    alpha[band] = np.clip((255 - a[..., 1]) / 180, 0, 1)[band]
    alpha[alpha < 0.08] = 0
    rim = (alpha > 0) & (alpha < 1)
    for c in range(3):
        ch = a[..., c]
        ch[rim] = np.clip((ch[rim] - (1 - alpha[rim]) * 255) / alpha[rim], 0, 255)
    ys, xs = np.where(alpha > 0)
    tile = Image.fromarray(np.dstack([a, alpha * 255]).astype('uint8'), 'RGBA')
    tile = tile.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    side = max(tile.size)
    square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    square.paste(tile, ((side - tile.width) // 2, (side - tile.height) // 2))
    return square


def app_icon():
    tile = cut_out(SOURCE).resize((824, 824), Image.LANCZOS)
    shadow = Image.new('RGBA', (1024, 1024), (11, 31, 77, 0))
    shadow.paste((11, 31, 77, 255), (100, 110), tile.split()[3].point(lambda v: int(v * 0.28)))
    icon = Image.alpha_composite(Image.new('RGBA', (1024, 1024)), shadow.filter(ImageFilter.GaussianBlur(14)))
    icon.alpha_composite(tile, (100, 100))
    return icon


def main():
    (HERE / 'KongFlow-menubar.svg').write_text(MENU_SVG)
    big = app_icon()
    big.save(HERE / 'KongFlow-icon-1024.png')
    big.save(BRANDING / 'KongFlow.icns', sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    cairosvg.svg2pdf(bytestring=MENU_SVG.encode(), write_to=str(BRANDING / 'rime.pdf'))
    Image.open(io.BytesIO(cairosvg.svg2png(bytestring=MENU_SVG.encode(), output_width=36, output_height=36))).save(HERE / 'KongFlow-menubar@2x.png')


if __name__ == '__main__':
    main()
