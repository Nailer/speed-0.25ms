"""Takes a genuine Blender UI screenshot for the contest's work-in-progress image.

Usage (GUI, not background): Blender speed.blend --window-geometry 0 0 1920 1080 --python wip_shot.py -- <out.png> [sec]

Lays out the Scripting workspace as: rendered camera view, build_scene.py in the text editor,
and a solid-shaded overview of the whole generated set in place of the console. Then captures the
window with Blender's own screenshot operator and quits.
"""
import math
import os
import sys

import bpy
import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
SEC = float(argv[1]) if len(argv) > 1 else 12.0


def setup():
    win = bpy.context.window_manager.windows[0]
    win.workspace = bpy.data.workspaces["Scripting"]
    # each step schedules the next, so a startup dialog that blocks the event loop can't
    # make them fire out of order
    bpy.app.timers.register(arrange, first_interval=3.0)
    return None


OVERVIEW = []   # the console area, turned into a second 3D viewport


def arrange():
    sc = bpy.context.scene
    hud.register_from_scene()
    sc.frame_set(int(1 + SEC * sc.render.fps))
    win = bpy.context.window_manager.windows[0]
    txt = bpy.data.texts.load(os.path.join(HERE, "build_scene.py"))
    for area in list(win.screen.areas):
        if area.type == "VIEW_3D":
            sp = area.spaces.active
            sp.shading.type = "RENDERED"
            sp.region_3d.view_perspective = "CAMERA"
            sp.overlay.show_overlays = True
            sp.show_gizmo_navigate = False
            sp.show_region_toolbar = False
        elif area.type == "TEXT_EDITOR":
            sp = area.spaces.active
            sp.text = txt
            sp.show_line_numbers = True
            sp.show_syntax_highlight = True
            sp.top = 49   # the front controller + WaveFront node group builder
            sp.show_region_footer = False   # the footer prints the file's absolute path
        elif area.type == "CONSOLE":
            area.type = "VIEW_3D"
            OVERVIEW.append(area)
    bpy.app.timers.register(frame_views, first_interval=3.0)
    return None


def frame_views():
    """Overview viewport: everything but the ceilings, in local view, seen from above."""
    win = bpy.context.window_manager.windows[0]
    area = OVERVIEW[0]
    sp = area.spaces.active
    sp.shading.type = "SOLID"
    sp.shading.color_type = "RANDOM"
    sp.shading.show_cavity = True
    sp.show_gizmo_navigate = False
    sp.show_region_toolbar = False
    sp.overlay.show_floor = False
    sp.overlay.show_axis_x = sp.overlay.show_axis_y = False
    region = next(r for r in area.regions if r.type == "WINDOW")
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(o.type == "MESH" and not o.name.startswith("ceil_"))
    sp.region_3d.view_perspective = "PERSP"
    sp.region_3d.view_rotation = mathutils.Euler((math.radians(42), 0, math.radians(-14))).to_quaternion()
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.view3d.localview(frame_selected=True)
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = None   # nothing selected: no orange outlines in the shot
    cam_area = next(a for a in win.screen.areas if a.type == "VIEW_3D" and a != area)
    cam_region = next(r for r in cam_area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=win, area=cam_area, region=cam_region):
        bpy.ops.view3d.view_center_camera()
    bpy.app.timers.register(shoot, first_interval=40.0)
    return None


def shoot():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "TEXT_EDITOR")
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot(filepath=OUT)
    print("WIP SCREENSHOT", OUT, flush=True)
    bpy.app.timers.register(quit_, first_interval=3.0)
    return None


def quit_():
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(setup, first_interval=2.0)
