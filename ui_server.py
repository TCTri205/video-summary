from fastapi import FastAPI, Request, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import json
import os
import asyncio
import uuid
import shutil
import subprocess
import sys
from pathlib import Path

app = FastAPI(title="Video Summarizer UI", version="1.0.0")

# Setup template and static folders
if not os.path.exists("templates"):
    os.makedirs("templates")

if not os.path.exists("static"):
    os.makedirs("static")

if not os.path.exists("Data/raw"):
    os.makedirs("Data/raw", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount deliverables safely
if not os.path.exists("deliverables"):
    os.makedirs("deliverables")
app.mount("/deliverables", StaticFiles(directory="deliverables"), name="deliverables")

templates = Jinja2Templates(directory="templates")
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
REQUIRED_MODULES = ("cv2", "torch", "transformers", "faster_whisper", "scenedetect", "jsonschema")


def _tail_text(text: str, max_lines: int = 30, max_chars: int = 4000) -> str:
    lines = text.strip().splitlines()
    tail = "\n".join(lines[-max_lines:])
    return tail[-max_chars:].strip()


def _project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "main.py").exists():
        return cwd
    return Path(__file__).resolve().parent


def _pipeline_python_candidates() -> list[Path]:
    repo_root = _project_root()
    configured = os.getenv("VIDEO_SUMMARY_PIPELINE_PYTHON", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(repo_root / "venv" / "Scripts" / "python.exe")
    candidates.append(Path(sys.executable))
    return candidates


def _resolve_pipeline_python() -> Path:
    configured = os.getenv("VIDEO_SUMMARY_PIPELINE_PYTHON", "").strip()
    if configured:
        configured_path = Path(configured)
        if not configured_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Configured pipeline interpreter does not exist: {configured_path}",
            )
        return configured_path

    for candidate in _pipeline_python_candidates()[1:]:
        if candidate.exists():
            return candidate

    raise HTTPException(
        status_code=500,
        detail="Unable to locate a Python interpreter for the pipeline.",
    )


def _safe_upload_path(unique_id: str, original_filename: str) -> Path:
    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only video files are allowed")
    return Path("Data/raw") / f"upload_{unique_id}{suffix}"


def _check_python_modules(python_path: Path) -> list[str]:
    probe_code = (
        "import importlib.util\n"
        "modules = " + repr(REQUIRED_MODULES) + "\n"
        "missing = [name for name in modules if importlib.util.find_spec(name) is None]\n"
        "print('\\n'.join(missing))\n"
    )
    result = subprocess.run(
        [str(python_path), "-c", probe_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        failure_detail = _tail_text(result.stderr) or _tail_text(result.stdout) or "Dependency probe failed."
        raise HTTPException(
            status_code=500,
            detail=f"Failed to inspect pipeline interpreter {python_path}: {failure_detail}",
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _run_pipeline_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        cwd=str(_project_root()),
    )


def _preflight_runtime(python_path: Path) -> None:
    missing_bins = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing_bins:
        raise HTTPException(
            status_code=500,
            detail=f"Missing system dependency: {', '.join(missing_bins)}",
        )

    missing_modules = _check_python_modules(python_path)
    if missing_modules:
        raise HTTPException(
            status_code=500,
            detail=f"Missing Python dependency in {python_path}: {', '.join(missing_modules)}",
        )

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/summarize")
async def summarize_video(file: UploadFile = File(...)):
    pipeline_python = _resolve_pipeline_python()
    _preflight_runtime(pipeline_python)

    unique_id = uuid.uuid4().hex[:8]
    run_id = f"run_ui_{unique_id}"
    file_path = _safe_upload_path(unique_id, file.filename)
    
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"[{run_id}] Saved uploaded file to {file_path}")
        
        cmd = [
            str(pipeline_python), "main.py",
            "--video-path", str(file_path),
            "--run-id", run_id
        ]

        print(f"[{run_id}] Pipeline interpreter: {pipeline_python}")
        print(f"[{run_id}] Executing: {' '.join(cmd)}")

        process = await asyncio.to_thread(_run_pipeline_command, cmd)
        stdout_text = process.stdout or ""
        stderr_text = process.stderr or ""
        
        if process.returncode != 0:
            print(f"[{run_id}] Pipeline failed with code {process.returncode}")
            if stdout_text:
                print(f"[{run_id}] STDOUT tail:\n{_tail_text(stdout_text)}")
            if stderr_text:
                print(f"[{run_id}] STDERR tail:\n{_tail_text(stderr_text)}")

            failure_detail = _tail_text(stderr_text) or _tail_text(stdout_text) or "Video processing pipeline failed."
            raise HTTPException(status_code=500, detail=failure_detail)

        deliverable_dir = os.path.join("deliverables", run_id)
        video_output = os.path.join(deliverable_dir, "summary_video.mp4")
        text_output = os.path.join(deliverable_dir, "summary_text.txt")
        
        if not os.path.exists(video_output) or not os.path.exists(text_output):
            raise HTTPException(status_code=500, detail="Pipeline succeeded but deliverables are missing.")
            
        with open(text_output, "r", encoding="utf-8") as f:
            summary_text = f.read()

        quality_status = "unknown"
        quality_report_path = Path("artifacts") / run_id / "g8_qc" / "quality_report.json"
        if quality_report_path.exists():
            with quality_report_path.open("r", encoding="utf-8") as f:
                quality_report = json.load(f)
            quality_status = str(quality_report.get("overall_status", "unknown")).lower()
            if quality_status != "pass":
                raise HTTPException(
                    status_code=500,
                    detail=f"Pipeline finished but QC status is {quality_status}.",
                )
            
        return JSONResponse(content={
            "success": True,
            "run_id": run_id,
            "video_url": f"/deliverables/{run_id}/summary_video.mp4",
            "summary_text": summary_text,
            "quality_status": quality_status,
            "pipeline_python": str(pipeline_python),
        })
    except HTTPException as exc:
        print(f"[{run_id}] Request failed: {exc.detail}")
        raise exc
    except Exception as e:
        print(f"[{run_id}] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ui_server:app", host="0.0.0.0", port=8000, reload=True)
