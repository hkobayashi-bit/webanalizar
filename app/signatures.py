"""
技術シグネチャの取得・管理
enthec/webappanalyzer (Wappalyzerオープンソースフォーク) のシグネチャを使用
"""

import json
import os
import string
import httpx

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "technologies")
CATEGORIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "categories.json")

BASE_URL = "https://raw.githubusercontent.com/AliasIO/wappalyzer/refs/heads/master/src/technologies"
CATEGORIES_URL = "https://raw.githubusercontent.com/AliasIO/wappalyzer/refs/heads/master/src/categories.json"

# Fallback URLs (enthec fork)
FALLBACK_BASE_URL = "https://raw.githubusercontent.com/enthec/webappanalyzer/main/src/technologies"
FALLBACK_CATEGORIES_URL = "https://raw.githubusercontent.com/enthec/webappanalyzer/main/src/categories.json"

# Technology signature file names: _.json, a.json - z.json
TECH_FILES = ["_.json"] + [f"{c}.json" for c in string.ascii_lowercase]

_signatures_cache: dict | None = None
_categories_cache: dict | None = None


async def download_signatures(force: bool = False) -> None:
    """GitHub からシグネチャファイルをダウンロード"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if not force and _all_files_exist():
        return

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # カテゴリファイル
        try:
            resp = await client.get(CATEGORIES_URL)
            resp.raise_for_status()
            with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
                f.write(resp.text)
        except Exception:
            try:
                resp = await client.get(FALLBACK_CATEGORIES_URL)
                resp.raise_for_status()
                with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
                    f.write(resp.text)
            except Exception as e:
                print(f"Warning: Failed to download categories.json: {e}")

        # 技術ファイル
        for filename in TECH_FILES:
            filepath = os.path.join(DATA_DIR, filename)
            if not force and os.path.exists(filepath):
                continue
            try:
                url = f"{BASE_URL}/{filename}"
                resp = await client.get(url)
                resp.raise_for_status()
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(resp.text)
            except Exception:
                try:
                    url = f"{FALLBACK_BASE_URL}/{filename}"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(resp.text)
                except Exception as e2:
                    print(f"Warning: Failed to download {filename}: {e2}")


def _all_files_exist() -> bool:
    if not os.path.exists(CATEGORIES_FILE):
        return False
    return all(os.path.exists(os.path.join(DATA_DIR, f)) for f in TECH_FILES)


def load_categories() -> dict[int, str]:
    """カテゴリID -> カテゴリ名のマッピングを返す"""
    global _categories_cache
    if _categories_cache is not None:
        return _categories_cache

    if not os.path.exists(CATEGORIES_FILE):
        return {}

    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    _categories_cache = {int(k): v.get("name", "") for k, v in data.items()}
    return _categories_cache


def load_signatures() -> dict:
    """全技術シグネチャを統合して返す"""
    global _signatures_cache
    if _signatures_cache is not None:
        return _signatures_cache

    all_techs = {}
    for filename in TECH_FILES:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                all_techs.update(data)
            except json.JSONDecodeError:
                continue

    _signatures_cache = all_techs
    return _signatures_cache


def clear_cache():
    global _signatures_cache, _categories_cache
    _signatures_cache = None
    _categories_cache = None
