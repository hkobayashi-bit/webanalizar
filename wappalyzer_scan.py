"""
Wappalyzer API を使った技術調査自動化スクリプト
入力: フォーム営業リスト (1).csv
出力: result.csv
"""

import pandas as pd
import requests
import time
import sys
from urllib.parse import urlparse
from tqdm import tqdm

# ===== ここにAPIキーを設定 =====
API_KEY = "YOUR_API_KEY_HERE"

# 設定
INPUT_FILE = "フォーム営業リスト (1).csv"
OUTPUT_FILE = "result.csv"
SLEEP_SECONDS = 1.0
TARGET_CATEGORIES = {"CMS", "Analytics", "CRM", "Advertising"}

WAPPALYZER_API_URL = "https://api.wappalyzer.com/v2/lookup/"


def extract_domain(url: str) -> str:
    """URLからドメインを抽出する"""
    if not url or pd.isna(url):
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0]
    except Exception:
        return ""


def lookup_technologies(domain: str) -> dict:
    """Wappalyzer APIで技術情報を取得する"""
    headers = {"x-api-key": API_KEY}
    params = {"urls": domain}

    resp = requests.get(WAPPALYZER_API_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = {cat: [] for cat in TARGET_CATEGORIES}

    # APIレスポンスはリスト形式
    for entry in data:
        for tech in entry.get("technologies", []):
            tech_name = tech.get("name", "")
            for cat in tech.get("categories", []):
                cat_name = cat.get("name", "")
                if cat_name in TARGET_CATEGORIES and tech_name not in results[cat_name]:
                    results[cat_name].append(tech_name)

    return {cat: ", ".join(techs) for cat, techs in results.items()}


def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("エラー: API_KEY を設定してください。")
        print("Wappalyzer の API キーを取得し、スクリプト上部の API_KEY 変数に設定してください。")
        sys.exit(1)

    # CSV読み込み
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")
    print(f"読み込み完了: {len(df)} 件")

    # URLが空の行をフィルタ（元データは保持）
    has_url = df["url"].notna() & (df["url"].str.strip() != "")
    print(f"URL あり: {has_url.sum()} 件 / URL なし: {(~has_url).sum()} 件")

    # 結果列を初期化
    for cat in TARGET_CATEGORIES:
        df[cat] = ""

    # URL がある行のみ API を叩く
    indices = df[has_url].index.tolist()

    for idx in tqdm(indices, desc="技術調査中", unit="件"):
        url = df.at[idx, "url"]
        domain = extract_domain(url)
        if not domain:
            for cat in TARGET_CATEGORIES:
                df.at[idx, cat] = "Error: invalid URL"
            continue

        try:
            techs = lookup_technologies(domain)
            for cat in TARGET_CATEGORIES:
                df.at[idx, cat] = techs.get(cat, "")
        except Exception as e:
            for cat in TARGET_CATEGORIES:
                df.at[idx, cat] = f"Error: {type(e).__name__}"

        time.sleep(SLEEP_SECONDS)

    # 保存
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n完了！結果を {OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
