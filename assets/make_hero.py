#!/usr/bin/env python3
"""추상 대문 이미지 생성: 수백 가닥의 흐릿한 선이 조리개를 지나 몇 가닥의 선명한 빛으로 — 컨텍스트 압축의 은유.
python make_hero.py  → hero.html (풀블리드 SVG). 헤드리스 크롬으로 PNG 렌더링."""
import math, random, sys
random.seed(7)
W, H = 1280, 640
FX, FY = 760, 322                      # 조리개(초점)

def strand(i, n):
    t = i / n
    y0 = 30 + 580 * (0.5 + 0.5 * math.sin(math.pi * (t * 2 - 0.5)))**1.0 * random.uniform(0.85, 1.0) + random.uniform(-20, 20)
    y0 = max(10, min(H - 10, y0))
    x1, y1 = random.uniform(180, 360), y0 + random.uniform(-90, 90)
    x2, y2 = random.uniform(480, 640), FY + (y0 - FY) * random.uniform(0.08, 0.28)
    jit = random.uniform(-3, 3)
    d = f"M -60 {y0:.1f} C {x1:.0f} {y1:.1f}, {x2:.0f} {y2:.1f}, {FX - 14} {FY + jit:.1f}"
    hue = random.random()
    col = "#8B5CF6" if hue < 0.4 else "#38BDF8" if hue < 0.75 else "#C4B5FD"
    op = random.uniform(0.14, 0.5)
    sw = random.uniform(1.0, 2.4)
    return f'<path d="{d}" stroke="{col}" stroke-opacity="{op:.2f}" stroke-width="{sw:.1f}" fill="none"/>'

strands = "\n".join(strand(i, 300) for i in range(300))

def beam(k, n):
    dy = (k - (n - 1) / 2) * 16
    ye = FY + dy * 4.2
    d = f"M {FX + 14} {FY + dy * 0.25:.1f} C {FX + 220} {FY + dy * 0.6:.1f}, {FX + 380} {ye:.1f}, {W + 60} {ye:.1f}"
    op = 0.95 - abs(dy) / 90
    return (f'<path d="{d}" stroke="#E0FBFF" stroke-opacity="{op:.2f}" stroke-width="2.6" fill="none" filter="url(#glow)"/>'
            f'<path d="{d}" stroke="#22D3EE" stroke-opacity="{op*0.9:.2f}" stroke-width="1.2" fill="none"/>')

beams = "\n".join(beam(k, 7) for k in range(7))

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
  <radialGradient id="g1" cx="86%" cy="10%" r="60%"><stop offset="0" stop-color="#7C3AED" stop-opacity=".42"/><stop offset="1" stop-color="#7C3AED" stop-opacity="0"/></radialGradient>
  <radialGradient id="g2" cx="8%" cy="95%" r="55%"><stop offset="0" stop-color="#22D3EE" stop-opacity=".30"/><stop offset="1" stop-color="#22D3EE" stop-opacity="0"/></radialGradient>
  <radialGradient id="core" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#FFFFFF" stop-opacity="1"/><stop offset=".35" stop-color="#BDF3FF" stop-opacity=".9"/><stop offset="1" stop-color="#22D3EE" stop-opacity="0"/></radialGradient>
  <linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".08" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>
  <mask id="mL"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>
  <filter id="glow" x="-20%" y="-200%" width="140%" height="500%"><feGaussianBlur stdDeviation="3.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="bigglow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="22"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="#070B16"/>
<rect width="{W}" height="{H}" fill="url(#g1)"/><rect width="{W}" height="{H}" fill="url(#g2)"/>
<g mask="url(#mL)">{strands}</g>
<circle cx="{FX}" cy="{FY}" r="70" fill="#22D3EE" opacity=".35" filter="url(#bigglow)"/>
<g>{beams}</g>
<circle cx="{FX}" cy="{FY}" r="30" fill="url(#core)"/>
<circle cx="{FX}" cy="{FY}" r="44" fill="none" stroke="#BDF3FF" stroke-opacity=".55" stroke-width="1.2"/>
<circle cx="{FX}" cy="{FY}" r="58" fill="none" stroke="#22D3EE" stroke-opacity=".18" stroke-width="1"/>
<line x1="{FX}" y1="{FY-120}" x2="{FX}" y2="{FY+120}" stroke="#BDF3FF" stroke-opacity=".28" stroke-width="1"/>
<text x="1208" y="528" text-anchor="end" font-family="Inter, 'Noto Sans KR', system-ui, sans-serif" font-weight="900" font-size="56" letter-spacing="-2" fill="#EAF2FF">cowork-litemode</text>
<text x="1208" y="564" text-anchor="end" font-family="Inter, 'Noto Sans KR', system-ui, sans-serif" font-weight="500" font-size="18" fill="#A5B4CF" letter-spacing=".5">Less context in. Same answers out.</text>
<text x="1208" y="592" text-anchor="end" font-family="'Noto Sans KR', system-ui, sans-serif" font-weight="600" font-size="16" fill="#7C8AA8">덜 넣고, 같은 답. — Claude Cowork 플러그인</text>
</svg>'''

html = f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;900&family=Noto+Sans+KR:wght@600&display=swap" rel="stylesheet">
<style>html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#070B16}}svg{{display:block}}</style></head>
<body>{svg}</body></html>'''
open("hero.html", "w", encoding="utf-8").write(html)
open("hero.svg", "w", encoding="utf-8").write(svg)
print("hero.html / hero.svg 생성")
