#!/bin/bash
# Run the Spark's pinned Blender 4.3.2 (ARM64 container) on a script in this folder.
# Usage: ./run_blender.sh [blend] -P script.py -- args
W=/home/daedyl/unwana-model
exec docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e LANG=C.UTF-8 \
  -e TURNTABLE=${TURNTABLE:-0} -e LD_LIBRARY_PATH=$W/tools/oidn/lib -e OIDN_BIN=$W/tools/oidn/bin/oidnDenoise \
  -v /home/daedyl/projects/mccoy-engines/blender-pydeps:/usr/local/lib/python3.13/dist-packages:ro \
  -v $W:$W -w $W --label unwana=1 daedyl-blender:4.3.2-arm64 blender -b "$@"
