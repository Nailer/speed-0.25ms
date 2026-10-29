"""Live readout (time + front distance) for the HUD text object.

Text bodies cannot be keyframed, so a frame-change handler rewrites it before each frame.
Must be registered in every Blender session that renders (build, preview and final).
"""
import bpy

_STATE = {}


def _update(scene, *_):
    t = (scene.frame_current - 1) / scene.render.fps
    st = _STATE
    obj = bpy.data.objects.get("hud")
    if not obj:
        return
    since = max(0.0, t - st["t0"])
    obj.data.body = "t  %4.1f s\nlight front  %4.2f m" % (since, since * st["c"])


def register(scene, hud_obj, t0, c):
    _STATE.update(t0=t0, c=c)
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "_update":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(_update)
    bpy.app.handlers.render_pre.append(_update)


def register_from_scene():
    scene = bpy.context.scene
    register(scene, bpy.data.objects.get("hud"), float(scene["t_click"]), float(scene["c_slow"]))
