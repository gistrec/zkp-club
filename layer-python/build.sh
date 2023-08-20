#!/usr/bin/env bash

BASE_DIR=$(dirname "$0")
PYTHON_DIR="$BASE_DIR/python"

rm -rf $PYTHON_DIR

pip3 install urllib3==1.26.6 -t $PYTHON_DIR  # Fix OpenSSL issue
pip3 install boto3 sentry-sdk python-telegram-bot -t $PYTHON_DIR
