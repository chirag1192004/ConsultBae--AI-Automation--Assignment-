import psycopg2

def setup_audio_table():
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(
        dbname="cbnexus_db",
        user="admin",
        password="password123",
        host="localhost",
        port="5433"
    )
    cur = conn.cursor()

    try:
        # First, add a primary key ID to consolidated_profiles if it doesn't exist
        print("Ensuring consolidated_profiles has a primary key 'id'...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='consolidated_profiles' AND column_name='id') THEN
                    ALTER TABLE consolidated_profiles ADD COLUMN id SERIAL PRIMARY KEY;
                END IF;
            END $$;
        """)
        
        # Then create the audio_submissions table
        print("Creating audio_submissions table...")
        cur.execute("""
            DROP TABLE IF EXISTS audio_submissions;
            CREATE TABLE audio_submissions (
                id SERIAL PRIMARY KEY,
                worker_id INTEGER REFERENCES consolidated_profiles(id),
                phone VARCHAR(20) NOT NULL,
                worker_name VARCHAR(100),
                audio_file_name VARCHAR(255),
                duration_sec NUMERIC(6, 2),
                sample_rate_khz NUMERIC(6, 2),
                bitrate_kbps INTEGER,
                loudness_db NUMERIC(6, 2),
                qa_status VARCHAR(50) DEFAULT 'Pending',
                quality_tier VARCHAR(50),
                ai_evaluation_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        print("Table 'audio_submissions' successfully created and linked!")

    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    setup_audio_table()
