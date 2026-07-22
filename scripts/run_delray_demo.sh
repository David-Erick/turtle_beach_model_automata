#!/usr/bin/env sh
set -eu
python -m turtle_beach_model.cli demo \
  --config configs/delray_demo.yaml \
  --output-dir outputs_demo \
  --quick \
  --synthetic-replicates 4 \
  --synthetic-turtles 25 \
  --replicates 8 \
  --n-turtles 30 \
  --validation-data-replicates 2 \
  --validation-replicates 4 \
  --validation-turtles 20 \
  --sensitivity-samples 16 \
  --sensitivity-turtles 15
