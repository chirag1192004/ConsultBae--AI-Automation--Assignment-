import psycopg2
from psycopg2.extras import RealDictCursor
import re

def get_db_connection():
    return psycopg2.connect(
        dbname="cbnexus_db",
        user="admin",
        password="password123",
        host="localhost",
        port="5433"
    )

def categorize_skills(skills_str):
    if not skills_str: return "other"
    
    text = str(skills_str).lower()
    
    categories = {
        'automation-heavy': ['automation', 'rpa', 'n8n', 'zapier', 'selenium', 'puppeteer', 'beautifulsoup', 'scripting', 'crawler', 'scraping'],
        'web dev': ['web', 'html', 'css', 'javascript', 'react', 'angular', 'vue', 'node', 'django', 'frontend', 'backend', 'php', 'laravel', 'fullstack', 'api', 'ui/ux'],
        'data': ['data', 'sql', 'pandas', 'numpy', 'spark', 'hadoop', 'machine learning', 'science', 'tableau', 'powerbi', 'excel', 'analytics', 'reporting', 'ai'],
        'cloud': ['cloud', 'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ci/cd', 'devops', 'linux', 'serverless']
    }
    
    scores = {'automation-heavy': 0, 'web dev': 0, 'data': 0, 'cloud': 0}
    
    for category, keywords in categories.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                scores[category] += 1
                
    # Also check if they mention python, java, etc which could lean towards automation or web
    if 'python' in text: scores['automation-heavy'] += 0.5; scores['data'] += 0.5
    
    best_match = max(scores, key=scores.get)
    if scores[best_match] > 0:
        return best_match
    return "other"

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("Checking if skill_category column exists...")
    cur.execute("""
        ALTER TABLE consolidated_profiles 
        ADD COLUMN IF NOT EXISTS skill_category VARCHAR(50);
    """)
    conn.commit()
    
    print("Fetching profiles...")
    cur.execute('SELECT id, "Skills" FROM consolidated_profiles')
    profiles = cur.fetchall()
    
    print(f"Categorizing {len(profiles)} profiles...")
    updates = []
    for profile in profiles:
        cat = categorize_skills(profile['Skills'])
        updates.append((cat, profile['id']))
        
    print("Updating database...")
    for cat, pid in updates:
        cur.execute("UPDATE consolidated_profiles SET skill_category = %s WHERE id = %s", (cat, pid))
        
    conn.commit()
    cur.close()
    conn.close()
    print("Successfully categorized all profiles!")

if __name__ == "__main__":
    main()
