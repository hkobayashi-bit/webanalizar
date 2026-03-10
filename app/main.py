"""FastAPI アプリケーション"""

import asyncio
import json
import uuid
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import Job, JobStatus, ScanResult
from .scanner import scan_url, scan_urls
from .signatures import download_signatures, load_signatures, load_categories, clear_cache
from .utils import normalize_url, parse_csv_urls, build_csv_export

import httpx

app = FastAPI(title="WebAnalizar")

# ジョブストア
jobs: dict[str, Job] = {}


@app.on_event("startup")
async def startup():
    """起動時にシグネチャをダウンロード"""
    print("シグネチャをダウンロード中...")
    await download_signatures()
    sigs = load_signatures()
    cats = load_categories()
    print(f"シグネチャ読み込み完了: {len(sigs)} 技術, {len(cats)} カテゴリ")


# 静的ファイル
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/scan")
async def start_scan(
    url: str = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    """スキャンジョブを開始"""
    urls = []

    if file and file.filename:
        content = await file.read()
        urls = parse_csv_urls(content)
        if not urls:
            raise HTTPException(400, "CSVからURLを抽出できませんでした")
    elif url:
        normalized = normalize_url(url)
        if not normalized:
            raise HTTPException(400, "無効なURLです")
        urls = [normalized]
    else:
        raise HTTPException(400, "URLまたはCSVファイルを指定してください")

    job_id = str(uuid.uuid4())
    job = Job(id=job_id, status=JobStatus.PENDING, total=len(urls), created_at=datetime.now())
    jobs[job_id] = job

    # バックグラウンドでスキャン開始
    asyncio.create_task(_run_scan(job_id, urls))

    return {"job_id": job_id, "total": len(urls)}


async def _run_scan(job_id: str, urls: list[str]):
    """バックグラウンドスキャン実行"""
    job = jobs[job_id]
    job.status = JobStatus.RUNNING

    async def on_progress(completed: int, result: ScanResult):
        job.completed = completed
        job.results.append(result)

    try:
        await scan_urls(urls, concurrency=10, on_progress=on_progress)
        job.status = JobStatus.COMPLETED
    except Exception as e:
        job.status = JobStatus.FAILED
        print(f"Scan failed: {e}")


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """ジョブ状態を取得"""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "ジョブが見つかりません")
    return {
        "id": job.id,
        "status": job.status.value,
        "total": job.total,
        "completed": job.completed,
        "results": [r.model_dump() for r in job.results],
    }


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """SSEでジョブ進捗をストリーミング"""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "ジョブが見つかりません")

    async def event_generator():
        last_sent = 0
        while True:
            if len(job.results) > last_sent:
                for i in range(last_sent, len(job.results)):
                    result = job.results[i]
                    data = json.dumps({
                        "completed": i + 1,
                        "total": job.total,
                        "result": result.model_dump(),
                    }, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                last_sent = len(job.results)

            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                yield f"data: {json.dumps({'done': True, 'status': job.status.value})}\n\n"
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/{job_id}/export")
async def export_job(job_id: str):
    """結果をCSVとしてエクスポート"""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "ジョブが見つかりません")

    csv_content = build_csv_export(job.results)
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=result.csv"},
    )


@app.post("/api/scan-single")
async def scan_single(url: str = Form(...)):
    """単一URLを即座にスキャンして結果を返す"""
    normalized = normalize_url(url)
    if not normalized:
        raise HTTPException(400, "無効なURLです")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        verify=False,
    ) as client:
        result = await scan_url(client, normalized)

    return result.model_dump()


@app.post("/api/update-signatures")
async def update_signatures():
    """シグネチャを更新"""
    clear_cache()
    await download_signatures(force=True)
    sigs = load_signatures()
    return {"message": f"シグネチャ更新完了: {len(sigs)} 技術"}
