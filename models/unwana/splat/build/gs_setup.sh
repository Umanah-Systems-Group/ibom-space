set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv python3-dev git build-essential ninja-build libgl1 libglib2.0-0 >/dev/null
python3 -m venv /w/tools/gs/venv
. /w/tools/gs/venv/bin/activate
pip install -q --upgrade pip wheel setuptools
pip install -q torch --index-url https://download.pytorch.org/whl/cu130
python -c "import torch;print('TORCH',torch.__version__,torch.cuda.is_available(),torch.cuda.get_device_name(0),torch.cuda.get_device_capability(0))"
pip install -q numpy pillow plyfile imageio tqdm torchmetrics
cd /w/tools/gs && rm -rf gsplat && git clone -q --depth 1 --recursive https://github.com/nerfstudio-project/gsplat.git
cd gsplat && TORCH_CUDA_ARCH_LIST="12.1" MAX_JOBS=16 pip install -q --no-build-isolation . 
python -c "import gsplat,torch;print('GSPLAT',gsplat.__version__)"
chown -R $UIDGID /w/tools/gs
