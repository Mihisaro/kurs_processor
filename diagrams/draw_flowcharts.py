#!/usr/bin/env python3
"""Генерация аккуратных блок-схем оптимизаций (SVG)."""

from pathlib import Path

OUT = Path(__file__).parent

MARKER = """
  <defs>
    <marker id="arr" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="#222"/>
    </marker>
    <style>
      .box { fill:#fff; stroke:#222; stroke-width:1.5; }
      .term { fill:#d6ebf9; stroke:#222; stroke-width:1.5; }
      .dia { fill:#fff4d6; stroke:#222; stroke-width:1.5; }
      .tx { font:14px Arial,sans-serif; fill:#222; }
      .hd { font:bold 16px Arial,sans-serif; fill:#222; }
      .lb { font:bold 12px Arial,sans-serif; fill:#444; }
      .ln { fill:none; stroke:#222; stroke-width:1.5; marker-end:url(#arr); }
    </style>
  </defs>
"""


def _svg_header(w, h):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n{MARKER}\n'


def _line(x1, y1, x2, y2):
    return f'<path d="M {x1} {y1} L {x2} {y2}" class="ln"/>\n'


def _oval(cx, cy, rx, ry, text):
    return (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" class="term"/>\n'
        f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" class="tx">{text}</text>\n'
    )


def _rect(cx, cy, w, h, lines):
    x, y = cx - w // 2, cy - h // 2
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" class="box"/>\n']
    if len(lines) == 1:
        parts.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" class="tx">{lines[0]}</text>\n')
    else:
        parts.append(f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" class="tx">{lines[0]}</text>\n')
        parts.append(f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" class="tx">{lines[1]}</text>\n')
    return "".join(parts)


def _diamond(cx, cy, hw, hh, lines):
    pts = f"{cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh} {cx - hw},{cy}"
    parts = [f'<polygon points="{pts}" class="dia"/>\n']
    if len(lines) == 1:
        parts.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" class="tx">{lines[0]}</text>\n')
    else:
        parts.append(f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" class="tx">{lines[0]}</text>\n')
        parts.append(f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" class="tx">{lines[1]}</text>\n')
    return "".join(parts)


def _label(x, y, text):
    return f'<text x="{x}" y="{y}" class="lb">{text}</text>\n'


def build_opt1():
    cx, loop_x, left_x = 280, 500, 155
    parts = [_svg_header(560, 920)]
    parts.append(f'<text x="{cx}" y="32" text-anchor="middle" class="hd">Опт. 1: устранение временной переменной</text>\n')

    y = 70
    parts.append(_oval(cx, y, 55, 22, "Начало"))
    parts.append(_line(cx, y + 22, cx, y + 38))

    y = 115
    parts.append(_rect(cx, y, 270, 40, ["i := 0,  out := пустой список"]))
    parts.append(_line(cx, y + 20, cx, y + 48))

    y = 175
    parts.append(_diamond(cx, y, 95, 38, ["i &lt; len(IR)?"]))
    parts.append(_label(cx - 115, y - 4, "нет"))
    parts.append(_line(cx - 95, y, 50, y))
    parts.append(_line(50, y, 50, 860))
    parts.append(_line(50, 860, cx - 110, 860))

    parts.append(_label(cx + 108, y - 4, "да"))
    parts.append(_line(cx, y + 38, cx, y + 68))

    y = 225
    parts.append(_diamond(cx, y, 115, 42, ["LOAD_CONST t=c", "и STORE x=t ?"]))
    parts.append(_label(cx - 130, y - 4, "нет"))
    parts.append(_line(cx - 115, y, left_x, y))
    parts.append(_line(left_x, y, left_x, 600))

    y = 600
    parts.append(_rect(left_x, y, 175, 44, ["out += IR[i]", "i := i + 1"]))
    parts.append(_line(left_x + 88, y, loop_x, y))
    parts.append(_line(loop_x, y + 22, loop_x, 175))
    parts.append(_line(loop_x, 175, cx + 95, 175))
    parts.append(_label(loop_x + 8, 380, "↑ цикл"))

    parts.append(_label(cx + 128, y - 4, "да"))
    parts.append(_line(cx, y + 42, cx, y + 72))

    y = 310
    parts.append(_rect(cx, y, 240, 36, ["out += STORE x = c"]))
    parts.append(_line(cx, y + 18, cx, y + 348))

    y = 375
    parts.append(_rect(cx, y, 150, 32, ["i := i + 2"]))
    parts.append(_line(cx, y + 16, cx, y + 408))

    y = 445
    parts.append(_diamond(cx, y, 78, 32, ["след. SET_TYPE?"]))
    parts.append(_label(cx - 95, y - 4, "нет"))
    parts.append(_line(cx - 78, y, loop_x, y))
    parts.append(_line(loop_x, y, loop_x, 175))
    parts.append(_line(loop_x, 175, cx + 95, 175))

    parts.append(_label(cx + 95, y - 4, "да"))
    parts.append(_line(cx, y + 32, cx, y + 498))

    y = 525
    parts.append(_rect(cx, y, 250, 36, ["out += SET_TYPE,  i := i + 1"]))
    parts.append(_line(cx, y + 18, loop_x, y + 18))
    parts.append(_line(loop_x, y + 18, loop_x, 175))
    parts.append(_line(loop_x, 175, cx + 95, 175))

    parts.append(_oval(cx, 860, 115, 24, "Переиндексация, конец"))
    parts.append("</svg>\n")
    return "".join(parts)


def build_opt2():
    cx, loop_x, left_x = 280, 500, 155
    parts = [_svg_header(560, 860)]
    parts.append(f'<text x="{cx}" y="32" text-anchor="middle" class="hd">Опт. 2: свёртка констант и канонизация</text>\n')

    y = 70
    parts.append(_oval(cx, y, 55, 22, "Начало"))
    parts.append(_line(cx, y + 22, cx, y + 38))

    y = 115
    parts.append(_rect(cx, y, 270, 40, ["i := 0,  out := пустой список"]))
    parts.append(_line(cx, y + 20, cx, y + 48))

    y = 175
    parts.append(_diamond(cx, y, 95, 38, ["i &lt; len(IR)?"]))
    parts.append(_label(cx - 115, y - 4, "нет"))
    parts.append(_line(cx - 95, y, 50, y))
    parts.append(_line(50, y, 50, 800))
    parts.append(_line(50, 800, cx - 110, 800))

    parts.append(_label(cx + 108, y - 4, "да"))
    parts.append(_line(cx, y + 38, cx, y + 68))

    y = 225
    parts.append(_diamond(cx, y, 115, 42, ["STORE x = v", "и SET_TYPE x = T ?"]))
    parts.append(_label(cx - 130, y - 4, "нет"))
    parts.append(_line(cx - 115, y, left_x, y))
    parts.append(_line(left_x, y, left_x, 540))

    y = 540
    parts.append(_rect(left_x, y, 175, 44, ["out += IR[i]", "i := i + 1"]))
    parts.append(_line(left_x + 88, y, loop_x, y))
    parts.append(_line(loop_x, y + 22, loop_x, 175))
    parts.append(_line(loop_x, 175, cx + 95, 175))

    parts.append(_label(cx + 128, y - 4, "да"))
    parts.append(_line(cx, y + 42, cx, y + 72))

    y = 300
    parts.append(_diamond(cx, y, 72, 30, ["v — литерал?"]))
    parts.append(_label(cx - 88, y - 4, "нет"))
    parts.append(_line(cx - 72, y, left_x, y))
    parts.append(_line(left_x, y, left_x, 540))

    parts.append(_label(cx + 88, y - 4, "да"))
    parts.append(_line(cx, y + 30, cx, y + 358))

    y = 395
    parts.append(_rect(cx, y, 310, 48, ["out += CONST_DECL", "x : T = v"]))
    parts.append(_line(cx, y + 24, cx, y + 448))

    y = 475
    parts.append(_rect(cx, y, 150, 32, ["i := i + 2"]))
    parts.append(_line(cx, y + 16, loop_x, y + 16))
    parts.append(_line(loop_x, y + 16, loop_x, 175))
    parts.append(_line(loop_x, 175, cx + 95, 175))
    parts.append(_label(loop_x + 8, 320, "↑ цикл"))

    parts.append(_oval(cx, 800, 115, 24, "Переиндексация, конец"))
    parts.append("</svg>\n")
    return "".join(parts)


def main():
    (OUT / "opt1_copy_propagation.svg").write_text(build_opt1(), encoding="utf-8")
    (OUT / "opt2_constant_fold.svg").write_text(build_opt2(), encoding="utf-8")
    print("OK:", OUT / "opt1_copy_propagation.svg")
    print("OK:", OUT / "opt2_constant_fold.svg")


if __name__ == "__main__":
    main()
