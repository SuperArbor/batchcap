#!/bin/bash

batchcap \
    "$(dirname "$BASH_SOURCE")" \
    -s 1 \
    -i \
    -c yellow \
    -n 0.08 \
    -g 270 \
    -r 0.01 \
    -t 4x4 \
    -o \
    -f png \
    