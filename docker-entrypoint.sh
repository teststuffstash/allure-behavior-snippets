#!/bin/sh

set -e

. /venv/bin/activate

allure-behavior-snippets "$1" "$2" "$3"
