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
# 0.43: a filled rounded tile with the K cut out of it, the same form as the system's own
# input-source icons (拼, A). One path, even-odd fill: the tile, then the outline of a K drawn
# with 2.1 pt round strokes (stem 6.1,4.6-6.1,13.4; arms 12.6,4.6-6.5,9.6 and 8.4,8.4-12.8,13.4),
# so the hole is real transparency in the PDF as well.
MENU_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="18pt" height="18pt" viewBox="0 0 18 18">
<path fill="#000" fill-rule="evenodd" d="M5.3 1.5H12.7A3.8 3.8 0 0 1 16.5 5.3V12.7A3.8 3.8 0 0 1 12.7 16.5H5.3A3.8 3.8 0 0 1 1.5 12.7V5.3A3.8 3.8 0 0 1 5.3 1.5Z
M7.15 10.42 L8.1 9.65 L12.01 14.09 L12.22 14.27 L12.46 14.39 L12.73 14.45 L13.01 14.43 L13.27 14.34 L13.49 14.19 L13.67 13.98 L13.79 13.74 L13.85 13.47 L13.83 13.19 L13.74 12.93 L13.59 12.71 L9.72 8.32 L13.27 5.41 L13.45 5.21 L13.58 4.97 L13.64 4.7 L13.64 4.43 L13.56 4.17 L13.41 3.93 L13.21 3.75 L12.97 3.62 L12.7 3.56 L12.43 3.56 L12.17 3.64 L11.93 3.79 L7.15 7.71 L7.15 4.6 L7.11 4.33 L7.01 4.07 L6.84 3.86 L6.62 3.69 L6.37 3.59 L6.1 3.55 L5.83 3.59 L5.58 3.69 L5.36 3.86 L5.19 4.07 L5.09 4.33 L5.05 4.6 L5.05 13.4 L5.09 13.67 L5.19 13.93 L5.36 14.14 L5.57 14.31 L5.83 14.41 L6.1 14.45 L6.37 14.41 L6.62 14.31 L6.84 14.14 L7.01 13.93 L7.11 13.67 L7.15 13.4Z"/></svg>"""


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


def menu_icon():
    (HERE / 'KongFlow-menubar.svg').write_text(MENU_SVG)
    cairosvg.svg2pdf(bytestring=MENU_SVG.encode(), write_to=str(BRANDING / 'rime.pdf'))
    Image.open(io.BytesIO(cairosvg.svg2png(bytestring=MENU_SVG.encode(), output_width=36, output_height=36))).save(
        HERE / 'KongFlow-menubar@2x.png'
    )


def main():
    menu_icon()
    big = app_icon()
    big.save(HERE / 'KongFlow-icon-1024.png')
    big.save(
        BRANDING / 'KongFlow.icns',
        sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
    )


if __name__ == '__main__':
    main()
