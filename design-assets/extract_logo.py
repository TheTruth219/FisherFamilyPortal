"""Extract the user's chosen shield, excluding the presentation sheet and text."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image

root = Path('/app')
source = Image.open(root / 'design-assets/fisher-logo-options.png').convert('L')
# Logo #2 is the upper-right symbol. The caption starts below y=250.
crop = source.crop((676, 89, 793, 247))
mask = crop.point(lambda value: 255 if value < 145 else 0)
bounds = mask.getbbox()
mask = mask.crop(bounds)
padded = Image.new('L', (mask.width + 12, mask.height + 12), 0)
padded.paste(mask, (6, 6))
bitmap = padded.point(lambda value: 0 if value else 255, mode='1')
bitmap_path = root / 'design-assets/shield-trace.pbm'
bitmap.save(bitmap_path)
svg_path = root / 'frontend/public/brand/fisher-shield.svg'
subprocess.run(['potrace', str(bitmap_path), '--svg', '--tight', '--turdsize', '4', '--alphamax', '0.65', '--opttolerance', '0.15', '--output', str(svg_path)], check=True)
ET.register_namespace('', 'http://www.w3.org/2000/svg')
svg = ET.parse(svg_path)
node = svg.getroot()
for metadata in list(node):
    if metadata.tag.endswith('metadata'):
        node.remove(metadata)
for group in node.iter('{http://www.w3.org/2000/svg}g'):
    group.set('fill', '#172c4d')
node.attrib.pop('width', None)
node.attrib.pop('height', None)
svg.write(svg_path, encoding='unicode')
# Transparent high-resolution raster copy of the same extracted mark.
rgba = Image.new('RGBA', padded.size, (23, 44, 77, 0))
rgba.putalpha(padded)
rgba.resize((padded.width * 4, padded.height * 4), Image.Resampling.LANCZOS).save(root / 'frontend/public/brand/fisher-shield.png')
print('Extracted logo #2; original symbol bounds:', bounds, '; SVG viewBox:', node.get('viewBox'))
