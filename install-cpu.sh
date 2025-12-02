#!/bin/bash
# Install CPU-only PyTorch to avoid CUDA dependencies
# This script installs all dependencies with CPU-only PyTorch

echo "Installing dependencies with CPU-only PyTorch..."
pip install -r requirements-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu

echo ""
echo "Installation complete!"
echo "PyTorch will use CPU only (no CUDA dependencies installed)"

