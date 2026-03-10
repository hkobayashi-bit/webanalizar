"""
技術検出エンジン
HTTP レスポンス（ヘッダー、HTML、Cookie）からWappalyzerシグネチャに基づいて技術を検出
"""

import re
from dataclasses import dataclass, field

from .signatures import load_signatures, load_categories


@dataclass
class PageData:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    html: str = ""
    cookies: dict[str, str] = field(default_factory=dict)
    scripts: list[str] = field(default_factory=list)
    meta_tags: dict[str, str] = field(default_factory=dict)


@dataclass
class DetectedTech:
    name: str
    categories: list[str] = field(default_factory=list)
    confidence: int = 0
    version: str = ""
    icon: str = ""
    website: str = ""


def _parse_pattern(pattern_str: str) -> tuple[str, int, str | None]:
    """
    Wappalyzerパターン文字列をパース
    形式: regex\\;confidence:N\\;version:\\1
    戻り値: (regex, confidence, version_group)
    """
    parts = pattern_str.split("\\;")
    regex = parts[0]
    confidence = 100
    version_group = None

    for part in parts[1:]:
        if part.startswith("confidence:"):
            try:
                confidence = int(part.split(":")[1])
            except (ValueError, IndexError):
                pass
        elif part.startswith("version:"):
            version_group = part.split(":", 1)[1] if ":" in part else None

    return regex, confidence, version_group


def _match_pattern(pattern_str: str, text: str) -> tuple[bool, int, str]:
    """パターンをテキストに対してマッチング"""
    if not pattern_str or not text:
        return False, 0, ""

    regex, confidence, version_group = _parse_pattern(pattern_str)
    if not regex:
        return True, confidence, ""

    try:
        match = re.search(regex, text, re.IGNORECASE)
        if match:
            version = ""
            if version_group:
                # \1, \2 などのバックリファレンスを解決
                version = version_group
                for i, group in enumerate(match.groups(), 1):
                    if group:
                        version = version.replace(f"\\{i}", group)
                # 未解決のバックリファレンスを除去
                version = re.sub(r"\\[0-9]", "", version).strip()
            return True, confidence, version
        return False, 0, ""
    except re.error:
        return False, 0, ""


def _ensure_list(value) -> list:
    """値をリストに変換"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return list(value.items())
    return []


def detect_technologies(page_data: PageData) -> list[DetectedTech]:
    """ページデータから使用技術を検出"""
    signatures = load_signatures()
    categories = load_categories()

    detected: dict[str, DetectedTech] = {}

    for tech_name, tech_sig in signatures.items():
        total_confidence = 0
        version = ""

        # headers マッチング
        if "headers" in tech_sig and isinstance(tech_sig["headers"], dict):
            for header_name, pattern in tech_sig["headers"].items():
                header_val = page_data.headers.get(header_name.lower(), "")
                if header_val:
                    for p in _ensure_list(pattern):
                        if isinstance(p, str):
                            matched, conf, ver = _match_pattern(p, header_val)
                            if matched:
                                total_confidence += conf
                                if ver:
                                    version = ver

        # html マッチング
        if "html" in tech_sig:
            for pattern in _ensure_list(tech_sig["html"]):
                if isinstance(pattern, str):
                    matched, conf, ver = _match_pattern(pattern, page_data.html)
                    if matched:
                        total_confidence += conf
                        if ver:
                            version = ver

        # scripts マッチング
        if "scripts" in tech_sig:
            for pattern in _ensure_list(tech_sig["scripts"]):
                if isinstance(pattern, str):
                    for script_src in page_data.scripts:
                        matched, conf, ver = _match_pattern(pattern, script_src)
                        if matched:
                            total_confidence += conf
                            if ver:
                                version = ver
                            break

        # meta マッチング
        if "meta" in tech_sig and isinstance(tech_sig["meta"], dict):
            for meta_name, pattern in tech_sig["meta"].items():
                meta_val = page_data.meta_tags.get(meta_name.lower(), "")
                if meta_val:
                    for p in _ensure_list(pattern):
                        if isinstance(p, str):
                            matched, conf, ver = _match_pattern(p, meta_val)
                            if matched:
                                total_confidence += conf
                                if ver:
                                    version = ver

        # cookies マッチング
        if "cookies" in tech_sig and isinstance(tech_sig["cookies"], dict):
            for cookie_name, pattern in tech_sig["cookies"].items():
                cookie_val = page_data.cookies.get(cookie_name, "")
                if cookie_name in page_data.cookies:
                    if isinstance(pattern, str) and pattern:
                        matched, conf, ver = _match_pattern(pattern, cookie_val)
                        if matched:
                            total_confidence += conf
                            if ver:
                                version = ver
                    else:
                        total_confidence += 100

        # URL マッチング
        if "url" in tech_sig:
            for pattern in _ensure_list(tech_sig["url"]):
                if isinstance(pattern, str):
                    matched, conf, ver = _match_pattern(pattern, page_data.url)
                    if matched:
                        total_confidence += conf
                        if ver:
                            version = ver

        if total_confidence > 0:
            # カテゴリ名を解決
            cat_ids = tech_sig.get("cats", [])
            cat_names = [categories.get(int(c), f"Category {c}") for c in cat_ids]

            detected[tech_name] = DetectedTech(
                name=tech_name,
                categories=cat_names,
                confidence=min(total_confidence, 100),
                version=version,
                icon=tech_sig.get("icon", ""),
                website=tech_sig.get("website", ""),
            )

    # implies チェーン解決
    _resolve_implies(detected, signatures, categories)

    return sorted(detected.values(), key=lambda t: t.confidence, reverse=True)


def _resolve_implies(
    detected: dict[str, DetectedTech],
    signatures: dict,
    categories: dict[int, str],
):
    """implies チェーンを解決して暗示される技術を追加"""
    added = True
    iterations = 0
    while added and iterations < 10:
        added = False
        iterations += 1
        for tech_name in list(detected.keys()):
            sig = signatures.get(tech_name, {})
            implies = sig.get("implies", [])
            if isinstance(implies, str):
                implies = [implies]
            for implied in implies:
                if isinstance(implied, str):
                    imp_name = implied.split("\\;")[0]
                    if imp_name in signatures and imp_name not in detected:
                        imp_sig = signatures[imp_name]
                        cat_ids = imp_sig.get("cats", [])
                        cat_names = [categories.get(int(c), f"Category {c}") for c in cat_ids]
                        detected[imp_name] = DetectedTech(
                            name=imp_name,
                            categories=cat_names,
                            confidence=50,
                            icon=imp_sig.get("icon", ""),
                            website=imp_sig.get("website", ""),
                        )
                        added = True
