"""
非同期URLスキャナー
URLにアクセスし、レスポンスから技術検出を行う
"""

import asyncio
import httpx
from bs4 import BeautifulSoup

from .detector import PageData, detect_technologies, DetectedTech
from .models import ScanResult, TechInfo

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

MAX_BODY_SIZE = 500_000  # 500KB


def _extract_page_data(url: str, response: httpx.Response) -> PageData:
    """HTTPレスポンスからPageDataを構築"""
    headers = {k.lower(): v for k, v in response.headers.items()}
    html = response.text[:MAX_BODY_SIZE]

    # Cookie抽出
    cookies = {c.name: c.value or "" for c in response.cookies.jar}

    # HTML解析
    scripts = []
    meta_tags = {}
    try:
        soup = BeautifulSoup(html, "lxml")

        # <script src="..."> を抽出
        for tag in soup.find_all("script", src=True):
            scripts.append(tag["src"])

        # <meta name="..." content="..."> を抽出
        for tag in soup.find_all("meta"):
            name = tag.get("name", "") or tag.get("property", "")
            content = tag.get("content", "")
            if name and content:
                meta_tags[name.lower()] = content

    except Exception:
        pass

    return PageData(
        url=str(response.url),
        headers=headers,
        html=html,
        cookies=cookies,
        scripts=scripts,
        meta_tags=meta_tags,
    )


def _tech_to_info(tech: DetectedTech) -> TechInfo:
    return TechInfo(
        name=tech.name,
        categories=tech.categories,
        confidence=tech.confidence,
        version=tech.version,
        icon=tech.icon,
        website=tech.website,
    )


async def scan_url(client: httpx.AsyncClient, url: str) -> ScanResult:
    """単一URLをスキャンして技術検出"""
    try:
        response = await client.get(url, follow_redirects=True)
        page_data = _extract_page_data(url, response)
        techs = detect_technologies(page_data)
        return ScanResult(
            url=url,
            status="success",
            technologies=[_tech_to_info(t) for t in techs],
        )
    except httpx.TimeoutException:
        return ScanResult(url=url, status="timeout", error_message="Request timed out")
    except Exception as e:
        return ScanResult(url=url, status="error", error_message=str(e)[:200])


async def scan_urls(
    urls: list[str],
    concurrency: int = 10,
    on_progress=None,
) -> list[ScanResult]:
    """複数URLを並列スキャン"""
    semaphore = asyncio.Semaphore(concurrency)
    results: list[ScanResult] = []
    completed = 0

    async def _scan_one(url: str):
        nonlocal completed
        async with semaphore:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                headers={"User-Agent": USER_AGENTS[0]},
                verify=False,
            ) as client:
                result = await scan_url(client, url)
                results.append(result)
                completed += 1
                if on_progress:
                    await on_progress(completed, result)
                return result

    tasks = [asyncio.create_task(_scan_one(url)) for url in urls]
    await asyncio.gather(*tasks, return_exceptions=True)

    return results
