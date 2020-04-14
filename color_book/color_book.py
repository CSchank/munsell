import csv
import math
import operator
import sys
from PIL import Image, ImageDraw, ImageFont

# Column headers from UEF tables
s_colnames = [
    'h', 'V', 'C'
]

c_colnames = [
    'x', 'y', 'z', 'X', 'Y', 'Z',
    'R', 'G', 'B', 'L*', 'a*', 'b*',
    'u', 'v', 'u*', 'v*'
]

munsell_colnames = [
    '{}'.format(wavelength) for wavelength in range(400, 700+5, 5)
]

# Gamma correction for UEF data (see munsellpageaotf.m)
gamma = 0.5


# Page (color wheel) order
ordered_hues = [
    'N',
    '2.5R',
    '5R',
    '7.5R',
    '10R',
    '2.5YR',
    '5YR',
    '7.5YR',
    '10YR',
    '2.5Y',
    '5Y',
    '7.5Y',
    '10Y',
    '2.5GY',
    '5GY',
    '7.5GY',
    '10GY',
    '2.5G',
    '5G',
    '7.5G',
    '10G',
    '2.5BG',
    '5BG',
    '7.5BG',
    '10BG',
    '2.5B',
    '5B',
    '7.5B',
    '10B',
    '2.5PB',
    '5PB',
    '7.5PB',
    '10PB',
    '2.5P',
    '5P',
    '7.5P',
    '10P',
    '2.5RP',
    '5RP',
    '7.5RP',
    '10RP'
]

def cast(row, filter):
    parsed_row = dict()
    for k, v in row.items():
        parsed_row[k] = filter(k, v)
    return parsed_row

def clamped_rgb_gamma(value):
    clamped = max(0, min(value/100.0, 1.0))
    return max(0, min(int(round(math.pow(clamped, gamma) * 255.0)), 255))

def cast_uef(row, filter):
    color = cast(row, filter)
    color['dR'], color['dG'], color['dB'] = [clamped_rgb_gamma(color[key]) for key in ['R', 'G', 'B']]
    return color

def rit_filter(k, v):
    if k == 'h':
        return v
    elif k == 'V':
        return 10 * int(v)
    elif k in ['file order', 'C', 'dR', 'dG', 'dB']:
        return int(v)
    else:
        return float(v)

def new_color_source(name):
    if name == 'uef':
        return UEFColorSource(name)
    else:
        return RITColorSource(name)

def draw_text_ralign(draw, xy, text, font):
    (w, h) = draw.textsize(text, font = font)
    (x, y) = xy
    draw.text((x - w, y), text, font = font, fill = '#000000')


# Munsell value (*10) and dRGB value
neutrals = [
    ( 95, 243 ),
    ( 90, 232 ),
    ( 85, 220 ),
    ( 80, 203 ),
    ( 70, 179 ),
    ( 60, 150 ),
    ( 50, 124 ),
    ( 40, 97 ),
    ( 30, 70 ),
    ( 25, 59 ),
    ( 20, 48 ),
    ( 10, 28 )
]

neutral_colors = [{
        'h': 'N', 'V': v, 'C': 0,
        'dR': rgb_val, 'dG': rgb_val, 'dB': rgb_val
    } for (v, rgb_val) in neutrals]


class ColorSource:
    def __init__(self, name):
        self.name = name

    def read_data(self):
        raise Exception('Must use subclass!')

    def get_rgb(self, color):
        return [color[key] for key in ['dR', 'dG', 'dB']]

    def find_chroma(self, h, c):
        if h == 'N':
            return (0, '')
        found = next( ((x, label) for (x, c_test, label) in self.chroma_labels if c_test == c), None)
        return found

    def find_value(self, v):
        found = next( ((y, label) for (y, v_test, label) in self.value_labels if v_test == v), None)
        return found

    def location_on_page(self, color):
        h = color['h']
        v = color['V']
        c = color['C']
        found_c = self.find_chroma(h, c)
        if found_c is not None:
            (x, c_label) = found_c
            found_v = self.find_value(v)
            if found_v is not None:
                (y, v_label) = found_v
                return (x, y, v_label, c_label)
        return None

    # Get highest chromas
    def get_chroma_range(self, hue, value, max):
        chromas = [color for color in self.data
            if color['h'] == hue and color['V'] == value and self.find_chroma(hue, color['C']) is not None]
        chromas.sort(key = lambda x: x['C'])
        return chromas[-max:]

    def print_colors(self):
        for idx, color in enumerate(self.data):
            r, g, b = self.get_rgb(color)
            print('idx {} rgb {} hex {}'.format(idx, (color['R'], color['G'], color['B']), '#{:02X}{:02X}{:02X}'.format(r, g, b)))


class UEFColorSource(ColorSource):
    chroma_labels = [(idx, c, label) for idx, (c, label) in enumerate([
        (1, '/1 '),
        (2, '/2 '),
        (4, '/4 '),
        (6, '/6 '),
        (8, '/8 '),
        (10, '/10'),
        (12, '/12'),
        (14, '/14'),
        (16, '/16')
    ])]

    value_labels = [(idx, v, label) for idx, (v, label) in enumerate([
        (25, '2.5/'),
        (30, '  3/'),
        (40, '  4/'),
        (50, '  5/'),
        (60, '  6/'),
        (70, '  7/'),
        (80, '  8/'),
        (85, '8.5/'),
        (90, '  9/')
    ])]

    def read_data(self):
        with open('munsell400_700_5.munsell.csv') as munsell_file:
            filter = lambda k, v: v
            self.munsell = [cast(row, filter) for row in csv.DictReader(munsell_file)]

        with open('munsell400_700_5.s.csv') as s_file:
            filter = lambda k, v: int(v) if k in ['V', 'C'] else v
            s = [cast(row, filter) for row in csv.DictReader(s_file)]

        with open('munsell400_700_5.c.csv') as c_file:
            filter = lambda k, v: float(v)
            c = [cast_uef(row, filter) for row in csv.DictReader(c_file)]

        self.data = neutral_colors
        for i in range(0, len(s)):
            s_row = s[i]
            c_row = c[i]
            print('{}: s {} c {}'.format(i, s_row, c_row))
            s_row.update(c_row)
            self.data.append(s_row)


class RITColorSource(ColorSource):
    chroma_labels = [(idx, c, label) for idx, (c, label) in enumerate([
        (2, '/2 '),
        (4, '/4 '),
        (6, '/6 '),
        (8, '/8 '),
        (10, '/10'),
        (12, '/12'),
        (14, '/14'),
        (16, '/16'),
        (18, '/18'),
        (20, '/20')
    ])]

    value_labels = [(idx, v, label) for idx, (v, label) in enumerate([
        # (10, '  1/'),
        (20, '  2/'),
        (30, '  3/'),
        (40, '  4/'),
        (50, '  5/'),
        (60, '  6/'),
        (70, '  7/'),
        (80, '  8/'),
        # (85, '8.5/'),
        (90, '  9/')
    ])]

    def read_data(self):
        with open('rit_munsell.csv') as c_file:
            data = [cast(row, rit_filter) for row in csv.DictReader(c_file)]
        data.sort(key = operator.itemgetter('h', 'V', 'C'))
        self.data = neutral_colors + data


# Formats an 8 1/2 by 11 inch page in the Munsell book
class MunsellPage:
    # Page parameters for PIL
    dpi = 100
    image_w = 1100
    image_h = 850

    small_font_size = 18
    large_font_size = 32
    small_font = ImageFont.truetype('./RobotoMono-BoldItalic.ttf', small_font_size)
    large_font = ImageFont.truetype('./RobotoMono-BoldItalic.ttf', large_font_size)

    patch_x0 = 100
    value_label_x0 = patch_x0 - 50
    patch_w = 72
    patch_w_stride = patch_w + 12

    patch_y0 = image_h - 50
    chroma_label_y0 = patch_y0 + 15
    patch_h = 72
    patch_h_stride = patch_h + 12

    def __init__(self, source, hue):
        self.page_num = ordered_hues.index(hue) + 1
        self.h = hue
        self.source = source
        self.init_image()

    def init_image(self):
        self.img = Image.new('RGB', (self.image_w, self.image_h), color = 'white')
        self.draw = ImageDraw.Draw(self.img)

        x0 = self.patch_x0 + (len(self.source.chroma_labels) * self.patch_w_stride)
        y0 = self.patch_y0 - (len(self.source.value_labels) * self.patch_h_stride)
        # print('{} {}'.format((x0, y0), self.h))
        draw_text_ralign(self.draw, (x0, y0), self.h, self.large_font)
        draw_text_ralign(self.draw, (x0, y0 + 40), 'p. {}'.format(self.page_num), self.small_font)

        for (y, v, label) in self.source.value_labels:
            y0 = self.patch_y0 - self.patch_h - (y * self.patch_h_stride)
            # print('{} {}'.format((self.value_label_x0, y0), label))
            self.draw.text((self.value_label_x0, y0), label, font = self.small_font, fill = '#000000', align = 'left')

        if self.h != 'N':
            for (x, c, label) in self.source.chroma_labels:
                x0 = self.patch_x0 + (x * self.patch_w_stride)
                # print('{} {}'.format((x0, self.chroma_label_y0), label))
                self.draw.text((x0, self.chroma_label_y0), label, font = self.small_font, fill = '#000000', align = 'left')

    def add_patch(self, color):
        location = self.source.location_on_page(color)
        if location:
            (x, y, v_label, c_label) = location
            x0 = self.patch_x0 + (x * self.patch_w_stride)
            y0 = self.patch_y0 - (y * self.patch_h_stride)
            x1 = x0 + self.patch_w
            y1 = y0 - self.patch_h
            xy = [x0, y0, x1, y1]
            r, g, b = self.source.get_rgb(color)
            fill = '#{:02X}{:02X}{:02X}'.format(r, g, b)
            # print('spec{} idx {} xy {} fill {}'.format(spec, idx, xy, fill))
            self.draw.rectangle(xy, fill = fill)
        else:
            print('Patch {} {}/{} will not be printed'.format(color['h'], color['V'], color['C']))

    def print(self):
        file_name = '{}_{:03d}_{}.png'.format(self.source.name, self.page_num, self.h.replace(' ', '_'))
        self.img.save(file_name, dpi = (self.dpi, self.dpi))


# Formats a 4 by 6 1/2 inch card of one hue and value
class MunsellCard:
    # Card parameters for PIL
    dpi = 100
    image_w = 650
    image_h = 400

    small_font_size = 18
    small_font = ImageFont.truetype('./RobotoMono-BoldItalic.ttf', small_font_size)

    patch_x0 = 75
    patch_w = 120
    patch_w_stride = patch_w + 12

    patch_y0 = image_h - 60
    patch_h = 120
    patch_h_stride = patch_h + 50

    def __init__(self, source, hue, value):
        self.h = hue
        self.v = value
        self.source = source
        self.init_image()

    def init_image(self):
        self.img = Image.new('RGB', (self.image_w, self.image_h), color = 'white')
        self.draw = ImageDraw.Draw(self.img)

    def add_patches(self):
        chroma_range = self.source.get_chroma_range(hue, value, 8)
        if len(chroma_range) == 0:
            print('No patches found for {} {}'.format(self.h, self.v))
            return False

        for idx, color in enumerate(chroma_range):
            self.add_patch(idx, color)
        return True

    def add_patch(self, idx, color):
        (y, x) = divmod(idx, 4)
        x0 = self.patch_x0 + (x * self.patch_w_stride)
        y0 = self.patch_y0 - (y * self.patch_h_stride)
        x1 = x0 + self.patch_w
        y1 = y0 - self.patch_h
        xy = [x0, y0, x1, y1]
        r, g, b = self.source.get_rgb(color)
        fill = '#{:02X}{:02X}{:02X}'.format(r, g, b)
        # print('spec{} idx {} xy {} fill {}'.format(spec, idx, xy, fill))
        self.draw.rectangle(xy, fill = fill)
        (d, m) = divmod(color['V'], 10)
        v_str = str(d) if m == 0 else '{}.{}'.format(d, m)
        label = '{} {}/{}'.format(color['h'], v_str, color['C'])
        self.draw.text((x0, y0 + 10), label, font = self.small_font, fill = '#000000', align = 'left')

    def print(self):
        if self.add_patches():
            file_name = '{}c_{}_{}.png'.format(self.source.name, self.h.replace(' ', '_'), self.v)
            self.img.save(file_name, dpi = (self.dpi, self.dpi))


class Munsell:
    def __init__(self, source_name = 'rit'):
        self.source = new_color_source(source_name)
        self.current_hue = ''
        self.current_page = None
        self.source.read_data()

    def print_card(self, hue, value):
        card = MunsellCard(self.source, hue, value)
        card.print()

    def print_book(self):
        for idx, color in enumerate(self.source.data):
            hue = color['h']
            if hue != self.current_hue:
                if self.current_page is not None:
                    self.current_page.print()

                self.current_hue = color['h']
                self.current_page = MunsellPage(self.source, hue)
            self.current_page.add_patch(color)

        if self.current_page is not None:
            self.current_page.print()

if __name__ == '__main__':
    import argparse
    import re

    parser = argparse.ArgumentParser()
    parser.add_argument('--source', help='data source: rit or uef', default='rit')
    parser.add_argument('--card', help='output card for a specific hue and value, like 10YR 8')
    args = parser.parse_args()

    mun = Munsell(args.source)
    if args.card is not None:
        print('args.card {}'.format(args.card))
        m = re.match(r'([.0-9]+)\s*([A-Z]+)\s*([.0-9]+)', args.card)
        if m:
            hue = '{}{}'.format(m.group(1), m.group(2))
            value = int(round(float(m.group(3)) * 10.0))
            mun.print_card(hue, value)
        else:
            print('Bad card argument: {}'.format(args.card))
    else:
        mun.print_book()
