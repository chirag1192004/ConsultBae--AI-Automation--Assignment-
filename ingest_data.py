import pandas as pd
import numpy as np
import re
import networkx as nx
from sqlalchemy import create_engine

issues_log = []

def log_issue(issue):
    issues_log.append(issue)

def clean_phone(phone):
    if pd.isna(phone):
        return None
    s = str(phone)
    # Remove all non-digits
    cleaned_s = re.sub(r'\D', '', s)
    # Strip leading country code for Indian numbers if it exists
    if len(cleaned_s) > 10 and cleaned_s.startswith('91'):
        cleaned_s = cleaned_s[2:]
    elif len(cleaned_s) > 10 and cleaned_s.startswith('0'):
        cleaned_s = cleaned_s[1:]
    
    if s != cleaned_s and cleaned_s:
        log_issue(f"Format resolution: Phone number '{s}' cleaned to '{cleaned_s}'")
    return cleaned_s if cleaned_s else None

def clean_email(email):
    if pd.isna(email):
        return None
    email_str = str(email).strip()
    email_lower = email_str.lower()
    if '@' not in email_lower:
        log_issue(f"Anomaly: Invalid email format found -> {email_str}")
        return None
    if email_str != email_lower:
        log_issue(f"Format resolution: Uppercase email '{email_str}' lowercased to '{email_lower}'")
    return email_lower

def standardize_city(city):
    if pd.isna(city) or not city: return None
    original = str(city).strip()
    c = original.lower()
    standard = original.title()
    
    if 'delhi' in c: standard = 'New Delhi'
    elif 'gurgaon' in c or 'gurugram' in c: standard = 'Gurugram'
    elif 'bangalore' in c or 'bengaluru' in c: standard = 'Bengaluru'
    elif 'noida' in c: standard = 'Noida'
    elif 'pune' in c: standard = 'Pune'
    
    if original != standard and original.lower() != standard.lower():
        log_issue(f"Entity matching: City '{original}' standardized to '{standard}'")
        
    return standard

def standardize_gig_rate(rate):
    if pd.isna(rate) or not rate: return None
    r = str(rate).lower().replace(' ', '')
    if 'k/month' in r:
        try: return f"{int(float(r.replace('k/month', '')) * 1000)}/month"
        except: pass
    elif '/month' in r:
        try: return f"{int(float(r.replace('/month', '')))}/month"
        except: pass
    elif '/hr' in r:
        try: return f"{int(float(r.replace('/hr', '')))}/hr"
        except: pass
    return str(rate)

def main():
    print("Loading CSV files...")
    df1 = pd.read_csv('database/source1_naukri_applicants.csv')
    df2 = pd.read_csv('database/source2_gig_workers.csv')
    df3 = pd.read_csv('database/source3_cbnexus_contacts.csv')

    print("Cleaning and standardizing data...")
    # Clean df1
    df1['Email_clean'] = df1['Email'].apply(clean_email)
    df1['Phone_clean'] = df1['Phone'].apply(clean_phone)
    df1['City_clean'] = df1['City'].apply(standardize_city)
    df1['Name_clean'] = df1['Full Name'].str.title().str.strip()
    df1['Applied Date_clean'] = pd.to_datetime(df1['Applied Date'], format='mixed', dayfirst=True, errors='coerce')
    
    def clean_ctc(ctc):
        if pd.isna(ctc): return None
        s = str(ctc).replace(',', '').strip()
        try:
            val = float(s)
            if val < 100: # assuming it's in LPA (e.g., 4.2 -> 420000)
                val = val * 100000
            return int(val)
        except:
            return None
            
    df1['CTC_clean'] = df1['Current CTC'].apply(clean_ctc)

    # Clean df2
    df2['Email_clean'] = df2['email_id'].apply(clean_email)
    df2['City_clean'] = df2['location'].apply(standardize_city)
    df2['Name_clean'] = df2['worker_name'].str.title().str.strip()
    df2['status_clean'] = df2['status'].str.title().str.strip()
    df2['rate_clean'] = df2['rate'].apply(standardize_gig_rate)

    # Clean df3
    df3['Phone_clean'] = df3['Phone Number'].apply(clean_phone)
    df3['City_clean'] = df3['City'].apply(standardize_city)
    df3['Name_clean'] = df3['Name'].str.title().str.strip()
    df3['Verified_clean'] = df3['Verified'].str.lower().map({'y': True, 'yes': True, 'n': False, 'no': False})

    print("Building Entity Resolution Graph...")
    G = nx.Graph()

    # Add nodes and edges from Naukri
    for idx, row in df1.iterrows():
        email = row['Email_clean']
        phone = row['Phone_clean']
        if pd.isna(email) and pd.isna(phone):
            log_issue(f"Naukri record missing both email and phone: {row['Full Name']}")
            continue
        
        nodes_to_link = []
        if pd.notna(email):
            nodes_to_link.append(f"email:{email}")
        if pd.notna(phone):
            nodes_to_link.append(f"phone:{phone}")
            
        for n in nodes_to_link:
            G.add_node(n, type='identifier')
        
        if len(nodes_to_link) == 2:
            G.add_edge(nodes_to_link[0], nodes_to_link[1])

    # Add nodes from Gig
    for idx, row in df2.iterrows():
        email = row['Email_clean']
        if pd.notna(email):
            G.add_node(f"email:{email}", type='identifier')
        else:
            log_issue(f"Gig record missing email: {row['worker_name']}")

    # Add nodes from CBNexus
    for idx, row in df3.iterrows():
        phone = row['Phone_clean']
        if pd.notna(phone):
            G.add_node(f"phone:{phone}", type='identifier')
        else:
            log_issue(f"CBNexus record missing phone: {row['Name']}")

    components = list(nx.connected_components(G))
    person_map = {}
    for person_id, comp in enumerate(components):
        for node in comp:
            person_map[node] = person_id

    def get_person_id(row, source):
        if source == 'df1':
            nodes = []
            if pd.notna(row['Email_clean']): nodes.append(f"email:{row['Email_clean']}")
            if pd.notna(row['Phone_clean']): nodes.append(f"phone:{row['Phone_clean']}")
            for n in nodes:
                if n in person_map: return person_map[n]
        elif source == 'df2':
            n = f"email:{row['Email_clean']}" if pd.notna(row['Email_clean']) else None
            if n in person_map: return person_map[n]
        elif source == 'df3':
            n = f"phone:{row['Phone_clean']}" if pd.notna(row['Phone_clean']) else None
            if n in person_map: return person_map[n]
        return None

    df1['person_id'] = df1.apply(lambda row: get_person_id(row, 'df1'), axis=1)
    df2['person_id'] = df2.apply(lambda row: get_person_id(row, 'df2'), axis=1)
    df3['person_id'] = df3.apply(lambda row: get_person_id(row, 'df3'), axis=1)

    print("Merging records & resolving conflicts...")
    consolidated_data = []

    for person_id in range(len(components)):
        p_df1 = df1[df1['person_id'] == person_id]
        p_df2 = df2[df2['person_id'] == person_id]
        p_df3 = df3[df3['person_id'] == person_id]
        
        if len(p_df1) > 1:
            log_issue(f"Duplicate person in Naukri data for person_id {person_id}. Rows: {len(p_df1)}. Resolution: taking first.")
        if len(p_df2) > 1:
            log_issue(f"Duplicate person in Gig data for person_id {person_id}. Rows: {len(p_df2)}. Resolution: taking first.")
        if len(p_df3) > 1:
            log_issue(f"Duplicate person in CBNexus data for person_id {person_id}. Rows: {len(p_df3)}. Resolution: taking first.")

        r1 = p_df1.iloc[0] if not p_df1.empty else None
        r2 = p_df2.iloc[0] if not p_df2.empty else None
        r3 = p_df3.iloc[0] if not p_df3.empty else None

        def resolve(field1, field2, field3):
            if field1 is not None and pd.notna(field1): return field1
            if field2 is not None and pd.notna(field2): return field2
            if field3 is not None and pd.notna(field3): return field3
            return None

        # Conflict check for names
        name1 = r1['Name_clean'] if r1 is not None else None
        name2 = r2['Name_clean'] if r2 is not None else None
        name3 = r3['Name_clean'] if r3 is not None else None
        
        names = [n for n in [name1, name2, name3] if n is not None and pd.notna(n)]
        if name1 is not None and pd.notna(name1):
            final_name = name1
        elif names:
            final_name = max(names, key=len)
        else:
            final_name = None
            
        if names and len(set(names)) > 1:
            log_issue(f"Name conflict for person_id {person_id}: {names}. Resolved to: {final_name}")

        # Emails and Phones
        email1 = r1['Email_clean'] if r1 is not None else None
        email2 = r2['Email_clean'] if r2 is not None else None
        phone1 = r1['Phone_clean'] if r1 is not None else None
        phone3 = r3['Phone_clean'] if r3 is not None else None

        final_email = email1 if email1 is not None and pd.notna(email1) else email2
        final_phone = phone1 if phone1 is not None and pd.notna(phone1) else phone3
        
        if email1 and email2 and email1 != email2:
            log_issue(f"Email conflict for person_id {person_id}: {email1} vs {email2}. Resolved to: {final_email}")
        if phone1 and phone3 and phone1 != phone3:
            log_issue(f"Phone conflict for person_id {person_id}: {phone1} vs {phone3}. Resolved to: {final_phone}")
            
        # Cities
        city1 = r1['City_clean'] if r1 is not None else None
        city2 = r2['City_clean'] if r2 is not None else None
        city3 = r3['City_clean'] if r3 is not None else None
        final_city = resolve(city1, city2, city3)
        valid_cities = [c for c in [city1, city2, city3] if c and pd.notna(c)]
        if valid_cities and len(set(valid_cities)) > 1:
             log_issue(f"City conflict for person_id {person_id}: {valid_cities}. Resolved to: {final_city}")

        # Merge skills
        skills1 = str(r1['Skills']) if r1 is not None and pd.notna(r1['Skills']) else ""
        skills2 = str(r2['skill_tags']) if r2 is not None and pd.notna(r2['skill_tags']) else ""
        
        merged_skills = []
        for s in [skills1, skills2]:
            if s and s.lower() != 'nan':
                tags = [x.strip().title() for x in s.split(',')]
                merged_skills.extend(tags)
        final_skills = ", ".join(sorted(list(set(merged_skills)))) if merged_skills else None

        sources = []
        if r1 is not None: sources.append("Naukri")
        if r2 is not None: sources.append("Gig")
        if r3 is not None: sources.append("CBNexus")
        if len(sources) > 1:
            log_issue(f"Entity Merge: Linked {final_name} across sources: {', '.join(sources)} (Email: {final_email}, Phone: {final_phone})")
            
        profile = {
            'Full Name': final_name,
            'Email': final_email,
            'Phone': final_phone,
            'City': final_city,
            'Experience (Years)': r1['Experience (Years)'] if r1 is not None else None,
            'Current CTC': r1['CTC_clean'] if r1 is not None else None,
            'Applied Date': r1['Applied Date_clean'].strftime('%d/%m/%Y') if r1 is not None and pd.notna(r1['Applied Date_clean']) else None,
            'Skills': final_skills,
            'Gig Rate': r2['rate_clean'] if r2 is not None else None,
            'Gig Status': r2['status_clean'] if r2 is not None else None,
            'CBNexus Verified': r3['Verified_clean'] if r3 is not None else None,
            'Projects Completed': r3['Projects Completed'] if r3 is not None else None
        }
        consolidated_data.append(profile)

    consolidated_df = pd.DataFrame(consolidated_data)

    print("\n================== DATA ISSUES & MERGE LOG ==================")
    for issue in issues_log:
        print(f"- {issue}")
    print("=============================================================\n")

    print(f"Total Unique Persons Extracted: {len(consolidated_df)}")

    print("\nAttempting Database Ingestion...")
    DATABASE_URL = "postgresql://admin:password123@localhost:5433/cbnexus_db"
    try:
        engine = create_engine(DATABASE_URL)
        

        consolidated_df.to_sql('consolidated_profiles', engine, if_exists='replace', index=False)
        print("Successfully ingested data into PostgreSQL (cbnexus_db -> consolidated_profiles).")
    except Exception as e:
        print(f"Warning: Database connection failed. Is PostgreSQL running?\nDetails: {e}")
        
    # Output as a local csv file for backup
    consolidated_df.to_csv('consolidated_profiles.csv', index=False)
    print("Saved a local copy to 'consolidated_profiles.csv'")

if __name__ == "__main__":
    main()
