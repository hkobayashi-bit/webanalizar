"""ユーティリティ関数"""

import csv
import io
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    """URLを正規化"""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def parse_csv_urls(content: bytes) -> list[str]:
    """CSVバイト列からURLリストを抽出"""
    # エンコーディング自動検出
    for encoding in ("utf-8-sig", "utf-8", "shift_jis", "cp932"):
        try:
            text = content.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        text = content.decode("utf-8", errors="ignore")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []

    # URL列を探す
    url_col = None
    for col in reader.fieldnames:
        if col.lower().strip() in ("url", "urls", "website", "domain", "ドメイン", "サイト"):
            url_col = col
            break

    if not url_col:
        # 最初の列にURLっぽいデータがあるか確認
        for col in reader.fieldnames:
            url_col = col
            break

    if not url_col:
        return []

    urls = []
    for row in reader:
        raw = row.get(url_col, "").strip()
        if raw:
            normalized = normalize_url(raw)
            if normalized:
                urls.append(normalized)

    return urls


def build_csv_export(results: list) -> str:
    """スキャン結果をCSV文字列に変換"""
    output = io.StringIO()
    writer = csv.writer(output)

    # ヘッダー
    writer.writerow(["URL", "Status", "Technologies", "Categories", "Details"])

    for r in results:
        tech_names = ", ".join(t.name for t in r.technologies)
        all_cats = set()
        for t in r.technologies:
            all_cats.update(t.categories)
        categories = ", ".join(sorted(all_cats))
        details = "; ".join(
            f"{t.name} ({', '.join(t.categories)}){f' v{t.version}' if t.version else ''}"
            for t in r.technologies
        )
        writer.writerow([
            r.url,
            r.status,
            tech_names,
            categories,
            details,
        ])

    return output.getvalue()
