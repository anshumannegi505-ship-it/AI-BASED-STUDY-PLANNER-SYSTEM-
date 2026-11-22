import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import time
import math
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Smart Study OS", page_icon="🧠", layout="wide")

DATA_FILE = "study_planner_db.json"

# --- CUSTOM STYLING ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1E293B;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
        color: white;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284C7 !important;
        color: white !important;
        font-weight: bold;
    }
    .risk-high { color: #F87171; font-weight: bold; }
    .risk-med { color: #FBBF24; font-weight: bold; }
    .risk-low { color: #34D399; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS (Persistent Storage) ---
def get_default_data():
    return {
        "xp": 150,
        "streak": 3,
        "last_study_date": str(datetime.today().date()),
        "subjects": [
            {
                "Subject": "Data Structures & Algo",
                "Difficulty": 5,
                "Exam Date": str(datetime.today().date() + timedelta(days=10)),
                "Topics": 10,
                "Completed": 3,
                "Last_Revised": str(datetime.today().date() - timedelta(days=3)),
                "Notes": "Time Complexity: Big-O, Master Theorem, Tree Traversals (Inorder, Preorder, Postorder)."
            },
            {
                "Subject": "Operating Systems",
                "Difficulty": 4,
                "Exam Date": str(datetime.today().date() + timedelta(days=15)),
                "Topics": 8,
                "Completed": 2,
                "Last_Revised": str(datetime.today().date() - timedelta(days=1)),
                "Notes": "Deadlock conditions: Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait."
            },
            {
                "Subject": "DBMS",
                "Difficulty": 3,
                "Exam Date": str(datetime.today().date() + timedelta(days=20)),
                "Topics": 6,
                "Completed": 4,
                "Last_Revised": str(datetime.today().date() - timedelta(days=7)),
                "Notes": "Normalization: 1NF (Atomic), 2NF (No Partial Dependency), 3NF (No Transitive Dependency)."
            }
        ],
        "daily_tasks": [
            {"task": "Solve 15 DSA Array problems", "done": False},
            {"task": "Revise OS Scheduling Algorithms", "done": True}
        ]
    }

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return get_default_data()
    return get_default_data()

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "db" not in st.session_state:
    st.session_state.db = load_data()

db = st.session_state.db

# --- AI ENGINE FUNCTIONS ---
def calculate_risk(sub, today):
    rem = sub["Topics"] - sub["Completed"]
    if rem <= 0:
        return "🟢 Completed", "risk-low", 0
    exam_dt = datetime.strptime(sub["Exam Date"], "%Y-%m-%d").date()
    days_left = max((exam_dt - today).days, 1)
    pace_needed = rem / days_left
    
    if pace_needed > 1.2 or (days_left <= 5 and rem > 3):
        return "🔴 High Risk", "risk-high", pace_needed
    elif pace_needed > 0.6:
        return "🟡 Moderate", "risk-med", pace_needed
    else:
        return "🟢 Safe Zone", "risk-low", pace_needed

def generate_ai_schedule(subjects, daily_hours, start_date, burnout_protection):
    schedule = []
    active_subs = []
    
    for sub in subjects:
        rem_topics = sub["Topics"] - sub["Completed"]
        exam_dt = datetime.strptime(sub["Exam Date"], "%Y-%m-%d").date()
        days_left = max((exam_dt - start_date).days, 1)
        
        if rem_topics > 0 and exam_dt >= start_date:
            urgency = 18 / days_left
            score = (sub["Difficulty"] * 1.6) + (rem_topics * 1.3) + urgency
            active_subs.append({
                "Subject": sub["Subject"],
                "Difficulty": sub["Difficulty"],
                "Rem_Topics": rem_topics,
                "Days_Left": days_left,
                "Score": score,
                "Exam_Date": exam_dt
            })
            
    if not active_subs:
        return pd.DataFrame()

    active_subs = sorted(active_subs, key=lambda x: x["Score"], reverse=True)
    total_score = sum(s["Score"] for s in active_subs)
    
    for day_offset in range(7):
        curr_day = start_date + timedelta(days=day_offset)
        day_label = curr_day.strftime("%a, %d %b")
        is_sunday
