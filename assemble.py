"""Frames + soundtrack -> H.264/AAC MP4 that plays inline in Discord.

  python3 assemble.py <framedir> <out.mp4> [step=1] [crf=20]

<framedir> holds f_####.png (every <step>th frame of the 24 fps timeline), so the image rate
is 24/step and the picture stays in sync with audio/soundtrack.wav.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
frames, out = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 1
crf = sys.argv[4] if len(sys.argv) > 4 else "20"

cmd = ["ffmpeg", "-v", "error", "-y",
       "-framerate", "%g" % (24 / step), "-pattern_type", "glob", "-i", os.path.join(frames, "f_*.png"),
       "-i", os.path.join(HERE, "audio", "soundtrack.wav"),
       "-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p", "-r", "24",
       "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",   # online/phone loudness; the raw mix peaks on the bump
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                        "-of", "default=nw=1", out], capture_output=True, text=True).stdout
print(out, probe.replace("\n", "  "))
