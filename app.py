import os
import json
import shutil
import uuid
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Video Summarizer API")

# Mount static files and templates
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure Data dirs exist
RAW_DIR = Path("Data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)
DELIVERABLES_DIR = Path("deliverables")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

from fastapi.responses import StreamingResponse

@app.post("/api/summarize")
async def summarize_video(video: UploadFile = File(...)):
    # Save uploaded file
    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(video.filename)[1] or ".mp4"
    safe_filename = f"upload_{file_id}{ext}"
    video_path = RAW_DIR / safe_filename
    
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
        
    run_id = f"run_web_{file_id}"
    
    async def generate_logs():
        cmd = [
            ".\\venv\\Scripts\\python.exe", "main.py",
            "--video-path", str(video_path),
            "--stage", "g8",
            "--run-id", run_id,
            "--summarize-backend", "local",
            "--summarize-model", r"C:\ZtranCongDuc8125\TOHC\S-GROUP\AI\PROJECT\VIDEO_SUMARIZE\model\checkpoint-650"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        full_stdout = []
        for line in iter(process.stdout.readline, ""):
            # Ensure each line from stdout is sent as a clean line
            if not line.endswith('\n'):
                line += '\n'
            yield line
        
        process.stdout.close()
        return_code = process.wait()
        
        if return_code != 0:
            yield f"__ERROR__: Pipeline failed with code {return_code}\n"
            return

        # Success, find deliverables
        final_dir = DELIVERABLES_DIR / run_id
        summary_video = final_dir / "summary_video.mp4"
        summary_text = final_dir / "summary_text.txt"
        
        if not summary_video.exists() or not summary_text.exists():
            yield "__ERROR__: Deliverables missing (video/text not found)\n"
            return
            
        text_content = summary_text.read_text(encoding="utf-8")
        result_data = {
            "status": "success",
            "run_id": run_id,
            "text": text_content,
            "video_url": f"/api/download/{run_id}/video"
        }
        yield f"__RESULT__:{json.dumps(result_data)}\n"

    return StreamingResponse(generate_logs(), media_type="text/plain")

@app.get("/api/download/{run_id}/video")
async def download_video(run_id: str):
    video_path = DELIVERABLES_DIR / run_id / "summary_video.mp4"
    if video_path.exists():
        return FileResponse(video_path, media_type="video/mp4")
    return JSONResponse(status_code=404, content={"error": "Video not found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
