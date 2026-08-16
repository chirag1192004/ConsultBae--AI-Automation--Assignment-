import os
import re
import json
import shutil
import urllib.request
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from audio_utils import get_audio_metadata

app = FastAPI()

# Setup directories
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

# Mount static files for UI and audio streaming
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

def get_db_connection():
    return psycopg2.connect(
        dbname="cbnexus_db",
        user="admin",
        password="password123",
        host="localhost",
        port="5433"
    )

def clean_phone(phone: str) -> str:
    """Exact standardization logic from Task 1."""
    if not phone: return ""
    s = str(phone)
    cleaned_s = re.sub(r'\D', '', s)
    if len(cleaned_s) > 10 and cleaned_s.startswith('91'):
        cleaned_s = cleaned_s[2:]
    elif len(cleaned_s) > 10 and cleaned_s.startswith('0'):
        cleaned_s = cleaned_s[1:]
    return cleaned_s

@app.post("/api/upload")
async def upload_audio(
    name: str = Form(...),
    phone: str = Form(...),
    audio: UploadFile = File(...),
    client_duration: float = Form(None),
    client_loudness: float = Form(None),
    client_sample_rate: float = Form(None)
):
    try:
        # Save file locally
        file_ext = audio.filename.split(".")[-1] if "." in audio.filename else "webm"
        safe_filename = f"{phone}_{audio.filename}".replace(" ", "_")
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
            
        # Extract metadata
        metrics = get_audio_metadata(
            file_path,
            client_duration=client_duration,
            client_loudness=client_loudness,
            client_sample_rate=client_sample_rate
        )
        
        # Connect to DB and handle entity linking
        conn = get_db_connection()
        cur = conn.cursor()
        
        cleaned_phone = clean_phone(phone)
        
        # Check if worker exists
        cur.execute('SELECT id FROM consolidated_profiles WHERE "Phone" = %s', (cleaned_phone,))
        result = cur.fetchone()
        
        # Ensure worker exists in profiles
        if result:
            worker_id = result[0]
        else:
            # Create new profile to prevent orphans
            cur.execute(
                'INSERT INTO consolidated_profiles ("Full Name", "Phone", "City") VALUES (%s, %s, %s) RETURNING id',
                (name.title(), cleaned_phone, "Unknown (From Audio App)")
            )
            worker_id = cur.fetchone()[0]
            
        conn.commit()
        cur.close()
        conn.close()

        # Fire webhook to n8n for AI orchestration (if n8n workflow is active)
        webhook_url = "http://localhost:5678/webhook-test/audio-triage"
        payload = {
            "worker_id": worker_id,
            "phone": cleaned_phone,
            "worker_name": name.title(),
            "audio_file_name": safe_filename,
            "duration_sec": metrics["duration_sec"],
            "sample_rate_khz": metrics["sample_rate_khz"],
            "bitrate_kbps": metrics["bitrate_kbps"],
            "loudness_db": metrics["loudness_db"]
        }
        
        try:
            req = urllib.request.Request(
                webhook_url, 
                data=json.dumps(payload).encode('utf-8'), 
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception as e:
            # If webhook-test fails, try production webhook
            try:
                prod_url = "http://localhost:5678/webhook/audio-triage"
                req = urllib.request.Request(
                    prod_url, 
                    data=json.dumps(payload).encode('utf-8'), 
                    headers={'Content-Type': 'application/json'}
                )
                urllib.request.urlopen(req, timeout=3)
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                # Webhook failed entirely, data won't enter audio_submissions
                pass
        
        return JSONResponse({"status": "success", "metrics": metrics, "worker_id": worker_id})
        
    except Exception as e:
        print(f"Error processing upload: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/submissions")
async def get_submissions():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT a.id, a.worker_name, a.phone, a.audio_file_name, a.duration_sec, 
                   a.sample_rate_khz, a.bitrate_kbps, a.loudness_db, a.qa_status, 
                   a.quality_tier, a.created_at, c."City"
            FROM audio_submissions a
            LEFT JOIN consolidated_profiles c ON a.worker_id = c.id
            ORDER BY a.created_at DESC
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert datetime to string and Decimal to float for JSON serialization
        for r in results:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            for k, v in r.items():
                if isinstance(v, Decimal):
                    r[k] = float(v)
            r['file_url'] = f"/uploads/{r['audio_file_name']}"
            
        return JSONResponse({"status": "success", "data": results})
        
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

from pydantic import BaseModel
class MatchRequest(BaseModel):
    transcript: str

@app.post("/api/match")
async def match_candidates(req: MatchRequest):
    try:
        text = req.transcript.lower()
        
        # Determine intent category based on transcript
        intent = "other"
        if any(w in text for w in ['automation', 'rpa', 'n8n', 'scripting', 'bot']):
            intent = 'automation-heavy'
        elif any(w in text for w in ['web', 'frontend', 'backend', 'react', 'html', 'developer']):
            intent = 'web dev'
        elif any(w in text for w in ['data', 'sql', 'analytics', 'machine learning', 'ai']):
            intent = 'data'
        elif any(w in text for w in ['cloud', 'aws', 'azure', 'devops', 'server']):
            intent = 'cloud'
            
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query matching candidates
        cur.execute("""
            SELECT id, "Full Name" as name, "Phone" as phone, "City" as city, "Skills" as skills, skill_category
            FROM consolidated_profiles 
            WHERE skill_category = %s
            LIMIT 10
        """, (intent,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        return JSONResponse({"status": "success", "intent": intent, "data": results})
        
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
