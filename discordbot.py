from keep_alive import keep_alive

# HTTPサーバー起動
keep_alive()

import discord
import requests
import csv
from io import StringIO
import re
import jaconv
from unidecode import unidecode
from rapidfuzz import fuzz, process
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# === Google Spreadsheet (CSV形式で公開されたURL) ===
CSV_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQcwnmp6pG5pyWdyrbSDIezH9PcgpwgSZv2mpkR5QYbodvYVMPmMH0qK0yKXR3IceGNqoaYZKDTOloj/pub?gid=0&single=true&output=csv'

# === 正規化関数 ===
def normalize(text):
    text = text.lower().strip()
    text = jaconv.kata2hira(text)  # カタカナ→ひらがな
    text = unidecode(text)         # ローマ字変換
    text = re.sub(r'\s+', '', text)  # 空白削除
    return text

# === Google Sheets からデータ取得 ===
def fetch_data():
    response = requests.get(CSV_URL)
    if response.status_code == 200:
        csv_content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(csv_content))
        data = [row for row in csv_reader]
        return data
    else:
        return None

# === Discord Bot ===
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('✅ ログインしました')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    if content.startswith('/vinfo') or content.startswith("/vlist"):
        data = fetch_data()
        if not data:
            await message.channel.send("⚠️ データが取得できませんでした。")
            return

        # === 管理者向け一覧表示 ===
        list_match = re.match(r"/vlist(?:\((\d+)\)|\s+all)?", content)
        if list_match:
            rows = data[5:]
            limit_str = list_match.group(1)
            if "all" in content:
                display_limit = len(rows)
            elif limit_str:
                display_limit = int(limit_str)
            else:
                display_limit = 20

            listing = []
            for i, row in enumerate(rows):
                if len(row) >= 3:
                    listing.append(f"{i}. {row[1].strip()} / {row[2].strip()}")
            response = "📋 登録済み事務所一覧（全{}件中 上位{}件）:\n".format(len(listing), display_limit)
            response += "\n".join(listing[:display_limit])
            await message.channel.send(f"```\n{response}```")
            return

        # No.指定（例：/vinfo(1)）
        match = re.match(r'/vinfo\((\d+)\)', content)
        if match:
            idx = int(match.group(1))
            actual_index = idx + 4
            if actual_index >= len(data):
                await message.channel.send(f"⚠️ No.{idx} はデータ範囲外です（最大 {len(data)-5} 件まで）。")
                return

            labels = data[4]
            values = data[actual_index]
            response = ""
            jp_name = ""
            en_name = ""
            for label, value in zip(labels, values):
                if label.strip() == "事務所名(和名)":
                    jp_name = value.strip()
                elif label.strip() == "事務所名(英名)":
                    en_name = value.strip()
                elif label.strip() == "No.":
                    continue  # 非表示
                else:
                    response += f"{label.strip()} : {value.strip()}\n"
            response = f"事務所名 : {jp_name}/{en_name}\n" + response
            await message.channel.send(f"```\n{response}```")
            return

        # テキスト検索
        query_full = content.replace('/vinfo', '').strip()
        show_score = False
        if query_full.endswith(' score'):
            show_score = True
            query = query_full[:-6].strip()
        else:
            query = query_full

        if not query:
            await message.channel.send("⚠️ 検索ワードが空です。例：`/vinfo ぶいありうむ`")
            return

        query_norm = normalize(query)
        candidates = []

        for row in data[5:]:
            if len(row) >= 3:
                name_jp = normalize(row[1])
                name_en = normalize(row[2])
                combined = row[1] + "/" + row[2]
                score = max(
                    fuzz.ratio(query_norm, name_jp),
                    fuzz.ratio(query_norm, name_en)
                )
                candidates.append((score, combined, row))

        best = max(candidates, key=lambda x: x[0], default=None)

        if best and best[0] >= 50:
            labels = data[4]
            values = best[2]
            response = ""
            if show_score:
                response += f"📋 最も一致する候補: {best[1]}（スコア: {best[0]:.1f}）\n"
            jp_name = ""
            en_name = ""
            body = ""
            for label, value in zip(labels, values):
                if label.strip() == "事務所名(和名)":
                    jp_name = value.strip()
                elif label.strip() == "事務所名(英名)":
                    en_name = value.strip()
                elif label.strip() == "No.":
                    if show_score:
                        body += f"{label.strip()} : {value.strip()}\n"
                    continue
                else:
                    body += f"{label.strip()} : {value.strip()}\n"
            response += f"事務所名 : {jp_name}/{en_name}\n" + body
            await message.channel.send(f"```\n{response}```")
        else:
            await message.channel.send("🔍 一致する事務所が見つかりませんでした。")


    # === VTuber名での検索コマンド (/vtuber) ===
    elif content.startswith('/vtuber'):
        if content.startswith('/vtuber'):
            # データ取得
            data = fetch_data()
            if not data:
                await message.channel.send("⚠️ データが取得できませんでした。")
                return

            # クエリ抽出とスコア表示オプションの処理
            query_full = content.replace('/vtuber', '').strip()
            show_score = False
            if query_full.endswith(' score'):
                show_score = True
                query = query_full[:-6].strip()
            else:
                query = query_full

            if not query:
                await message.channel.send("⚠️ VTuber名を指定してください。例：`/vtuber 天音かなた`")
                return
    
            query_norm = normalize(query)
            candidates = []

            # N列（index 13）にあるVTuber名を正規化してスコア計算
            for row in data[5:]:
                if len(row) > 13:
                    raw_names = row[13]
                    vtuber_names = [normalize(name) for name in re.split(r'[、,]', raw_names)]
                    best_score = max(fuzz.ratio(query_norm, name) for name in vtuber_names)
                    candidates.append((best_score, raw_names, row))

            # 一致度が最も高い候補を抽出
            best = max(candidates, key=lambda x: x[0], default=None)

            if best and best[0] >= 50:
                labels = data[4]
                values = best[2]
                response = ""
                if show_score:
                    response += f"📋 一致候補: {best[1]}（スコア: {best[0]:.1f}）\n"

                # 事務所情報の組み立て
                jp_name = ""
                en_name = ""
                body = ""
                for label, value in zip(labels, values):
                    if label.strip() == "事務所名(和名)":
                        jp_name = value.strip()
                    elif label.strip() == "事務所名(英名)":
                        en_name = value.strip()
                    elif label.strip() == "No.":
                        if show_score:
                            body += f"{label.strip()} : {value.strip()}\n"
                        continue
                    else:
                        body += f"{label.strip()} : {value.strip()}\n"

                # 結果送信
                response += f"事務所名 : {jp_name}/{en_name}\n" + body
                await message.channel.send(f"```\n{response}```")
            else:
                await message.channel.send("🔍 一致するVTuberが見つかりませんでした。")

# === Botの起動 ===
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ エラー: DISCORD_TOKEN が設定されていません")
else:
    client.run(TOKEN)

