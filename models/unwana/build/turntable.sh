#!/bin/bash
# 360-degree turntable: 72 frames at 1920x1080 (denoised), then encoded to MP4 (H.264, 24 fps = 3 s loop).
cd /home/daedyl/unwana-model
TURNTABLE=72 ./run_blender.sh unwana.blend -P render_views.py -- $PWD/out/turntable 1920 1080 96 Turntable
./run_blender.sh --factory-startup -P encode_mp4.py -- $PWD/out/turntable $PWD/out/unwana-turntable.mp4 24
echo TURNTABLE_DONE
