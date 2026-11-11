#!/bin/bash
# Final stills: 10 named views at 3840x2160 / 200 spp, close-ups at 2560x1440 / 256 spp (all OIDN-denoised).
cd /home/daedyl/unwana-model
./run_blender.sh unwana.blend -P render_views.py -- $PWD/out/renders 3840 2160 200 \
  Front Rear Left Right Top Bottom FrontLeftIso FrontRightIso RearLeftIso RearRightIso
./run_blender.sh unwana.blend -P render_views.py -- $PWD/out/closeups 2560 1440 256 \
  Closeup_OpticalTerminal Closeup_MLISeam Closeup_Nozzle Closeup_SolarHinge Closeup_Imager
echo FINALS_DONE
