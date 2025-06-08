#!/bin/bash
set -euo pipefail

# Update system packages
sudo apt-get update

# Install Python 3.11 and pip
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Add virtual environment activation to profile
echo "source $(pwd)/venv/bin/activate" >> $HOME/.profile

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Install additional test dependencies explicitly mentioned in CI
pip install "pydantic>=2.10.4" pytest ruff

# Install dev dependencies from pyproject.toml
pip install "pytest>=8.4.0" "pytest-asyncio>=0.23.6" "ruff>=0.4.8"

# Set OPENAI_API_KEY environment variable for tests (some tests require it)
export OPENAI_API_KEY="test"
echo 'export OPENAI_API_KEY="test"' >> $HOME/.profile

# Ensure the current directory is in PYTHONPATH for imports
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
echo "export PYTHONPATH=\"$(pwd):\${PYTHONPATH:-}\"" >> $HOME/.profile