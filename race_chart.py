"""Distance-time chart of the race, from the same constants as build_scene.py.

  python3 race_chart.py out.svg      (then: rsvg-convert -w 1600 out.svg -o out.png)

Time is measured from the switch click. Each racer has its own finish: the Roomba's is the
bed it bumps (that wakes the cat), the light's is the cat itself.
"""
import sys

C_SLOW, ROOMBA_V = 0.25, 0.30
T_CLICK, T_ROOMBA_GO = 1.6, 3.1
BULB_X, BED_X0 = -3.0, 2.1
LIGHT_TO_CAT = 6.0125                              # m, bulb to the cat's face (front arrives at 25.65 s)

roomba_go = T_ROOMBA_GO - T_CLICK                  # 1.5 s after the click
roomba_dist = (BED_X0 - 0.17) - BULB_X             # 4.93 m
roomba_done = roomba_go + roomba_dist / ROOMBA_V   # 17.93 s
light_done = LIGHT_TO_CAT / C_SLOW                 # 24.05 s

W, H = 1600, 900
L, R, T, B = 150, 1500, 150, 760
TMAX, DMAX = 26.0, 7.0


def X(t):
    return L + (R - L) * t / TMAX


def Y(d):
    return B - (B - T) * d / DMAX


BG, FG, DIM, GRID = "#0d0f12", "#f2efe9", "#8a8f98", "#23272e"
LIGHT, ROOMBA = "#ffe7b0", "#7fc4ff"
FONT = "font-family='Helvetica Neue, Helvetica, Arial, sans-serif'"

s = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
     f"<rect width='{W}' height='{H}' fill='{BG}'/>",
     f"<text x='{L}' y='70' fill='{FG}' font-size='40' font-weight='600' {FONT}>0.25 m/s: the race in numbers</text>",
     f"<text x='{L}' y='112' fill='{DIM}' font-size='24' {FONT}>time since the switch is flicked (s) vs distance travelled (m)</text>"]
for t in range(0, 27, 2):
    s.append(f"<line x1='{X(t)}' y1='{T}' x2='{X(t)}' y2='{B}' stroke='{GRID}'/>")
    s.append(f"<text x='{X(t)}' y='{B + 34}' fill='{DIM}' font-size='20' text-anchor='middle' {FONT}>{t}</text>")
for d in range(0, 8):
    s.append(f"<line x1='{L}' y1='{Y(d)}' x2='{R}' y2='{Y(d)}' stroke='{GRID}'/>")
    s.append(f"<text x='{L - 18}' y='{Y(d) + 7}' fill='{DIM}' font-size='20' text-anchor='end' {FONT}>{d} m</text>")
s.append(f"<text x='{(L + R) / 2}' y='{B + 76}' fill='{DIM}' font-size='22' text-anchor='middle' {FONT}>seconds after the click</text>")

# light: r = 0.25 t, from the click to the cat
s.append(f"<line x1='{X(0)}' y1='{Y(0)}' x2='{X(light_done)}' y2='{Y(LIGHT_TO_CAT)}' stroke='{LIGHT}' stroke-width='6' stroke-linecap='round'/>")
# roomba: waits 1.5 s, then 0.30 m/s to the bed
s.append(f"<polyline points='{X(0)},{Y(0)} {X(roomba_go)},{Y(0)} {X(roomba_done)},{Y(roomba_dist)}' fill='none' stroke='{ROOMBA}' stroke-width='6' stroke-linejoin='round' stroke-linecap='round'/>")

for t, d, col, lab1, lab2, dy in ((roomba_done, roomba_dist, ROOMBA, "ROOMBA  0.30 m/s",
                                   "bumps the bed (cat wakes): %.2f m at %.1f s" % (roomba_dist, roomba_done), -78),
                                  (light_done, LIGHT_TO_CAT, LIGHT, "LIGHT  0.25 m/s",
                                   "reaches the cat: %.2f m at %.1f s" % (LIGHT_TO_CAT, light_done), -78)):
    s.append(f"<circle cx='{X(t)}' cy='{Y(d)}' r='11' fill='{col}'/>")
    anchor = "end"
    s.append(f"<text x='{X(t) - 4}' y='{Y(d) + dy}' fill='{col}' font-size='26' font-weight='600' text-anchor='{anchor}' {FONT}>{lab1}</text>")
    s.append(f"<text x='{X(t) - 4}' y='{Y(d) + dy + 32}' fill='{FG}' font-size='21' text-anchor='{anchor}' {FONT}>{lab2}</text>")

# margin bracket along the bottom
yb = B - 40
s.append(f"<line x1='{X(roomba_done)}' y1='{yb}' x2='{X(light_done)}' y2='{yb}' stroke='#ff8a2a' stroke-width='4'/>")
for t in (roomba_done, light_done):
    s.append(f"<line x1='{X(t)}' y1='{yb - 14}' x2='{X(t)}' y2='{yb + 14}' stroke='#ff8a2a' stroke-width='4'/>")
s.append(f"<text x='{(X(roomba_done) + X(light_done)) / 2}' y='{yb - 22}' fill='#ff8a2a' font-size='28' font-weight='700' text-anchor='middle' {FONT}>ROOMBA WINS BY {light_done - roomba_done:.1f} s</text>")
s.append("</svg>")

open(sys.argv[1], "w").write("\n".join(s))
print("roomba %.2f m done %.2f s | light %.2f m done %.2f s | margin %.2f s"
      % (roomba_dist, roomba_done, LIGHT_TO_CAT, light_done, light_done - roomba_done))
