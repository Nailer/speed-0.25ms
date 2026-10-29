"""Resumable render with a stall watchdog. Run with the system Python (not inside Blender).

  python3 render_final.py <outdir> <percent> <samples> [chunk=30] [step=1]

Set BLENDER=/path/to/blender to use a Blender other than ../tools/Blender.app.

Finds frames that do not yet exist in <outdir> (a half-written frame is detected by size)
and renders them in chunks, so a crash or Ctrl-C loses at most one chunk. Re-run to resume.
If Blender writes no frame for STALL seconds (seen once: EEVEE hung mid-frame at ~1% CPU),
it is killed and the chunk is retried; three stalls in a row on the same frame stop the run.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.environ.get("BLENDER") or os.path.join(HERE, "..", "tools", "Blender.app", "Contents", "MacOS", "Blender")
BLEND = os.path.join(HERE, "speed.blend")
FIRST, LAST = 1, 705   # must match build_scene.py (FRAME_END)
STALL = 180            # seconds without a new frame (first frame includes load + shader compile)

outdir, pct, samples = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
chunk = int(sys.argv[4]) if len(sys.argv) > 4 else 30
step = int(sys.argv[5]) if len(sys.argv) > 5 else 1
os.makedirs(outdir, exist_ok=True)
WANT = list(range(FIRST, LAST + 1, step))


def have(i):
    p = os.path.join(outdir, "f_%04d.png" % i)
    return os.path.exists(p) and os.path.getsize(p) > 20_000


def count():
    return sum(1 for i in WANT if have(i))


stalls = {}
t_start = time.time()
while True:
    todo = [i for i in WANT if not have(i)]
    if not todo:
        print("ALL FRAMES PRESENT:", len(WANT), "in %.0f min" % ((time.time() - t_start) / 60), flush=True)
        break
    a = todo[0]
    b = min(a + chunk * step - 1, LAST)
    t0 = time.time()
    cmd = [BLENDER, "-b", BLEND, "--python", os.path.join(HERE, "final_setup.py"), "-o",
           os.path.join(outdir, "f_####"), "-s", str(a), "-e", str(b), "-j", str(step), "-a"]
    env = dict(os.environ, RES_PCT=pct, SAMPLES=samples)
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n_last, t_last, stalled = count(), time.time(), False
    while p.poll() is None:
        time.sleep(5)
        n = count()
        if n != n_last:
            n_last, t_last = n, time.time()
        elif time.time() - t_last > STALL:
            p.kill()
            p.wait()
            stalled = True
            break
    done = count()
    print("chunk %d-%d rc=%s %.0fs%s  (%d/%d frames)" % (
        a, b, p.returncode, time.time() - t0, " STALLED, killed" if stalled else "", done, len(WANT)), flush=True)
    if not have(a):
        stalls[a] = stalls.get(a, 0) + 1
        if stalls[a] >= 3:
            print("no progress on frame %d after 3 tries, stopping" % a, flush=True)
            sys.exit(1)
