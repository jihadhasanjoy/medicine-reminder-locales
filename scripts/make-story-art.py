# Draws the Insights story pictures and animations, one scene per story:
#   stories/animations/<id>.json   a 4 s Lottie loop (30 fps, 800x480)
#   <svg dir>/<id>.svg             the same scene, still (frame 0)
#   python3 scripts/make-story-art.py [svg dir]
# The pictures in stories/images/ are those SVGs as 800x480 WebP, e.g.
#   npx sharp-cli -i <svg dir>/x.svg -o stories/images/x.webp
# The app plays the animation and falls back to the picture. Each scene is
# a list of layers made of flat shapes; a layer can move, turn, grow or
# fade over the loop. Edit a scene, run this, convert the pictures, then
# `node scripts/build-manifest.mjs`.
import json
import math
import os
import sys

FR, OP, W, H = 30, 120, 800, 480
ROOT = os.path.join(os.path.dirname(__file__), '..', 'stories')


def rgb(hex_color):
    h = hex_color.lstrip('#')
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


BG = '#EAF4FD'
BLUE = '#1E88E5'
BLUE_D = '#1565C0'
BLUE_L = '#90CAF9'
SKY = '#D4E9FB'
CORAL = '#FF7043'
CORAL_L = '#FFCCBC'
TEAL = '#26C6DA'
GREEN = '#2BB673'
GREEN_L = '#C8EBD7'
YELLOW = '#FFC845'
WHITE = '#FFFFFF'
INK = '#263445'
GREY = '#B0BEC5'
GREY_L = '#ECEFF1'
SKIN = '#F5C9A6'
HAIR = '#4E342E'
HAIR_GREY = '#CFD8DC'

K = 0.5523  # circle-to-bezier handle length


# ---- Shapes: everything becomes a bezier path (vertices, in, out). ----

def poly(points, closed=True):
    z = [[0, 0]] * len(points)
    return {'v': [list(p) for p in points], 'i': z, 'o': z, 'c': closed}


def ellipse(cx, cy, rx, ry=None):
    ry = rx if ry is None else ry
    return {'v': [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]],
            'i': [[-rx * K, 0], [0, -ry * K], [rx * K, 0], [0, ry * K]],
            'o': [[rx * K, 0], [0, ry * K], [-rx * K, 0], [0, -ry * K]], 'c': True}


def rrect(x, y, w, h, r=0):
    r = min(r, w / 2, h / 2)
    if r == 0:
        return poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    k = r * K
    v = [[x + r, y], [x + w - r, y], [x + w, y + r], [x + w, y + h - r],
         [x + w - r, y + h], [x + r, y + h], [x, y + h - r], [x, y + r]]
    i = [[-k, 0], [0, 0], [0, -k], [0, 0], [k, 0], [0, 0], [0, k], [0, 0]]
    o = [[0, 0], [k, 0], [0, 0], [0, k], [0, 0], [-k, 0], [0, 0], [0, -k]]
    return {'v': v, 'i': i, 'o': o, 'c': True}


def arc(cx, cy, r, a0, a1, steps=16):
    pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * s / steps)),
            cy + r * math.sin(math.radians(a0 + (a1 - a0) * s / steps))) for s in range(steps + 1)]
    return poly(pts, closed=False)


def heart(cx, cy, s):
    # From the bottom point round the left lobe, the dip, the right lobe.
    v = [[0, 0.95], [-1, -0.2], [-0.5, -0.9], [0, -0.5], [0.5, -0.9], [1, -0.2]]
    i = [[0.45, -0.35], [0, 0.4], [-0.32, 0], [-0.06, -0.28], [-0.32, 0], [0, -0.4]]
    o = [[-0.45, -0.35], [0, -0.4], [0.32, 0], [0.06, -0.28], [0.32, 0], [0, 0.4]]
    return {'v': [[cx + x * s, cy + y * s] for x, y in v], 'i': [[x * s, y * s] for x, y in i],
            'o': [[x * s, y * s] for x, y in o], 'c': True}


def turn(shape, deg, ox=0, oy=0):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)

    def p(x, y):
        return [ox + (x - ox) * c - (y - oy) * s, oy + (x - ox) * s + (y - oy) * c]

    def d(x, y):
        return [x * c - y * s, x * s + y * c]
    return {'v': [p(*v) for v in shape['v']], 'i': [d(*v) for v in shape['i']],
            'o': [d(*v) for v in shape['o']], 'c': shape['c']}


def fill(shape, color, opacity=100):
    return {'shape': shape, 'fill': color, 'opacity': opacity}


def line(shape, color, width, opacity=100):
    return {'shape': shape, 'stroke': color, 'width': width, 'opacity': opacity}


# ---- Reusable things. ----

def capsule(cx, cy, length, r, deg, c1, c2):
    b = length / 2 - r
    top = {'v': [[-r, 0], [-r, -b], [0, -b - r], [r, -b], [r, 0]],
           'i': [[0, 0], [0, 0], [-r * K, 0], [0, -r * K], [0, 0]],
           'o': [[0, 0], [0, -r * K], [r * K, 0], [0, 0], [0, 0]], 'c': True}
    bottom = {'v': [[-r, 0], [r, 0], [r, b], [0, b + r], [-r, b]],
              'i': [[0, 0], [0, 0], [0, 0], [r * K, 0], [0, r * K]],
              'o': [[0, 0], [0, 0], [0, r * K], [-r * K, 0], [0, 0]], 'c': True}
    shine = rrect(-r * 0.55, -b - r * 0.4, r * 0.28, b * 0.9, r * 0.14)

    def place(s):
        s = turn(s, deg)
        return {'v': [[x + cx, y + cy] for x, y in s['v']], 'i': s['i'], 'o': s['o'], 'c': s['c']}
    return [fill(place(top), c1), fill(place(bottom), c2), fill(place(shine), WHITE, 70)]


def tablet(cx, cy, r, color=WHITE):
    return [fill(ellipse(cx, cy + r * 0.12, r), GREY, 60), fill(ellipse(cx, cy, r), color),
            line(poly([(cx - r * 0.55, cy), (cx + r * 0.55, cy)], False), GREY, r * 0.14)]


def check_badge(r, color=GREEN):
    return [fill(ellipse(0, 0, r), color), line(ellipse(0, 0, r), WHITE, r * 0.16),
            line(poly([(-r * 0.42, 0.02 * r), (-r * 0.1, r * 0.34), (r * 0.45, -r * 0.3)], False),
                 WHITE, r * 0.2)]


def sparkle(cx, cy, s, color):
    b = s * 0.3
    return [fill(poly([(cx, cy - s), (cx + b, cy - b), (cx + s, cy), (cx + b, cy + b),
                       (cx, cy + s), (cx - b, cy + b), (cx - s, cy), (cx - b, cy - b)]), color)]


def person(body_color, head_r, hair=HAIR, hair_style='short'):
    # Centred on the neck: head above, shoulders below.
    items = [fill(rrect(-head_r * 1.9, head_r * 0.4, head_r * 3.8, head_r * 3.2, head_r * 1.5), body_color)]
    if hair_style == 'pigtails':
        items += [fill(ellipse(-head_r * 1.05, -head_r * 0.9, head_r * 0.42), hair),
                  fill(ellipse(head_r * 1.05, -head_r * 0.9, head_r * 0.42), hair)]
    items.append(fill(ellipse(0, -head_r * 0.8, head_r), SKIN))
    if hair_style in ('short', 'pigtails'):
        items.append(fill(ellipse(0, -head_r * 1.35, head_r * 0.98, head_r * 0.55), hair))
    elif hair_style == 'bun':
        items += [fill(ellipse(0, -head_r * 1.35, head_r * 0.98, head_r * 0.55), hair),
                  fill(ellipse(0, -head_r * 1.95, head_r * 0.42), hair)]
    items += [fill(ellipse(-head_r * 0.35, -head_r * 0.75, head_r * 0.1), INK),
              fill(ellipse(head_r * 0.35, -head_r * 0.75, head_r * 0.1), INK),
              line(arc(0, -head_r * 0.6, head_r * 0.35, 30, 150, 8), INK, head_r * 0.08)]
    return items


def backdrop(*blobs):
    items = [fill(rrect(0, 0, W, H), BG)]
    for cx, cy, r, color, opacity in blobs:
        items.append(fill(ellipse(cx, cy, r), color, opacity))
    return layer(items)


def shadow(cx, cy, rx, ry=None):
    return fill(ellipse(cx, cy, rx, ry or rx * 0.14), BLUE_D, 10)


# ---- Layers and motion. A motion is a function of t (0..1 over the loop). ----

def layer(items, at=(0, 0), move=None, scale=None, rotate=None, opacity=None, trim=None):
    return {'items': items, 'at': at, 'move': move, 'scale': scale, 'rotate': rotate,
            'opacity': opacity, 'trim': trim}


def placed(items, x, y, **motion):
    # A thing drawn around (0, 0), put at (x, y) and moving about there.
    return layer(shift(items, x, y), at=(x, y), **motion)


def wave(t, phase=0):
    return math.sin(2 * math.pi * (t + phase))


def bob(dy, phase=0):
    return lambda t: (0, dy * wave(t, phase))


def pulse(amount, phase=0):
    return lambda t: 100 + amount * (0.5 + 0.5 * wave(t, phase))


def swing(deg, phase=0):
    return lambda t: deg * wave(t, phase)


def beat(t):
    # Two quick beats, then rest: a heartbeat.
    x = t * 2 % 1
    return 100 + 14 * max(0, math.sin(math.pi * x / 0.25)) if x < 0.25 else 100


STEP = 4  # frames between sampled keyframes


def sampled(fn, wrap):
    keys = []
    for f in range(0, OP + 1, STEP):
        keys.append({'t': f, 's': wrap(fn(f / OP)),
                     'o': {'x': [0.33], 'y': [0.33]}, 'i': {'x': [0.67], 'y': [0.67]}})
    del keys[-1]['o'], keys[-1]['i']
    return {'a': 1, 'k': keys}


def static(v):
    return {'a': 0, 'k': v}


def lottie_shape(item, trim):
    s = item['shape']
    it = [{'ty': 'sh', 'ks': static({'c': s['c'], 'v': s['v'], 'i': s['i'], 'o': s['o']})}]
    if trim and 'stroke' in item:
        it.append({'ty': 'tm', 's': static(0), 'e': sampled(trim, lambda v: [v]), 'o': static(0), 'm': 1})
    if 'fill' in item:
        it.append({'ty': 'fl', 'c': static(rgb(item['fill']) + [1]), 'o': static(item['opacity']), 'r': 1})
    else:
        it.append({'ty': 'st', 'c': static(rgb(item['stroke']) + [1]), 'o': static(item['opacity']),
                   'w': static(item['width']), 'lc': 2, 'lj': 2})
    it.append({'ty': 'tr', 'p': static([0, 0]), 'a': static([0, 0]), 's': static([100, 100]),
               'r': static(0), 'o': static(100)})
    return {'ty': 'gr', 'it': it}


def xy(v):
    # A scale is one number, or (x, y) to stretch one way only.
    return list(v) if isinstance(v, tuple) else [v, v]


def to_lottie(name, layers):
    out = []
    for index, L in enumerate(layers):
        ax, ay = L['at']
        ks = {'a': static([ax, ay, 0]),
              'p': sampled(L['move'], lambda d: [ax + d[0], ay + d[1], 0]) if L['move'] else static([ax, ay, 0]),
              's': sampled(L['scale'], lambda v: [*xy(v), 100]) if L['scale'] else static([100, 100, 100]),
              'r': sampled(L['rotate'], lambda v: [v]) if L['rotate'] else static(0),
              'o': sampled(L['opacity'], lambda v: [v]) if L['opacity'] else static(100)}
        # Lottie draws the first layer on top: reverse the scene's order.
        out.insert(0, {'ddd': 0, 'ind': index + 1, 'ty': 4, 'nm': f'L{index}', 'sr': 1, 'ip': 0, 'op': OP,
                       'st': 0, 'bm': 0, 'ks': ks,
                       'shapes': [lottie_shape(item, L['trim']) for item in reversed(L['items'])]})
    return {'v': '5.7.4', 'fr': FR, 'ip': 0, 'op': OP, 'w': W, 'h': H, 'nm': name, 'ddd': 0,
            'assets': [], 'layers': out}


def svg_path(s):
    v, i, o = s['v'], s['i'], s['o']
    n = len(v)
    d = [f'M{v[0][0]:.1f} {v[0][1]:.1f}']
    for k in range(1, n + (1 if s['c'] else 0)):
        a, b = v[k - 1], v[k % n]
        c1 = (a[0] + o[k - 1][0], a[1] + o[k - 1][1])
        c2 = (b[0] + i[k % n][0], b[1] + i[k % n][1])
        d.append(f'C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {b[0]:.1f} {b[1]:.1f}')
    return ' '.join(d) + (' Z' if s['c'] else '')


def to_svg(layers):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    for L in layers:
        ax, ay = L['at']
        dx, dy = L['move'](0) if L['move'] else (0, 0)
        sx, sy = xy(L['scale'](0)) if L['scale'] else (100, 100)
        rot = L['rotate'](0) if L['rotate'] else 0
        op = (L['opacity'](0) if L['opacity'] else 100) / 100
        parts.append(f'<g opacity="{op:.2f}" transform="translate({ax + dx:.1f} {ay + dy:.1f}) '
                     f'rotate({rot:.1f}) scale({sx / 100:.3f} {sy / 100:.3f}) translate({-ax} {-ay})">')
        for item in L['items']:
            d = svg_path(item['shape'])
            a = item['opacity'] / 100
            if 'fill' in item:
                parts.append(f'<path d="{d}" fill="{item["fill"]}" fill-opacity="{a:.2f}"/>')
            else:
                parts.append(f'<path d="{d}" fill="none" stroke="{item["stroke"]}" stroke-opacity="{a:.2f}" '
                             f'stroke-width="{item["width"]}" stroke-linecap="round" stroke-linejoin="round"/>')
        parts.append('</g>')
    parts.append('</svg>')
    return '\n'.join(parts)


# ---- The scenes. ----

def clock(cx, cy, r):
    face = [shadow(cx, cy + r + 18, r * 0.8), fill(ellipse(cx, cy, r + 10), BLUE),
            fill(ellipse(cx, cy, r), WHITE)]
    for h in range(12):
        a = math.radians(h * 30)
        size = r * (0.07 if h % 3 == 0 else 0.04)
        face.append(fill(ellipse(cx + math.sin(a) * r * 0.8, cy - math.cos(a) * r * 0.8, size), BLUE_L if h % 3 else BLUE))
    return [layer(face),
            layer([line(poly([(cx, cy), (cx, cy - r * 0.48)], False), INK, r * 0.08)],
                  at=(cx, cy), rotate=lambda t: 120 + 30 * t),
            layer([line(poly([(cx, cy), (cx, cy - r * 0.7)], False), CORAL, r * 0.05)],
                  at=(cx, cy), rotate=lambda t: 360 * t),
            layer([fill(ellipse(cx, cy, r * 0.08), INK)])]


def on_time():
    return [backdrop((140, 90, 120, WHITE, 60), (700, 400, 160, SKY, 100)),
            *clock(320, 230, 125),
            layer([shadow(565, 395, 60)], at=(565, 395), scale=pulse(-12)),
            layer(capsule(565, 230, 170, 34, 35, BLUE, CORAL), at=(565, 230), move=bob(14), rotate=swing(4)),
            placed(check_badge(34), 640, 330, scale=pulse(10, 0.25)),
            layer(sparkle(470, 110, 14, YELLOW), at=(470, 110), scale=pulse(35)),
            layer(sparkle(690, 140, 10, TEAL), at=(690, 140), scale=pulse(40, 0.5))]


def missed_dose():
    x, y, w, h = 210, 90, 380, 300
    card = [shadow(400, 410, 170), fill(rrect(x, y, w, h, 28), WHITE), fill(rrect(x, y, w, 70, 28), BLUE),
            fill(rrect(x, y + 40, w, 30), BLUE), fill(rrect(x + 80, y - 18, 16, 44, 8), BLUE_D),
            fill(rrect(x + w - 96, y - 18, 16, 44, 8), BLUE_D)]
    dots = []
    for row in range(3):
        for col in range(5):
            cx, cy = x + 62 + col * 64, y + 120 + row * 66
            if (row, col) == (1, 3):
                continue
            done = row * 5 + col < 11
            dots.append(fill(ellipse(cx, cy, 20), GREEN if done else GREY_L))
            if done:
                dots.append(line(poly([(cx - 8, cy), (cx - 2, cy + 6), (cx + 9, cy - 6)], False), WHITE, 4))
    mx, my = x + 62 + 3 * 64, y + 120 + 66
    return [backdrop((690, 100, 130, WHITE, 60), (110, 400, 150, SKY, 100)),
            layer(card + dots),
            layer([line(ellipse(mx, my, 20), CORAL, 5), fill(ellipse(mx, my, 6), CORAL)],
                  at=(mx, my), scale=pulse(18), opacity=lambda t: 70 + 30 * wave(t)),
            layer(capsule(650, 300, 120, 24, -40, BLUE, CORAL), at=(650, 300), move=bob(10, 0.2), rotate=swing(8)),
            placed([fill(ellipse(0, 0, 26), YELLOW), fill(rrect(-4, -15, 8, 18, 4), INK), fill(ellipse(0, 11, 4.5), INK)],
                   640, 160, scale=pulse(12, 0.5))]


def with_food():
    cx, cy = 340, 280
    plate = [shadow(cx, cy + 128, 150), fill(ellipse(cx, cy, 140), WHITE), line(ellipse(cx, cy, 104), GREY_L, 6),
             fill(ellipse(cx - 30, cy - 15, 40), GREEN), fill(ellipse(cx + 34, cy + 22, 30), CORAL),
             fill(ellipse(cx + 20, cy - 40, 22), YELLOW), fill(ellipse(cx - 18, cy + 45, 20), CORAL_L)]
    cutlery = [fill(rrect(150, 170, 14, 220, 7), GREY), fill(rrect(142, 150, 30, 70, 10), GREY),
               fill(rrect(516, 160, 16, 230, 8), GREY), fill(rrect(512, 150, 24, 90, 12), GREY)]
    return [backdrop((680, 90, 140, WHITE, 60), (120, 80, 90, SKY, 100)),
            layer(cutlery + plate),
            layer(capsule(650, 150, 140, 28, 25, BLUE, CORAL), at=(650, 150), move=bob(16), rotate=swing(6)),
            *clock(650, 340, 50)]


def full_course():
    x, y, w, h = 200, 90, 380, 230
    pack = [shadow(390, 340, 180), fill(rrect(x, y, w, h, 26), BLUE_L), fill(rrect(x + 12, y + 12, w - 24, h - 24, 18), SKY)]
    for row in range(2):
        for col in range(5):
            cx, cy = x + 62 + col * 64, y + 72 + row * 88
            if row == 0 and col < 3:
                pack.append(line(ellipse(cx, cy, 24), BLUE_L, 4))
            else:
                pack += tablet(cx, cy, 24)
    bar = [fill(rrect(200, 380, 380, 22, 11), WHITE)]
    return [backdrop((120, 410, 140, SKY, 100), (700, 80, 120, WHITE, 60)),
            layer(pack),
            layer(tablet(x + 62 + 3 * 64, y + 72, 24), at=(x + 62 + 3 * 64, y + 72), scale=pulse(14)),
            layer(bar),
            # The course fills up day by day.
            layer([fill(rrect(200, 380, 380, 22, 11), GREEN)], at=(200, 391),
                  scale=lambda t: (30 + 70 * min(1, t * 1.3), 100)),
            placed(check_badge(36), 640, 200, scale=pulse(12, 0.3)),
            layer(sparkle(660, 110, 12, YELLOW), at=(660, 110), scale=pulse(40))]


def routine():
    cx, cy = 400, 340
    orbit = [fill(ellipse(cx, cy - 190, 42), YELLOW), fill(ellipse(cx, cy - 190, 58), YELLOW, 30),
             fill(ellipse(cx, cy + 190, 34), WHITE), fill(ellipse(cx + 14, cy + 182, 30), SKY)]
    ground = [fill(rrect(-20, 330, W + 40, 200, 0), GREEN_L), fill(ellipse(160, 350, 260, 50), GREEN_L)]
    box = [shadow(400, 420, 190), fill(rrect(220, 300, 360, 100, 22), WHITE)]
    lids = [BLUE, TEAL, GREEN, YELLOW, CORAL, BLUE_L, CORAL_L]
    for d in range(7):
        box += [fill(rrect(236 + d * 48, 316, 40, 68, 12), lids[d], 85)]
    return [backdrop((650, 90, 150, WHITE, 50)),
            layer(orbit, at=(cx, cy), rotate=lambda t: -60 + 360 * t),
            layer(ground),
            layer(box),
            layer(tablet(236 + 2 * 48 + 20, 300, 18), at=(356, 300), move=lambda t: (0, -40 - 20 * wave(t))),
            layer(sparkle(620, 250, 12, TEAL), at=(620, 250), scale=pulse(40))]


def refill():
    x, y = 260, 120
    bottle = [shadow(355, 420, 120), fill(rrect(x, y + 40, 190, 260, 34), WHITE),
              line(rrect(x, y + 40, 190, 260, 34), BLUE_L, 6),
              fill(rrect(x - 8, y, 206, 56, 16), CORAL), fill(rrect(x + 20, y + 130, 150, 90, 12), SKY)]
    level = [fill(rrect(x + 14, y + 236, 162, 50, 22), BLUE_L)]
    pills = tablet(x + 60, y + 262, 16) + tablet(x + 100, y + 268, 16) + tablet(x + 138, y + 260, 16)
    rx, ry, rr = 590, 230, 70
    arrows = [line(arc(rx, ry, rr, 200, 340), BLUE, 14), line(arc(rx, ry, rr, 20, 160), BLUE, 14),
              fill(poly([(rx + rr - 22, ry - 34), (rx + rr + 20, ry - 18), (rx + rr - 6, ry + 6)]), BLUE),
              fill(poly([(rx - rr + 22, ry + 34), (rx - rr - 20, ry + 18), (rx - rr + 6, ry - 6)]), BLUE)]
    return [backdrop((120, 90, 120, WHITE, 60), (700, 420, 150, SKY, 100)),
            layer(bottle),
            layer(level + pills, at=(355, y + 286), scale=lambda t: (100, 85 + 15 * wave(t))),
            layer(arrows, at=(rx, ry), rotate=lambda t: 360 * t),
            layer(sparkle(680, 120, 12, YELLOW), at=(680, 120), scale=pulse(40))]


def side_effects():
    pts = [(380, 240), (450, 240), (475, 190), (505, 300), (535, 160), (565, 260), (590, 240), (700, 240)]
    card = [shadow(470, 400, 260), fill(rrect(130, 110, 600, 260, 36), WHITE)]
    return [backdrop((700, 70, 120, SKY, 100), (90, 420, 130, WHITE, 60)),
            layer(card),
            layer([line(poly(pts, False), BLUE_L, 10)]),
            layer([line(poly(pts, False), BLUE, 10)], trim=lambda t: min(100, t * 160)),
            layer([fill(heart(270, 230, 70), CORAL), fill(ellipse(240, 200, 12, 18), WHITE, 45)], at=(270, 240), scale=beat),
            placed([fill(rrect(-10, -34, 20, 68, 10), GREEN), fill(rrect(-34, -10, 68, 20, 10), GREEN)],
                   660, 320, scale=pulse(10, 0.4))]


def mixing():
    warn = [fill(poly([(0, -62), (64, 50), (-64, 50)]), YELLOW), line(poly([(0, -62), (64, 50), (-64, 50)]), YELLOW, 18),
            fill(rrect(-7, -28, 14, 46, 7), INK), fill(ellipse(0, 34, 8), INK)]
    leaf = [fill(ellipse(0, 0, 26, 52), GREEN), line(poly([(0, -44), (0, 52)], False), GREEN_L, 4)]
    return [backdrop((120, 90, 130, WHITE, 60), (690, 410, 150, SKY, 100)),
            layer([shadow(270, 400, 70)] + capsule(270, 280, 170, 34, 30, BLUE, WHITE), at=(270, 300), rotate=swing(7)),
            layer([shadow(530, 400, 70)] + capsule(530, 280, 170, 34, -30, CORAL, YELLOW), at=(530, 300), rotate=swing(7, 0.5)),
            placed(warn, 400, 140, scale=pulse(12)),
            placed(leaf, 660, 190, rotate=lambda t: 35 + 10 * wave(t, 0.25)),
            layer(tablet(130, 240, 26), at=(130, 240), move=bob(10, 0.3))]


def ask_doctor():
    doc = [shadow(0, 180, 150)] + person(WHITE, 52, HAIR, 'short')
    coat = [line(poly([(-40, 40), (0, 120), (40, 40)], False), GREY, 6),
            line(arc(0, 95, 46, 200, 340, 10), INK, 7), fill(ellipse(38, 110, 12), GREY),
            fill(rrect(-58, 140, 20, 6, 3), CORAL), fill(rrect(-51, 133, 6, 20, 3), CORAL)]
    bubble1 = [fill(rrect(-120, -55, 240, 110, 40), BLUE), fill(poly([(-70, 40), (-100, 80), (-30, 45)]), BLUE)]
    bubble2 = [fill(rrect(-90, -45, 180, 90, 34), WHITE), fill(poly([(40, 35), (70, 70), (10, 40)]), WHITE),
               fill(rrect(-10, -30, 20, 60, 10), CORAL), fill(rrect(-30, -10, 60, 20, 10), CORAL)]
    return [backdrop((690, 410, 170, SKY, 100), (100, 80, 110, WHITE, 60)),
            layer(shift(doc + coat, 260, 260), at=(260, 260), move=bob(4)),
            layer(shift(bubble1, 540, 140)),
            *[layer([fill(ellipse(540 + dx, 140, 11), WHITE)], at=(540 + dx, 140), move=bob(7, k * 0.15))
              for k, dx in enumerate((-50, 0, 50))],
            layer(shift(bubble2, 590, 320), at=(590, 320), scale=pulse(8, 0.5))]


def shift(items, dx, dy):
    out = []
    for item in items:
        s = item['shape']
        moved = {'v': [[x + dx, y + dy] for x, y in s['v']], 'i': s['i'], 'o': s['o'], 'c': s['c']}
        out.append({**item, 'shape': moved})
    return out


def storage():
    x, y, w, h = 200, 70, 320, 340
    cab = [shadow(360, 425, 180), fill(rrect(x, y, w, h, 26), WHITE), line(rrect(x, y, w, h, 26), BLUE_L, 6),
           fill(rrect(x + 20, y + 110, w - 40, 10, 5), BLUE_L), fill(rrect(x + 20, y + 220, w - 40, 10, 5), BLUE_L),
           fill(rrect(x + 130, y + 20, 60, 60, 14), CORAL), fill(rrect(x + 152, y + 30, 16, 40, 6), WHITE),
           fill(rrect(x + 140, y + 42, 40, 16, 6), WHITE)]
    items = [(x + 50, y + 150, BLUE), (x + 110, y + 160, TEAL), (x + 210, y + 140, CORAL), (x + 260, y + 155, GREEN),
             (x + 60, y + 255, YELLOW), (x + 150, y + 265, BLUE_L), (x + 230, y + 250, CORAL_L)]
    for bx, by, color in items:
        # Standing on the shelf below.
        hh = (y + 220 if by < y + 220 else y + 330) - by
        cab += [fill(rrect(bx - 18, by, 36, hh, 8), color), fill(rrect(bx - 13, by - 10, 26, 12, 4), INK, 70)]
    lock = [fill(rrect(-34, -6, 68, 56, 12), YELLOW), line(arc(0, -6, 22, 180, 360, 10), GREY, 10),
            fill(ellipse(0, 18, 7), INK), fill(rrect(-3, 18, 6, 16, 3), INK)]
    thermo = [fill(rrect(-14, -90, 28, 150, 14), WHITE), line(rrect(-14, -90, 28, 150, 14), BLUE_L, 5),
              fill(ellipse(0, 70, 26), BLUE)]
    return [backdrop((690, 90, 130, WHITE, 60), (110, 420, 140, SKY, 100)),
            layer(cab),
            placed(lock, 520, 330, rotate=swing(10)),
            layer(shift(thermo, 650, 230)),
            # Staying cool: the thermometer rises and falls a little.
            layer([fill(rrect(644, 200, 12, 100, 6), BLUE)], at=(650, 300), scale=lambda t: (100, 85 + 15 * wave(t))),
            layer(sparkle(620, 110, 12, TEAL), at=(620, 110), scale=pulse(40))]


def family():
    return [backdrop((400, 470, 330, SKY, 100), (690, 80, 110, WHITE, 60)),
            layer([shadow(260, 440, 110)] + shift(person(BLUE, 50, HAIR, 'short'), 260, 300), at=(260, 300), move=bob(6)),
            layer([shadow(430, 440, 110)] + shift(person(TEAL, 48, HAIR_GREY, 'bun'), 430, 300), at=(430, 300), move=bob(6, 0.33)),
            layer([shadow(580, 440, 80)] + shift(person(CORAL, 38, HAIR, 'pigtails'), 580, 340), at=(580, 340), move=bob(8, 0.66)),
            layer([fill(heart(430, 110, 34), CORAL)], at=(430, 110), scale=beat),
            layer(capsule(160, 150, 90, 18, 40, BLUE, CORAL), at=(160, 150), move=bob(8, 0.5), rotate=swing(8)),
            layer(sparkle(660, 160, 12, YELLOW), at=(660, 160), scale=pulse(40))]


SCENES = {'on-time': on_time, 'missed-dose': missed_dose, 'with-food': with_food, 'full-course': full_course,
          'routine': routine, 'refill': refill, 'side-effects': side_effects, 'mixing': mixing,
          'ask-doctor': ask_doctor, 'storage': storage, 'family': family}


def main():
    svg_dir = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs(os.path.join(ROOT, 'animations'), exist_ok=True)
    for name, scene in SCENES.items():
        layers = scene()
        with open(os.path.join(ROOT, 'animations', f'{name}.json'), 'w') as f:
            json.dump(to_lottie(name, layers), f, separators=(',', ':'))
        if svg_dir:
            os.makedirs(svg_dir, exist_ok=True)
            with open(os.path.join(svg_dir, f'{name}.svg'), 'w') as f:
                f.write(to_svg(layers))
    print('ok', len(SCENES))


main()
