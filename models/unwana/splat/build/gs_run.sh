# usage (inside the CUDA container): bash /w/gs_run.sh <args for splat_train.py>
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq python3 python3-dev libgomp1 >/dev/null 2>&1
. /w/tools/gs/venv/bin/activate
cd /w
python -u ${SCRIPT:-splat_train.py} "$@"
chown -R $UIDGID /w/splat
