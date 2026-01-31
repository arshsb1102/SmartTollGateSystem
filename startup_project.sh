#!/bin/bash

echo "=== Smart Toll Gate Project Startup Check ==="

# 1. Check venv folder
if [ ! -d "venv" ]; then
  echo "❌ Virtual environment not found."
  echo "Run: python3 -m venv venv"
  exit 1
fi

# 2. Activate venv
echo "Activating virtual environment..."
echo "source venv/bin/activate # (run this command in your terminal)"


# 3. Check Python
echo "Checking Python..."
python --version || { echo "❌ Python not working"; exit 1; }

# 4. Check pip
echo "Checking pip..."
pip --version || { echo "❌ pip not working"; exit 1; }

# 5. Check required Python packages
echo "Checking Python packages..."

REQUIRED_PACKAGES=("opencv-python" "pytesseract" "numpy")

for pkg in "${REQUIRED_PACKAGES[@]}"; do
  pip show $pkg > /dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "❌ Missing package: $pkg"
    echo "Run: pip install -r requirements.txt"
    exit 1
  else
    echo "✔ $pkg installed"
  fi
done

# 6. Check Tesseract OCR
echo "Checking Tesseract OCR..."
if ! command -v tesseract &> /dev/null; then
  echo "❌ Tesseract not installed."
  echo "Run: brew install tesseract"
  exit 1
else
  echo "✔ Tesseract installed"
fi

# 7. Camera permission reminder
echo "⚠️  Ensure Terminal has Camera permission (macOS)"
echo "System Settings → Privacy & Security → Camera"

echo ""
echo "✅ All checks passed."
echo "You are ready to run the Smart Toll Gate project."
echo ""
