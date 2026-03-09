#!/usr/bin/env bash

read -p "Enter migration message: " msg

if [ -z "$msg" ]; then
  echo "Migration message cannot be empty."
  exit 1
fi

uv run alembic revision --autogenerate -m "$msg"
