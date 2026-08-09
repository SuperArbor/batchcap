#!/bin/bash

# ============================
# Configuration
# ============================

# 只需要修改这里
script_dir = ""

# ============================
# Run BatchCap
# ============================

"${script_dir}/.venv/bin/python" \
    "${script_dir}/BatchCap.py" \
    -p "$(dirname "$BASH_SOURCE")" \
    -s 1 \
    -i \
    -c yellow \
    -n 0.08 \
    -g 270 \
    -r 0.01 \
    -t 5x4 \
    -o \
    -f png