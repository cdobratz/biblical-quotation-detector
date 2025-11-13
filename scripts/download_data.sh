#!/bin/bash

echo "Downloading biblical texts..."

# Download HelloAO Bible Database
cd data/raw
wget https://bible.helloao.org/bible.db
wget https://bible.helloao.org/api.zip

# Clone Greek NT repositories
git clone https://github.com/Center-for-New-Testament-Restoration/SR
git clone https://github.com/Center-for-New-Testament-Restoration/BHP
git clone https://github.com/Center-for-New-Testament-Restoration/transcriptions
git clone https://github.com/biblicalhumanities/sblgnt
git clone https://github.com/eliranwong/OpenGNT

echo "Download complete!"