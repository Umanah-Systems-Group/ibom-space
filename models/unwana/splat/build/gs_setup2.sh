set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv python3-dev git build-essential ninja-build >/dev/null
. /w/tools/gs/venv/bin/activate
cd /w/tools/gs/gsplat
# this world-space (3DGUT) kernel is not used here; instantiate it for RGB/RGBA only so it compiles in minutes
sed -i '46s/dispatch::IntParam<GSPLAT_NUM_CHANNELS>;/dispatch::IntParam<3, 4>;/' gsplat/cuda/csrc/RasterizeToPixelsFromWorld3DGSParallelBatchFwd.cu
sed -n 46p gsplat/cuda/csrc/RasterizeToPixelsFromWorld3DGSParallelBatchFwd.cu
TORCH_CUDA_ARCH_LIST="12.1" MAX_JOBS=16 pip install -q --no-build-isolation .
python -c "import gsplat,torch;print('GSPLAT',gsplat.__version__)"
chown -R $UIDGID /w/tools/gs
