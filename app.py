import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import math

# Page Configuration
st.set_page_config(page_title="AI Smart Study Planner", page_icon="🧠", layout="wide")

# Custom CSS for Modern Dark/Clean Cards
st.markdown("""
<style>
    .metric-card {
        background-color: #1E293B;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #38BDF8;
        color: white;
        margin-bottom: 10px;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State (Data store karne ke liye)
if "subjects" not in st.session_state:
    st.session_state.subjects = [
        {"Subject": "Data Structures", "Difficulty": 5, "Exam Date": datetime.today().date() + timedelta(days=10), "Topics": 8, "Completed": 2},
        {"Subject": "Operating Systems", "Difficulty": 4, "Exam Date": datetime.today().date() + timedelta(days=14), "Topics": 6, "Completed": 1},
        {"Subject": "DBMS", "Difficulty": 3, "Exam Date": datetime.today().date() + timedelta(days=18), "Topics": 5, "Completed": 3},
    ]

# --- AI SCHEDULING ENGINE ---
def generate_ai_schedule(subjects, daily_hours, start_date):
    schedule = []
    today = start_date
    
    # Active subjects jinme topics baaki hain
    active_subs = []
    for sub in subjects:
        rem_topics = sub["Topics"] - sub["Completed"]
        days_left = max((sub["Exam Date"] - today).days, 1)
        if rem_topics > 0:
            # AI Priority Formula: (Difficulty * Remaining Topics) / Urgency
            urgency_factor = 15 / days_left
            priority_score = (sub["Difficulty"] * 1.5) + (rem_topics * 1.2) + urgency_factor
            active_subs.append({
                "Subject": sub["Subject"],
                "Difficulty": sub["Difficulty"],
                "Rem_Topics": rem_topics,
                "Days_Left": days_left,
                "Score": priority_score,
                "Exam_Date": sub["Exam Date"]
            })
            
    if not active_subs:
        return pd.DataFrame()

    # Sort by AI Priority Score (Highest first)
    active_subs = sorted(active_subs, key=lambda x: x["Score"], reverse=True)
    total_score = sum(s["Score"] for s in active_subs)
    
    # Generate 7-Day Smart Plan
    for day_offset in range(7):
        current_day = today + timedelta(days=day_offset)
        day_name = current_day.strftime("%A, %d %b")
        
        # Sunday ko halka rakhne ke liye (Burnout Protection)
        effective_hours = daily_hours * 0.75 if current_day.weekday() == 6 else daily_hours
        
        for sub in active_subs:
            if current_day <= sub["Exam_Date"]:
                # Proportional time allocation
                allocated_hrs = round((sub["Score"] / total_score) * effective_hours, 1)
                if allocated_hrs >= 0.5:
                    # Pomodoro technique calculation (50 min study + 10 min break)
                    sessions = max(1, math.floor(allocated_hrs))
                    mode = "🔥 Deep Focus (Hard)" if sub["Difficulty"] >= 4 else "⚡ Active Recall (Medium)"
                    
                    schedule.append({
                        "Date": day_name,
                        "Subject": sub["Subject"],
                        "Study Duration": f"{allocated_hrs} hrs ({sessions} Pomodoro)",
                        "AI Strategy": mode,
                        "Revision Alert": "Spaced Revision Due!" if day_offset in [2, 5] else "New Topic + Notes"
                    })
                    
    return pd.DataFrame(schedule)

# --- SIDEBAR: ADD SUBJECTS & SETTINGS ---
with st.sidebar:
    st.title("⚙️ Planner Settings")
    daily_hours = st.slider("Roz kitne ghante padh sakte hain?", 2.0, 12.0, 5.0, 0.5)
    st.divider()
    
    st.subheader("➕ Naya Subject Add Karein")
    with st.form("add_subject_form", clear_on_submit=True):
        sub_name = st.text_input("Subject ka Naam (e.g., Python, Maths)")
        difficulty = st.slider("Difficulty Level (1=Easy, 5=Hard)", 1, 5, 3)
        exam_date = st.date_input("Exam Date", min_value=datetime.today().date() + timedelta(days=1))
        total_topics = st.number_input("Total Chapters / Topics", min_value=1, max_value=50, value=5)
        completed_topics = st.number_input("Kitne Complete ho gaye?", min_value=0, max_value=50, value=0)
        
        submitted = st.form_submit_button("Add to AI Planner")
        if submitted:
            if sub_name.strip() == "":
                st.error("Subject ka naam likhna zaroori hai!")
            elif completed_topics > total_topics:
                st.error("Completed topics total topics se zyada nahi ho sakte!")
            else:
                st.session_state.subjects.append({
                    "Subject": sub_name.strip(),
                    "Difficulty": difficulty,
                    "Exam Date": exam_date,
                    "Topics": total_topics,
                    "Completed": completed_topics
                })
                st.success(f"{sub_name} add ho gaya!")

    if st.button("🗑️ Reset All Data"):
        st.session_state.subjects = []
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("🧠 AI-Based Smart Study Planner")
st.caption("Dynamic Priority Scheduling • Burnout Protection • Spaced Repetition Engine")

# Top KPI Metrics
if st.session_state.subjects:
    total_t = sum(s["Topics"] for s in st.session_state.subjects)
    comp_t = sum(s["Completed"] for s in st.session_state.subjects)
    readiness = round((comp_t / total_t) * 100, 1) if total_t > 0 else 0
    nearest_exam = min((s["Exam Date"] - datetime.today().date()).days for s in st.session_state.subjects)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Exam Readiness Score", f"{readiness}%", f"{comp_t}/{total_t} Topics Done")
    col2.metric("⏳ Next Exam In", f"{max(0, nearest_exam)} Days", "Stay Consistent")
    col3.metric("⏱️ Daily Target", f"{daily_hours} Hours", "Includes 10m Pomodoro Breaks")

st.divider()

# Two-Column Layout: Syllabus Tracker & AI Timetable
left_col, right_col = st.columns([1, 1.6])

with left_col:
    st.subheader("📚 Syllabus & Progress Tracker")
    if not st.session_state.subjects:
        st.info("Sidebar se apna pehla subject add karein!")
    else:
        for idx, sub in enumerate(st.session_state.subjects):
            prog = sub["Completed"] / sub["Topics"]
            with st.container():
                st.markdown(f"**{sub['Subject']}** (Difficulty: {'⭐'*sub['Difficulty']})")
                st.progress(prog)
                c1, c2 = st.columns([2, 1])
                c1.caption(f"Exam: {sub['Exam Date']} | Done: {sub['Completed']}/{sub['Topics']}")
                if sub["Completed"] < sub["Topics"]:
                    if c2.button("✅ +1 Topic", key=f"btn_{idx}"):
                        st.session_state.subjects[idx]["Completed"] += 1
                        st.rerun()

with right_col:
    st.subheader("📅 AI Generated 7-Day Smart Timetable")
    if st.session_state.subjects:
        df_schedule = generate_ai_schedule(st.session_state.subjects, daily_hours, datetime.today().date())
        if not df_schedule.empty:
            st.dataframe(df_schedule, use_container_width=True, hide_index=True)
            
            # Download Button
            csv = df_schedule.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Timetable (CSV)",
                data=csv,
                file_name="AI_Smart_Study_Plan.csv",
                mime="text/csv"
            )
        else:
            st.success("🎉 Badhai ho! Aapke saare topics complete ho chuke hain!")
