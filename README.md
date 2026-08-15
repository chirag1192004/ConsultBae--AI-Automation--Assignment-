# ConsultBae AI Automation Assignment

## Progress Report
- [x] **Task 1 (Merge)**: Completed.
  - Successfully merged 3 messy CSV files (Naukri, Gig, CBNexus) into a single PostgreSQL database schema without duplicates.
- [ ] **Task 2 (Automation)**: Pending.
- [ ] **Task 3 (Audio App)**: Pending.
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
