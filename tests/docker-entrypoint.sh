#!/bin/sh

set -e

#. /venv/bin/activate

pytest "$@"
#pytest --config-file=pytest-docker.ini acceptance_tests.py