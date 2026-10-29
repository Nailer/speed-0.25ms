"""Loaded in every final-render Blender session: registers the HUD and applies quality settings."""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hud  # noqa: E402

sc = bpy.context.scene
hud.register_from_scene()
sc.render.resolution_percentage = int(os.environ.get("RES_PCT", "100"))
sc.eevee.taa_render_samples = int(os.environ.get("SAMPLES", "8"))
