#!/bin/bash

# Optional: Exit on any error
set -e

echo "🔧 Creating virtual environment (if not exists)..."
python3 -m venv venv

echo "✅ Virtual environment ready."

echo "📦 Installing requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Requirements installed."

echo "⚙️ Setting up PM2 to run the scraper..."
# Name the process "abtirsi-scraper"
pm2 start venv/bin/python3 --name abtirsi-scraper -- abtirsi_scraper_async.py

echo "💾 Saving PM2 config..."
pm2 save

echo "🔁 Set PM2 to launch on system startup..."
pm2 startup systemd -u $USER --hp $HOME

echo "🚀 Scraper is now running with PM2 and will restart on reboot."
