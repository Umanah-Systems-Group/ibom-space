"""Encode a PNG sequence to H.264 MP4 with Blender's built-in FFmpeg.
Run: blender -b --factory-startup -P encode_mp4.py -- <frames_dir> <out.mp4> <fps>"""
import bpy, os, sys
d, out, fps = sys.argv[sys.argv.index("--") + 1:][:3]
files = sorted(f for f in os.listdir(d) if f.startswith("frame_") and f.endswith(".png"))
sc = bpy.context.scene
sc.sequence_editor_create()
strip = sc.sequence_editor.sequences.new_image("tt", os.path.join(d, files[0]), 1, 1)
for f in files[1:]:
    strip.elements.append(f)
sc.frame_start, sc.frame_end = 1, len(files)
sc.render.fps = int(fps)
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'Standard'
r = sc.render
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format = 'MPEG4'; r.ffmpeg.codec = 'H264'
r.ffmpeg.constant_rate_factor = 'HIGH'; r.ffmpeg.ffmpeg_preset = 'GOOD'
r.filepath = out
bpy.ops.render.render(animation=True)
print("MP4_OK", out)
