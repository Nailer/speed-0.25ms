"""Builds the whole "0.25 m/s" film from nothing: geometry, materials, animation, camera, text.

Usage:
  Blender --background --python build_scene.py -- <out.blend> [width height samples]

Everything in the film is generated here (no imported assets). The speed of light is
slowed to C_SLOW m/s; a single empty ("Front") carries the front radius, and every
material reads it through the "WaveFront" node group.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hud  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
W = int(argv[1]) if len(argv) > 1 else 960
H = int(argv[2]) if len(argv) > 2 else 540
SAMPLES = int(argv[3]) if len(argv) > 3 else 8

FPS = 24
C_SLOW = 0.25            # metres per second: the "speed of light" in this film
C_REAL = 299_792_458
ROOMBA_V = 0.30          # m/s, a real Roomba is about this fast
T_CLICK = 1.6            # switch flick, light is born
T_ROOMBA_GO = T_CLICK + 1.5
T_END_CARD = 26.6
T_END = 29.4
FRAME_END = int(T_END * FPS)
ORIGIN = Vector((-3.0, 0.5, 2.15))   # the bulb

random.seed(25)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, FRAME_END


def f(t):
    """seconds -> frame number"""
    return 1 + t * FPS


# ---------------------------------------------------------------- front controller
# "Front" is an empty at the bulb whose uniform scale IS the front radius. "FrontOrigin" sits at
# the same point with unit scale. Shaders read both through Texture Coordinate > Object, so no
# drivers touch any material (drivers on node values made EEVEE re-sync every material per frame).
front = bpy.data.objects.new("Front", None)
scene.collection.objects.link(front)
front.location = ORIGIN
front.scale = (0.001,) * 3
front.keyframe_insert("scale", frame=f(T_CLICK))
front.scale = (C_SLOW * (T_END - T_CLICK),) * 3
front.keyframe_insert("scale", frame=f(T_END))
for fc in front.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
front_origin = bpy.data.objects.new("FrontOrigin", None)
scene.collection.objects.link(front_origin)
front_origin.location = ORIGIN


def build_wavefront_group():
    g = bpy.data.node_groups.new("WaveFront", "ShaderNodeTree")
    g.interface.new_socket("Lit", in_out="OUTPUT", socket_type="NodeSocketFloat")
    g.interface.new_socket("Shell", in_out="OUTPUT", socket_type="NodeSocketFloat")
    nout = g.nodes.new("NodeGroupOutput")
    # d = distance from the bulb in metres; q = d / r (r = front radius); r - d = d / q - d
    tc_d = g.nodes.new("ShaderNodeTexCoord")
    tc_d.object = front_origin
    tc_q = g.nodes.new("ShaderNodeTexCoord")
    tc_q.object = front
    d_len = g.nodes.new("ShaderNodeVectorMath")
    d_len.operation = "LENGTH"
    g.links.new(tc_d.outputs["Object"], d_len.inputs[0])
    q_len = g.nodes.new("ShaderNodeVectorMath")
    q_len.operation = "LENGTH"
    g.links.new(tc_q.outputs["Object"], q_len.inputs[0])
    div = g.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    g.links.new(d_len.outputs["Value"], div.inputs[0])
    g.links.new(q_len.outputs["Value"], div.inputs[1])
    sub = g.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    g.links.new(div.outputs[0], sub.inputs[0])
    g.links.new(d_len.outputs["Value"], sub.inputs[1])
    lit = g.nodes.new("ShaderNodeMath")
    lit.operation = "GREATER_THAN"
    lit.inputs[1].default_value = 0.0
    g.links.new(sub.outputs[0], lit.inputs[0])
    ab = g.nodes.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    g.links.new(sub.outputs[0], ab.inputs[0])
    mr = g.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 0.12
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    g.links.new(ab.outputs[0], mr.inputs["Value"])
    pw = g.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.0
    g.links.new(mr.outputs[0], pw.inputs[0])
    g.links.new(lit.outputs[0], nout.inputs["Lit"])
    g.links.new(pw.outputs[0], nout.inputs["Shell"])
    return g


WAVE = build_wavefront_group()
SHELL_COLOR = (1.0, 0.80, 0.50, 1)


def _shade(color, k):
    return (color[0] * k, color[1] * k, color[2] * k, 1)


def pat_planks(nt, color):
    """floorboards: Brick texture laid along X in world space, plus wave grain"""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset, br.offset_frequency = 0.37, 1
    br.inputs["Color1"].default_value = color
    br.inputs["Color2"].default_value = _shade(color, 0.8)
    br.inputs["Mortar"].default_value = _shade(color, 0.3)
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.004
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Brick Width"].default_value = 1.3
    br.inputs["Row Height"].default_value = 0.14
    nt.links.new(geo.outputs["Position"], br.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.bands_direction = "Y"
    wv.inputs["Scale"].default_value = 1.6
    wv.inputs["Distortion"].default_value = 6.0
    wv.inputs["Detail"].default_value = 3.0
    nt.links.new(geo.outputs["Position"], wv.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.18
    nt.links.new(br.outputs["Color"], mix.inputs["A"])
    nt.links.new(wv.outputs["Color"], mix.inputs["B"])
    return mix.outputs["Result"]


def pat_stripes(nt, color):
    """wallpaper: vertical stripes about 12 cm apart"""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 2.6
    nt.links.new(geo.outputs["Position"], wv.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = _shade(color, 1.22)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def pat_checker(nt, color):
    """quilt: 25 cm checks"""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    ck = nt.nodes.new("ShaderNodeTexChecker")
    ck.inputs["Color1"].default_value = color
    ck.inputs["Color2"].default_value = _shade(color, 0.7)
    ck.inputs["Scale"].default_value = 4.0
    nt.links.new(geo.outputs["Position"], ck.inputs["Vector"])
    return ck.outputs["Color"]


def pat_rings(nt, color):
    """round rug: concentric rings around the object's own centre"""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "RINGS"
    wv.inputs["Scale"].default_value = 0.9
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.95, 0.85, 0.6, 1)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def mat_lit(name, color, rough=0.65, shell_boost=1.0, pattern=None):
    """Surface that only exists (is lit) behind the front; glows at the front."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lit = nt.nodes.new("ShaderNodeBsdfPrincipled")
    lit.inputs["Base Color"].default_value = color
    lit.inputs["Roughness"].default_value = rough
    dark = nt.nodes.new("ShaderNodeEmission")
    dark.inputs["Color"].default_value = (color[0] * 0.02, color[1] * 0.02, color[2] * 0.02, 1)
    dark.inputs["Strength"].default_value = 1.0
    if pattern:
        col = pattern(nt, color)
        nt.links.new(col, lit.inputs["Base Color"])
        nt.links.new(col, dark.inputs["Color"])
        dark.inputs["Strength"].default_value = 0.02
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = WAVE
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(grp.outputs["Lit"], mix.inputs[0])
    nt.links.new(dark.outputs[0], mix.inputs[1])
    nt.links.new(lit.outputs[0], mix.inputs[2])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = SHELL_COLOR
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 10.0 * shell_boost
    nt.links.new(grp.outputs["Shell"], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(mix.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def mat_emit(name, color, strength=5.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "EM"
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------- helpers
def box(name, center, size, mat, parent=None):
    bpy.ops.mesh.primitive_cube_add(location=center)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.data.materials.append(mat)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def sphere(name, center, radius, scale, mat, parent=None, seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(location=center, radius=radius, segments=seg, ring_count=seg // 2)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def cyl(name, center, radius, depth, mat, parent=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(location=center, radius=radius, depth=depth, vertices=verts)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(mat)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def empty(name, loc):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    scene.collection.objects.link(e)
    return e


def linear(obj):
    for fc in obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# ---------------------------------------------------------------- materials
M = {
    "floor": mat_lit("floor", (0.42, 0.26, 0.15, 1), 0.5, pattern=pat_planks),
    "hallwall": mat_lit("hallwall", (0.10, 0.38, 0.42, 1), pattern=pat_stripes),
    "bedwall": mat_lit("bedwall", (0.80, 0.45, 0.45, 1)),
    "ceil": mat_lit("ceil", (0.9, 0.86, 0.8, 1)),
    "trim": mat_lit("trim", (0.95, 0.92, 0.86, 1)),
    "mustard": mat_lit("mustard", (0.95, 0.65, 0.10, 1), 0.4),
    "red": mat_lit("red", (0.85, 0.15, 0.12, 1), 0.4),
    "green": mat_lit("green", (0.15, 0.55, 0.25, 1), 0.7),
    "wood": mat_lit("wood", (0.55, 0.34, 0.18, 1), 0.5),
    "bedframe": mat_lit("bedframe", (0.35, 0.2, 0.12, 1), 0.5),
    "sheet": mat_lit("sheet", (0.22, 0.35, 0.75, 1), 0.9, pattern=pat_checker),
    "pillow": mat_lit("pillow", (0.95, 0.93, 0.88, 1), 0.9),
    "mattress": mat_lit("mattress", (0.5, 0.46, 0.42, 1), 0.9),
    "rug": mat_lit("rug", (0.8, 0.3, 0.25, 1), 0.95, pattern=pat_rings),
    "cat": mat_lit("cat", (0.95, 0.52, 0.16, 1), 0.9, shell_boost=1.2),
    "catdark": mat_lit("catdark", (0.5, 0.22, 0.06, 1), 0.9),
    "roomba": mat_lit("roomba", (0.18, 0.18, 0.2, 1), 0.3),
    "glass": mat_lit("glass", (0.2, 0.3, 0.5, 1), 0.1),
    "dust": mat_lit("dust", (1, 0.95, 0.85, 1), 0.5, shell_boost=6.0),
    "bulb": mat_emit("bulb", (1.0, 0.85, 0.55, 1), 0.0),
    "led": mat_emit("led", (0.2, 0.5, 1.0, 1), 8.0),
    "eye": mat_emit("eye", (0.75, 1.0, 0.2, 1), 12.0),
    "pupil": mat_emit("pupil", (0, 0, 0, 1), 0.0),
    "white": mat_emit("white", (1, 1, 1, 1), 3.0),
    "black": mat_emit("blackcard", (0, 0, 0, 1), 0.0),
}

# ---------------------------------------------------------------- the house (cutaway, no front wall)
X0, X1, XP, XE = -3.6, 4.7, 0.2, 4.7
Y0, Y1 = -1.4, 1.6
HZ = 2.4
box("floor", ((X0 + X1) / 2, (Y0 + Y1) / 2, -0.05), (X1 - X0, Y1 - Y0, 0.1), M["floor"])
box("ceil_hall", ((X0 + XP) / 2, (Y0 + Y1) / 2, HZ + 0.05), (XP - X0, Y1 - Y0, 0.1), M["ceil"])
box("ceil_bed", ((XP + X1) / 2, (Y0 + Y1) / 2, HZ + 0.05), (X1 - XP, Y1 - Y0, 0.1), M["ceil"])
box("back_hall", ((X0 + XP) / 2, Y1 + 0.05, HZ / 2), (XP - X0, 0.1, HZ), M["hallwall"])
box("back_bed", ((XP + X1) / 2, Y1 + 0.05, HZ / 2), (X1 - XP, 0.1, HZ), M["bedwall"])
box("end_left", (X0 - 0.05, (Y0 + Y1) / 2, HZ / 2), (0.1, Y1 - Y0, HZ), M["hallwall"])
box("end_right", (X1 + 0.05, (Y0 + Y1) / 2, HZ / 2), (0.1, Y1 - Y0, HZ), M["bedwall"])
# partition with a doorway y in [-0.1, 1.1]
box("part_a", (XP, (Y0 - 0.1) / 2, HZ / 2), (0.14, (-0.1 - Y0), HZ), M["hallwall"])
box("part_b", (XP, (1.1 + Y1) / 2, HZ / 2), (0.14, (Y1 - 1.1), HZ), M["hallwall"])
box("part_head", (XP, 0.5, 2.2 + 0.1), (0.14, 1.2, 0.2), M["hallwall"])
for i, yy in enumerate((-0.1, 1.1)):
    box(f"door_trim{i}", (XP, yy, 1.1), (0.2, 0.06, 2.2), M["trim"])
box("skirting_hall", ((X0 + XP) / 2, Y1 - 0.01, 0.07), (XP - X0, 0.03, 0.14), M["trim"])
box("skirting_bed", ((XP + X1) / 2, Y1 - 0.01, 0.07), (X1 - XP, 0.03, 0.14), M["trim"])

# hall props
box("switchplate", (-3.35, Y1 - 0.01, 1.3), (0.09, 0.02, 0.14), M["trim"])
lever = box("switchlever", (-3.35, Y1 - 0.03, 1.3), (0.03, 0.025, 0.06), M["red"])
lever.rotation_euler = (math.radians(-25), 0, 0)
lever.keyframe_insert("rotation_euler", frame=1)
lever.keyframe_insert("rotation_euler", frame=f(T_CLICK - 0.05))
lever.rotation_euler = (math.radians(25), 0, 0)
lever.keyframe_insert("rotation_euler", frame=f(T_CLICK + 0.03))
for fc in lever.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
# bulb on a cord
cord = cyl("cord", (ORIGIN.x, ORIGIN.y, (HZ + ORIGIN.z) / 2), 0.008, HZ - ORIGIN.z + 0.02, M["pillow"], verts=8)
sphere("bulb", ORIGIN, 0.07, (1, 1, 1), M["bulb"])
bulb_mat = M["bulb"].node_tree.nodes["EM"]
bulb_mat.inputs["Strength"].default_value = 0.0
bulb_mat.inputs["Strength"].keyframe_insert("default_value", frame=f(T_CLICK - 0.02))
bulb_mat.inputs["Strength"].default_value = 60.0
bulb_mat.inputs["Strength"].keyframe_insert("default_value", frame=f(T_CLICK + 0.04))

for i, (px, col) in enumerate(((-2.1, "mustard"), (-1.3, "red"), (-0.55, "green"))):
    box(f"frame{i}", (px, Y1 - 0.03, 1.55 + 0.1 * (i % 2)), (0.5, 0.04, 0.38 + 0.1 * i), M["wood"])
    box(f"art{i}", (px, Y1 - 0.055, 1.55 + 0.1 * (i % 2)), (0.4, 0.02, 0.28 + 0.1 * i), M[col])
# shoe rack + boots
box("rack", (-2.6, 1.15, 0.12), (0.8, 0.35, 0.24), M["wood"])
box("boot1", (-2.8, 1.12, 0.34), (0.12, 0.28, 0.22), M["red"])
box("boot2", (-2.55, 1.12, 0.34), (0.12, 0.28, 0.22), M["mustard"])
# plant
cyl("pot", (-1.0, 1.2, 0.2), 0.16, 0.4, M["red"], verts=16)
for i in range(7):
    a = i / 7 * math.tau
    sphere(f"leaf{i}", (-1.0 + 0.12 * math.cos(a), 1.2 + 0.12 * math.sin(a), 0.62 + 0.08 * (i % 3)), 0.12, (0.6, 0.6, 1.5), M["green"], seg=10)
# radiator
box("radiator", (-0.1, 1.5, 0.35), (0.7, 0.1, 0.5), M["trim"])

# bedroom
bed = empty("BedRoot", (0, 0, 0))
bed_x0, bed_x1 = 2.1, 4.5
box("bedframe", ((bed_x0 + bed_x1) / 2, 0.5, 0.2), (bed_x1 - bed_x0, 1.9, 0.4), M["bedframe"], bed)
box("mattress", ((bed_x0 + bed_x1) / 2, 0.5, 0.48), (bed_x1 - bed_x0 - 0.06, 1.84, 0.16), M["mattress"], bed)
box("blanket", (3.7, 0.5, 0.58), (1.6, 1.88, 0.07), M["sheet"], bed)
box("pillow", (4.28, 0.5, 0.64), (0.34, 1.0, 0.14), M["pillow"], bed)
box("headboard", (bed_x1 - 0.03, 0.5, 0.75), (0.06, 1.95, 1.05), M["bedframe"], bed)
box("nightstand", (4.35, -1.05, 0.25), (0.5, 0.5, 0.5), M["wood"])
cyl("lampbase", (4.35, -1.05, 0.56), 0.06, 0.12, M["mustard"], verts=12)
bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.17, radius2=0.1, depth=0.22, location=(4.35, -1.05, 0.72))
shade = bpy.context.object
shade.data.materials.append(M["pillow"])
box("wardrobe", (1.0, 1.35, 1.0), (1.0, 0.45, 2.0), M["wood"])
box("wardrobe_door", (1.0, 1.12, 1.0), (0.02, 0.0, 0.0), M["wood"]).hide_render = True
cyl("rug", (3.2, 0.2, 0.012), 1.2, 0.02, M["rug"], verts=48)
box("window", (3.0, Y1 - 0.02, 1.5), (1.0, 0.04, 0.9), M["glass"])
for i, (dx, dz) in enumerate(((0, 0), (0, 0))):
    box(f"mullion{i}", (3.0, Y1 - 0.045, 1.5), ((0.04, 0.02, 0.9), (1.0, 0.02, 0.04))[i], M["trim"])

# ---------------------------------------------------------------- the cat (asleep until the Roomba arrives)
cat_c = Vector((2.85, 0.55, 0.56))
cat_root = empty("CatRoot", cat_c)
cat_root.parent = bed
cat_root.matrix_parent_inverse = bed.matrix_world.inverted()
sphere("cat_body", cat_c + Vector((0.05, 0.0, 0.15)), 0.23, (1.5, 1.1, 0.85), M["cat"], cat_root)
head = sphere("cat_head", cat_c + Vector((-0.2, -0.23, 0.2)), 0.13, (1.0, 0.95, 0.9), M["cat"], cat_root)
for sx in (-1, 1):
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.055, depth=0.1,
                                    location=cat_c + Vector((-0.2 + 0.075 * sx, -0.21, 0.33)))
    ear = bpy.context.object
    ear.data.materials.append(M["cat"])
    ear.parent = cat_root
    ear.matrix_parent_inverse = cat_root.matrix_world.inverted()
# stripes
for i in range(4):
    st = box(f"stripe{i}", cat_c + Vector((0.0 + 0.1 * i, 0.0, 0.31 - 0.015 * abs(i - 1.5))), (0.05, 0.4, 0.02), M["catdark"], cat_root)
# tail: curve around the body
cu = bpy.data.curves.new("tail", "CURVE")
cu.dimensions = "3D"
cu.bevel_depth = 0.035
cu.bevel_resolution = 4
sp = cu.splines.new("BEZIER")
sp.bezier_points.add(3)
pts = [(0.30, 0.10, 0.12), (0.35, -0.25, 0.1), (0.05, -0.38, 0.1), (-0.08, -0.30, 0.1)]
for bp_, p in zip(sp.bezier_points, pts):
    bp_.co = cat_c + Vector(p)
    bp_.handle_left_type = bp_.handle_right_type = "AUTO"
tail = bpy.data.objects.new("tail", cu)
cu.materials.append(M["cat"])
scene.collection.objects.link(tail)
tail.parent = cat_root
tail.matrix_parent_inverse = cat_root.matrix_world.inverted()

# eyes: emissive, only exist once the cat wakes (they glow in the dark ahead of the light)
T_BUMP_ARRIVE = T_ROOMBA_GO + ((bed_x0 - 0.17) - ORIGIN.x) / ROOMBA_V
T_EYES = T_BUMP_ARRIVE + 1.3
eyes = []
for sx in (-1, 1):
    pos = cat_c + Vector((-0.2 + 0.055 * sx, -0.345, 0.225))
    ey = sphere(f"eye{sx}", pos, 0.028, (1.0, 0.35, 1.0), M["eye"], cat_root, seg=12)
    pu = sphere(f"pupil{sx}", pos + Vector((0, -0.012, 0)), 0.016, (0.3, 0.5, 1.0), M["pupil"], cat_root, seg=8)
    for o in (ey, pu):
        o.scale = (o.scale[0], o.scale[1], 0.001)
        o.keyframe_insert("scale", frame=f(T_EYES - 0.2))
    for o, k in ((ey, 1.0), (pu, 1.0)):
        o.scale = (o.scale[0], o.scale[1], k * (1.0 if o is ey else 1.2))
        o.keyframe_insert("scale", frame=f(T_EYES + 0.15))
    for o in (ey, pu):  # squint when annoyed by the second bump
        o.scale = (o.scale[0], o.scale[1], 0.4)
        o.keyframe_insert("scale", frame=f(T_BUMP_ARRIVE + 3.6))
        o.keyframe_insert("scale", frame=f(T_BUMP_ARRIVE + 4.8))
        o.scale = (o.scale[0], o.scale[1], 1.0)
        o.keyframe_insert("scale", frame=f(T_BUMP_ARRIVE + 5.0))
    eyes += [ey, pu]

# flattened "closed" eyes still bloomed as glowing slits, so they do not render until they open
for o in eyes:
    o.hide_render = True
    o.keyframe_insert("hide_render", frame=1)
    o.hide_render = False
    o.keyframe_insert("hide_render", frame=f(T_EYES - 0.2))

# tail flick via driver (simple expression, no script needed)
tail_pivot = empty("TailPivot", cat_c + Vector((0.2, 0.0, 0.1)))
d = tail.driver_add("rotation_euler", 2).driver
d.type = "SCRIPTED"
d.expression = "0.15*sin(frame*0.18)"

# ---------------------------------------------------------------- the Roomba (outruns the light)
roomba = empty("Roomba", (ORIGIN.x, ORIGIN.y, 0.045))
cyl("roomba_body", (ORIGIN.x, ORIGIN.y, 0.045), 0.17, 0.09, M["roomba"], roomba)
ring = cyl("roomba_ring", (ORIGIN.x, ORIGIN.y, 0.093), 0.12, 0.006, M["led"], roomba)
cyl("roomba_button", (ORIGIN.x, ORIGIN.y, 0.097), 0.035, 0.006, M["roomba"], roomba)
box("roomba_bumper", (ORIGIN.x + 0.165, ORIGIN.y, 0.04), (0.02, 0.2, 0.035), M["roomba"], roomba)
# LED: blue while travelling, amber after bump, lit through keyframed emission colour
led = M["led"].node_tree.nodes["EM"].inputs["Color"]
led.default_value = (0.2, 0.5, 1.0, 1)
led.keyframe_insert("default_value", frame=f(T_BUMP_ARRIVE - 0.05))
led.default_value = (1.0, 0.45, 0.05, 1)
led.keyframe_insert("default_value", frame=f(T_BUMP_ARRIVE + 0.05))
M["led"].node_tree.nodes["EM"].inputs["Strength"].default_value = 3.0

rx_stop = bed_x0 - 0.17
keys = [
    (T_ROOMBA_GO, ORIGIN.x, 0.0),
    (T_BUMP_ARRIVE, rx_stop, 0.0),
    (T_BUMP_ARRIVE + 0.30, rx_stop - 0.18, 0.0),          # recoil
    (T_BUMP_ARRIVE + 0.60, rx_stop - 0.18, 25.0),         # turn
    (T_BUMP_ARRIVE + 0.95, rx_stop - 0.01, 25.0),         # second try, a bit off angle
    (T_BUMP_ARRIVE + 1.25, rx_stop - 0.12, 25.0),
    (T_BUMP_ARRIVE + 3.5, rx_stop - 0.12, 25.0),
]
roomba.location = (ORIGIN.x, ORIGIN.y, 0.045)
roomba.keyframe_insert("location", frame=1)
roomba.rotation_euler = (0, 0, 0)
roomba.keyframe_insert("rotation_euler", frame=1)
for t, x, rot in keys:
    roomba.location = (x, ORIGIN.y + (0.0 if rot == 0 else -0.04), 0.045)
    roomba.rotation_euler = (0, 0, math.radians(rot))
    roomba.keyframe_insert("location", frame=f(t))
    roomba.keyframe_insert("rotation_euler", frame=f(t))
# straight travel must be linear (constant 0.30 m/s) up to the bump
for fc in roomba.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR" if kp.co.x <= f(T_BUMP_ARRIVE) + 0.1 else "BEZIER"
# bed + cat jolt when bumped
for t, dx in ((T_BUMP_ARRIVE - 0.05, 0), (T_BUMP_ARRIVE + 0.05, 0.02), (T_BUMP_ARRIVE + 0.18, -0.008),
              (T_BUMP_ARRIVE + 0.35, 0), (T_BUMP_ARRIVE + 1.0, 0), (T_BUMP_ARRIVE + 1.05, 0.012),
              (T_BUMP_ARRIVE + 1.25, 0)):
    bed.location = (dx, 0, 0)
    bed.keyframe_insert("location", frame=f(t))

# ---------------------------------------------------------------- dust motes (Geometry Nodes)
dust_obj = bpy.data.objects.new("dust", bpy.data.meshes.new("dust"))
scene.collection.objects.link(dust_obj)
dust_obj.data.materials.append(M["dust"])
gn = bpy.data.node_groups.new("DustMotes", "GeometryNodeTree")
gn.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
gn.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
gin = gn.nodes.new("NodeGroupInput")
gout = gn.nodes.new("NodeGroupOutput")
pts_n = gn.nodes.new("GeometryNodePoints")
pts_n.inputs["Count"].default_value = 450
rnd = gn.nodes.new("FunctionNodeRandomValue")
rnd.data_type = "FLOAT_VECTOR"
rnd.inputs["Min"].default_value = (X0 + 0.2, Y0 + 0.2, 0.2)
rnd.inputs["Max"].default_value = (X1 - 0.2, Y1 - 0.3, HZ - 0.15)
rnd.inputs["Seed"].default_value = 7
gn.links.new(rnd.outputs["Value"], pts_n.inputs["Position"])
pos_n = gn.nodes.new("GeometryNodeInputPosition")
time_n = gn.nodes.new("GeometryNodeInputSceneTime")
noise = gn.nodes.new("ShaderNodeTexNoise")
noise.noise_dimensions = "4D"
noise.inputs["Scale"].default_value = 0.6
gn.links.new(pos_n.outputs[0], noise.inputs["Vector"])
tmul = gn.nodes.new("ShaderNodeMath")
tmul.operation = "MULTIPLY"
tmul.inputs[1].default_value = 0.08
gn.links.new(time_n.outputs["Seconds"], tmul.inputs[0])
gn.links.new(tmul.outputs[0], noise.inputs["W"])
vsub = gn.nodes.new("ShaderNodeVectorMath")
vsub.operation = "SUBTRACT"
vsub.inputs[1].default_value = (0.5, 0.5, 0.5)
gn.links.new(noise.outputs["Color"], vsub.inputs[0])
vsc = gn.nodes.new("ShaderNodeVectorMath")
vsc.operation = "SCALE"
vsc.inputs["Scale"].default_value = 1.2
gn.links.new(vsub.outputs[0], vsc.inputs[0])
setp = gn.nodes.new("GeometryNodeSetPosition")
gn.links.new(pts_n.outputs[0], setp.inputs["Geometry"])
gn.links.new(vsc.outputs[0], setp.inputs["Offset"])
ico = gn.nodes.new("GeometryNodeMeshIcoSphere")
ico.inputs["Radius"].default_value = 0.007
ico.inputs["Subdivisions"].default_value = 1
inst = gn.nodes.new("GeometryNodeInstanceOnPoints")
gn.links.new(setp.outputs[0], inst.inputs["Points"])
gn.links.new(ico.outputs[0], inst.inputs["Instance"])
rs = gn.nodes.new("FunctionNodeRandomValue")
rs.data_type = "FLOAT"
rs.inputs[2].default_value = 0.5   # Min
rs.inputs[3].default_value = 2.2   # Max
gn.links.new(rs.outputs[1], inst.inputs["Scale"]) if False else None
setm = gn.nodes.new("GeometryNodeSetMaterial")
setm.inputs["Material"].default_value = M["dust"]
gn.links.new(inst.outputs[0], setm.inputs["Geometry"])
gn.links.new(setm.outputs[0], gout.inputs["Geometry"])
mod = dust_obj.modifiers.new("DustMotes", "NODES")
mod.node_group = gn

# ---------------------------------------------------------------- lights (hidden ahead of the front by the mask)
def light(name, kind, loc, energy, size=1.0, color=(1.0, 0.85, 0.6), rot=(0, 0, 0)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    else:
        ld.shadow_soft_size = size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = rot
    scene.collection.objects.link(lo)
    return lo


light("bulb_light", "POINT", ORIGIN - Vector((0, 0, 0.1)), 450, 0.08)
light("hall_fill", "AREA", (-1.2, 0.3, 2.3), 140, 2.0, rot=(0, 0, 0))
light("bed_fill", "AREA", (3.0, 0.3, 2.3), 220, 2.5, color=(1.0, 0.75, 0.55))
light("front_fill", "AREA", (0.5, -3.8, 1.6), 90, 3.0, color=(0.9, 0.8, 0.7), rot=(math.radians(90), 0, 0))

# ---------------------------------------------------------------- camera
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 30
cam = bpy.data.objects.new("cam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
tgt = empty("CamTarget", (-3.0, 0.5, 2.0))
tc = cam.constraints.new("TRACK_TO")
tc.target = tgt
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"

shots = [  # t, camera position, look-at
    (0.0, (-3.0, -1.7, 1.75), (-3.0, 0.5, 2.0)),
    (T_CLICK, (-3.0, -1.7, 1.75), (-3.0, 0.5, 2.0)),
    (T_CLICK + 4.0, (-2.7, -2.7, 1.7), (-2.1, 0.5, 1.2)),
    (12.0, (-0.6, -4.3, 1.7), (-0.2, 0.5, 1.0)),
    (18.0, (1.4, -4.6, 1.5), (1.9, 0.5, 0.7)),
    (T_BUMP_ARRIVE + 1.0, (1.4, -3.4, 1.25), (2.4, 0.5, 0.55)),
    (24.5, (1.7, -2.3, 1.0), (2.6, 0.55, 0.55)),
    (T_END_CARD, (1.8, -2.1, 0.95), (2.7, 0.55, 0.55)),
]
for t, cp, tp in shots:
    cam.location = cp
    tgt.location = tp
    cam.keyframe_insert("location", frame=f(t))
    tgt.keyframe_insert("location", frame=f(t))

# Chase insert: hard cut to a floor-level camera riding ahead of the Roomba at its own 0.30 m/s,
# looking back at it while the light dome comes down the hall behind. Hard cut back out after.
T_CHASE_IN, T_CHASE_OUT = 9.5, 14.0


def roomba_x(t):
    return ORIGIN.x + ROOMBA_V * (t - T_ROOMBA_GO)


def chase(t):
    rx = roomba_x(t)
    return (rx + 1.1, 0.38, 0.3), (rx - 0.6, 0.55, 0.16)


F_IN, F_OUT = round(f(T_CHASE_IN)), round(f(T_CHASE_OUT))
for ob, k in ((cam, 0), (tgt, 1)):
    fcs = [fc for fc in ob.animation_data.action.fcurves if fc.data_path == "location"]
    before = [fc.evaluate(F_IN - 1) for fc in fcs]
    after = [fc.evaluate(F_OUT) for fc in fcs]
    for fc in fcs:  # drop the wide-shot keys that fall inside the insert
        for kp in [kp for kp in fc.keyframe_points if F_IN - 1 < kp.co.x < F_OUT]:
            fc.keyframe_points.remove(kp)
    for frame, vals in ((F_IN - 1, before), (F_IN, chase(T_CHASE_IN)[k]),
                        (F_OUT - 1, chase((F_OUT - 2) / FPS)[k]), (F_OUT, after)):
        ob.location = vals
        ob.keyframe_insert("location", frame=frame)
    for fc in fcs:
        for kp in fc.keyframe_points:
            if kp.co.x in (F_IN - 1, F_OUT - 1):
                kp.interpolation = "CONSTANT"   # the cut
            elif kp.co.x == F_IN:
                kp.interpolation = "LINEAR"     # constant speed, locked to the Roomba

# ---------------------------------------------------------------- typography (parented to camera)
try:  # Inter ships with Blender; packed so the .blend does not depend on where Blender is installed
    FONT = bpy.data.fonts.load(os.path.join(bpy.utils.system_resource("DATAFILES"), "fonts", "Inter.woff2"))
    FONT.pack()
except Exception as e:
    print("FONT FALLBACK", e)
    FONT = None


def text(name, body, size, pos, mat, align="LEFT", dist=1.4):
    cu_ = bpy.data.curves.new(name, "FONT")
    cu_.body = body
    cu_.size = size
    cu_.align_x = align
    cu_.align_y = "CENTER"
    if FONT:
        cu_.font = FONT
    cu_.materials.append(mat)
    o = bpy.data.objects.new(name, cu_)
    scene.collection.objects.link(o)
    o.parent = cam
    o.location = (pos[0], pos[1], -dist)
    return o


def show(o, t0, t1):
    o.hide_render = True
    o.hide_viewport = True
    o.keyframe_insert("hide_render", frame=1)
    o.keyframe_insert("hide_viewport", frame=1)
    o.hide_render = False
    o.hide_viewport = False
    o.keyframe_insert("hide_render", frame=f(t0))
    o.keyframe_insert("hide_viewport", frame=f(t0))
    o.hide_render = True
    o.hide_viewport = True
    o.keyframe_insert("hide_render", frame=f(t1))
    o.keyframe_insert("hide_viewport", frame=f(t1))


T1 = text("t_label", "THE SPEED OF LIGHT", 0.06, (0, 0.17), M["white"], "CENTER")
T2 = text("t_value", "299,792,458 m/s", 0.14, (0, 0.04), M["white"], "CENTER")
show(T1, 0.2, T_CLICK - 0.05)
show(T2, 0.2, T_CLICK - 0.05)
T3 = text("t_label2", "TODAY, SLOWED BY %s×" % format(round(C_REAL / C_SLOW), ","), 0.05, (0, 0.03), M["white"], "CENTER")
T4 = text("t_value2", "0.25 m/s", 0.16, (0, -0.1), M["white"], "CENTER")
show(T3, T_CLICK + 0.05, T_CLICK + 3.8)
show(T4, T_CLICK + 0.05, T_CLICK + 3.8)

HUD = text("hud", "t 0.0 s\nfront 0.00 m", 0.04, (-0.62, -0.32), M["white"], "LEFT")
show(HUD, T_CLICK + 4.0, T_END_CARD)

# translucent plate behind the HUD so the readout stays legible when the bright front passes behind it
plate_m = bpy.data.materials.new("hud_plate")
plate_m.use_nodes = True
plate_m.surface_render_method = "BLENDED"   # true alpha blend; the default dithering shows as grain
pn = plate_m.node_tree
pn.nodes.clear()
p_out = pn.nodes.new("ShaderNodeOutputMaterial")
p_mix = pn.nodes.new("ShaderNodeMixShader")
p_mix.inputs[0].default_value = 0.88
p_tr = pn.nodes.new("ShaderNodeBsdfTransparent")
p_bk = pn.nodes.new("ShaderNodeEmission")
p_bk.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
pn.links.new(p_tr.outputs[0], p_mix.inputs[1])
pn.links.new(p_bk.outputs[0], p_mix.inputs[2])
pn.links.new(p_mix.outputs[0], p_out.inputs["Surface"])
plate = bpy.data.objects.new("hud_plate", bpy.data.meshes.new("hud_plate"))
x0, x1, y0, y1 = -0.645, -0.17, -0.385, -0.255
plate.data.from_pydata([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [], [(0, 1, 2, 3)])
plate.data.materials.append(plate_m)
scene.collection.objects.link(plate)
plate.parent = cam
plate.location = (0, 0, -1.41)
show(plate, T_CLICK + 4.0, T_END_CARD)
# pull the readout and plate towards the lens, scaled about the camera so the framing is identical:
# at 1.4 m the floor hid them in the low chase shot (camera 0.3 m up); at 0.21 m nothing is that close
HUD_K = 0.15
for o in (HUD, plate):
    o.location = o.location * HUD_K
    o.scale = (HUD_K,) * 3

# end card: black card + three lines
card = bpy.data.objects.new("card", bpy.data.meshes.new("card"))
card.data.from_pydata([(-3, -2, 0), (3, -2, 0), (3, 2, 0), (-3, 2, 0)], [], [(0, 1, 2, 3)])
card.data.materials.append(M["black"])
scene.collection.objects.link(card)
card.parent = cam
card.location = (0, 0, -1.0)
show(card, T_END_CARD, T_END + 1)
E1 = text("e1", "ROOMBA   0.30 m/s", 0.075, (0, 0.14), M["white"], "CENTER", dist=0.9)
E2 = text("e2", "LIGHT   0.25 m/s", 0.075, (0, 0.03), M["white"], "CENTER", dist=0.9)
E3 = text("e3", "ROOMBA WINS.", 0.1, (0, -0.14), mat_emit("accent", (1.0, 0.45, 0.05, 1), 5.0), "CENTER", dist=0.9)
show(E1, T_END_CARD + 0.1, T_END + 1)
show(E2, T_END_CARD + 0.5, T_END + 1)
show(E3, T_END_CARD + 1.0, T_END + 1)

# speed tag floating over the Roomba, always facing the camera
tag = text("roomba_tag", "0.30 m/s", 0.12, (0, 0), mat_emit("tagmat", (0.45, 0.75, 1.0, 1), 4.0), "CENTER")
tag.parent = roomba
tag.location = (0, 0, 0.34)
tag.rotation_euler = (0, 0, 0)
tc2 = tag.constraints.new("TRACK_TO")
tc2.target = cam
tc2.track_axis = "TRACK_Z"
tc2.up_axis = "UP_Y"
show(tag, T_ROOMBA_GO + 0.4, T_BUMP_ARRIVE + 0.2)

# ---------------------------------------------------------------- render settings
scene.world = bpy.data.worlds.new("w")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
r = scene.render
r.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = SAMPLES
r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
r.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "None"
scene.view_settings.exposure = -0.4
scene.use_nodes = True
ct = scene.node_tree
ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers")
gl = ct.nodes.new("CompositorNodeGlare")
gl.glare_type = "BLOOM" if "BLOOM" in [e.identifier for e in gl.bl_rna.properties["glare_type"].enum_items] else "FOG_GLOW"
gl.quality = "MEDIUM"
gl.threshold = 1.2
co = ct.nodes.new("CompositorNodeComposite")
ct.links.new(rl.outputs["Image"], gl.inputs["Image"])
ct.links.new(gl.outputs["Image"], co.inputs["Image"])

scene["c_slow"] = C_SLOW
scene["t_click"] = T_CLICK
hud.register(scene, HUD, T_CLICK, C_SLOW)

# report the timeline for sanity
cat_pos = cat_c + Vector((0, 0, 0.2))
print("FRONT HITS CAT AT t=%.2fs (d=%.2fm)" % (T_CLICK + (cat_pos - ORIGIN).length / C_SLOW, (cat_pos - ORIGIN).length))
print("ROOMBA ARRIVES AT BED t=%.2fs ; EYES OPEN t=%.2fs" % (T_BUMP_ARRIVE, T_EYES))
print("FRAMES", FRAME_END, "duration", T_END)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED", OUT)
