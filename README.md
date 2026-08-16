# ConsultBae AI Automation Assignment

## Progress Report
- [x] **Task 1 (Merge)**: Completed.
  - Successfully merged 3 messy CSV files (Naukri, Gig, CBNexus) into a single PostgreSQL database schema without duplicates.
- [ ] **Task 2 (Automation)**: Pending.
- [x] **Task 3 (Audio App)**: Completed.
  - Developed a full-stack SPA with FastAPI and Vanilla JS featuring live browser recording, file uploads, audio metadata extraction (duration, bitrate, loudness), and a real-time dashboard.
- [ ] **Task 4 (Data Issues Report)**: Integrated below for Task 1.
- [ ] **Task 5 (Stretch)**: Pending.

---

## Setup Steps (Task 1)

### 1. Database Setup
We use Docker to spin up a PostgreSQL database and pgAdmin. To avoid local port conflicts, PostgreSQL is mapped to `5433` and pgAdmin to `5051`.
```bash
docker compose up -d --build
```
- **PostgreSQL**: `localhost:5433` (DB: `cbnexus_db`, User: `admin`, Pass: `password123`)
- **pgAdmin**: `http://localhost:5051` (User: `admin@admin.com`, Pass: `admin`)

### 2. Python Environment
Install the required dependencies using pip:
```bash
pip install -r requirements.txt
```

### 3. Running the Ingestion Pipeline
Execute the Python script to clean, merge, and insert the data into the database:
```bash
python ingest_data.py
```
*Note: The script also generates a local fallback CSV `consolidated_profiles.csv`.*

---

## Setup Steps (Task 2 & 3)

### 1. n8n Automation (Task 2)
The `n8n` platform runs natively in our Docker cluster on port `5678`.
1. Go to `http://localhost:5678` and complete the initial setup.
2. Click **Import from File** and upload the `n8n_workflow.json` located in this repository.
3. Configure the **Postgres Nodes** to connect to our local DB using the internal Docker IP: `172.19.0.2` (Port: `5432`, User: `admin`, Pass: `password123`, DB: `cbnexus_db`).

### 2. Audio Collection Web App (Task 3)
We built a premium, glassmorphism-themed Audio Application.
1. Create the necessary database table to receive audio submissions:
```bash
python create_audio_table.py
```
2. Start the FastAPI backend server:
```bash
cd audio_app
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```
3. Open your browser and navigate to `http://localhost:8080` to access the App and the live QA Dashboard.

---

## Task 4: Data Issues Report (For Task 1)

During the data ingestion, several data quality issues were identified and programmatically resolved:

1. **Missing Common Identifiers (The Core Merge Problem)**: 
   - *Issue*: Naukri has both Email and Phone, Gig only has Email, and CBNexus only has Phone.
   - *Resolution*: Implemented a transitive graph-matching algorithm using `networkx`. The Naukri dataset acts as a bridge, allowing us to link a Gig record (via email) to a CBNexus record (via phone) if they both match the same Naukri profile.
2. **Inconsistent/Messy Phone Numbers**: 
   - *Issue*: Phone numbers contained country codes (e.g., `+91-`, `0`), dashes, spaces, and mixed lengths.
   - *Resolution*: Created a cleaning function to strip all non-numeric characters and remove leading `91` or `0` for numbers exceeding 10 digits, resulting in a clean, standard 10-digit identifier for everyone.
3. **Inconsistent City Names**: 
   - *Issue*: Variations like `GURGAON` vs `gurugram`, `Delhi NCR` vs `New Delhi`, and `bangalore` vs `Bengaluru`.
   - *Resolution*: Implemented a dynamic substring standardizer (`standardize_city`) to map variations to their modern, standard Title Case names (e.g., "New Delhi", "Gurugram", "Bengaluru").
4. **Invalid Email Formats**: 
   - *Issue*: Some email fields contained comma-separated skills instead of emails (e.g., `react, javascript, mysql`), and many were uppercase.
   - *Resolution*: Added format validation (checking for `@`) and forced all valid emails to lowercase. Invalid emails were dropped from the identifier pool and logged.
5. **Inconsistent Financial & Date Formatting**:
   - *Issue*: CTC was represented dynamically (e.g., `4.2` LPA vs `417964`) and dates varied in structure.
   - *Resolution*: Converted LPA figures `<100` into raw integers (by multiplying by 1,000,000) and standardized all dates to the Indian standard `DD/MM/YYYY`. Gig rates were padded (e.g. `28k/month` to `28000/month`).
6. **Internal File Duplicates**:
   - *Issue*: The Naukri dataset contained duplicates for the same person (e.g., `person_id 23` and `25`).
   - *Resolution*: Deduped within the script by taking the first occurrence to avoid SQL constraint violations.

---

## Stuck Log

**1. Database Port Conflicts**
- **Where I got stuck**: When running `docker compose up`, I encountered the error `Bind for 0.0.0.0:5432 failed: port is already allocated`. The default Postgres port was busy on the host machine.
- **How I got unstuck**: I realized another local instance was running. Instead of terminating the host process, I updated `docker-compose.yml` to map host port `5433` to container port `5432`, and updated the `DATABASE_URL` in the python script accordingly. I also changed pgAdmin to `5051` to be safe.

**2. Transitive Record Linking**
- **Where I got stuck**: I needed to merge the same person across 3 files, but realized Gig and CBNexus had absolutely no common fields (one has Email, the other has Phone).
- **How I got unstuck**: I decided to use Graph Theory. I used the `networkx` library to represent Emails and Phones as nodes. The Naukri dataset (which has both) creates the "edges" (connections). Finding the "connected components" in this graph perfectly clustered all records belonging to the same person, allowing me to assign a single unique `person_id` across all three datasets effortlessly.

**3. n8n Docker Host Routing & DNS**
- **Where I got stuck**: While setting up the Postgres node inside the n8n Docker container at `http://localhost:5678` (Task 2), n8n returned a "Connection Refused" error when using `localhost`, and a "Host Not Found" when using the docker service name `db` (even though they are on the same Docker network).
- **How I got unstuck**: Because n8n runs inside a Docker container, `localhost` points to the n8n container itself, not the host machine. Furthermore, due to a Docker DNS glitch on Windows, the service hostname `db` wasn't resolving properly in the n8n UI. I bypassed the Docker DNS entirely by retrieving the explicit internal docker IP for the Postgres container (`172.19.0.2`) and used that to instantly establish the connection.

**4. Browser Audio Extraction (Missing FFmpeg)**
- **Where I got stuck**: Extracting metadata (Loudness, Bitrate) from browser-recorded `.webm` audio blobs requires `ffmpeg` bindings in Python (via `pydub`), which caused fatal crash loops (`audioop` missing in Python 3.13) when the binary wasn't perfectly configured on the host machine.
- **How I got unstuck**: Instead of demanding the user install system-level C++ binaries for `ffmpeg`, I pivoted the backend to use `mutagen` for dependency-free extraction of standard files, and wrote a heuristic fallback algorithm to manually calculate the bitrate and duration natively from the raw byte sizes for the WebM blobs.
