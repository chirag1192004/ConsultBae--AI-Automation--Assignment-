import os
import re
import shutil
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from audio_utils import get_audio_metadata

app = FastAPI()

# Setup directories
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

# Mount static files for UI and audio streaming
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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
    audio: UploadFile = File(...)
):
    try:
        # Save file locally
        file_ext = audio.filename.split(".")[-1] if "." in audio.filename else "webm"
        safe_filename = f"{phone}_{audio.filename}".replace(" ", "_")
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
            
        # Extract metadata
        metrics = get_audio_metadata(file_path)
        
        # Connect to DB and handle entity linking
        conn = get_db_connection()
        cur = conn.cursor()
        
        cleaned_phone = clean_phone(phone)
        
        # Check if worker exists
        cur.execute('SELECT id FROM consolidated_profiles WHERE "Phone" = %s', (cleaned_phone,))
        result = cur.fetchone()
        
        if result:
            worker_id = result[0]
        else:
            # Create new profile to prevent orphans
            cur.execute(
                'INSERT INTO consolidated_profiles ("Full Name", "Phone", "City") VALUES (%s, %s, %s) RETURNING id',
                (name.title(), cleaned_phone, "Unknown (From Audio App)")
            )
            worker_id = cur.fetchone()[0]
            
        # Insert audio submission
        cur.execute(
            """
            INSERT INTO audio_submissions 
            (worker_id, phone, worker_name, audio_file_name, duration_sec, sample_rate_khz, bitrate_kbps, loudness_db, qa_status, quality_tier) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                worker_id, cleaned_phone, name, safe_filename, 
                metrics["duration_sec"], metrics["sample_rate_khz"], metrics["bitrate_kbps"], 
                metrics["loudness_db"], "Pending", metrics["quality_tier"]
            )
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
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
            JOIN consolidated_profiles c ON a.worker_id = c.id
            ORDER BY a.created_at DESC
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert datetime to string for JSON serialization
        for r in results:
            r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            r['file_url'] = f"/uploads/{r['audio_file_name']}"
            
        return JSONResponse({"status": "success", "data": results})
        
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
