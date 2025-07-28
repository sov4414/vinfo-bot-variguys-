#!/bin/bash

# Bot をバックグラウンドで起動
python3 discordbot.py &

# ダミーの HTTP サーバーでポートを開ける（Render 対策）
python3 -m http.server 8001