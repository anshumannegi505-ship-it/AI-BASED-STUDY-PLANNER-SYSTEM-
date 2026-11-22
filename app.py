import streamlit as st
import pandas as pd
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
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS (Persistent + Cloud Safe) ---
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
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

if "db" not in st.session_state:
    st.session_state.db = load_data()

db = st.session_state.db

# --- AI ENGINE FUNCTIONS ---
def calculate_risk(sub, today):
    rem = sub["Topics"] - sub["Completed"]
    if rem <= 0:
        return "🟢 Completed", 0.0
    exam_dt = datetime.strptime(sub["Exam Date"], "%Y-%m-%d").date()
    days_left = max((exam_dt - today).days, 1)
    pace_needed = rem / days_left
    
    if pace_needed > 1.2 or (days_left <= 5 and rem > 3):
        return "🔴 High Risk", pace_needed
    elif pace_needed > 0.6:
        return "🟡 Moderate", pace_needed
    else:
        return "🟢 Safe Zone", pace_needed

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
        is_sunday = (curr_day.weekday() == 6)
        
        eff_hours = daily_hours * 0.75 if (is_sunday and burnout_protection) else daily_hours
        
        for sub in active_subs:
            if curr_day <= sub["Exam_Date"]:
                alloc_hrs = round((sub["Score"] / total_score) * eff_hours, 1)
                if alloc_hrs >= 0.5:
                    pomo_count = max(1, math.floor(alloc_hrs))
                    if is_sunday and burnout_protection:
                        task_type = "🧘 Light Revision & Mock Test"
                    elif sub["Difficulty"] >= 4:
                        task_type = "🔥 Deep Focus (Hard Concepts)"
                    else:
                        task_type = "⚡ Active Recall & PYQs"
                        
                    schedule.append({
                        "Date": day_label,
                        "Subject": sub["Subject"],
                        "Hours": alloc_hrs,
                        "Pomodoros": f"{pomo_count} x 50m",
                        "AI Strategy": task_type,
                        "Priority": "High" if sub["Score"] == active_subs[0]["Score"] else "Normal"
                    })
    return pd.DataFrame(schedule)

# --- SIDEBAR: CONTROLS & GAMIFICATION ---
with st.sidebar:
    st.title("🧠 AI Study OS")
    
    level = (db["xp"] // 200) + 1
    st.markdown(f"### 🏆 Level {level} Scholar | 🔥 {db['streak']} Day Streak")
    st.progress((db["xp"] % 200) / 200)
    st.caption(f"XP: {db['xp']} / {level * 200} (Complete topics or Pomodoro to earn XP)")
    
    st.divider()
    st.subheader("⚙️ AI Engine Settings")
    daily_hours = st.slider("Daily Study Capacity (Hours)", 2.0, 14.0, 6.0, 0.5)
    burnout_mode = st.toggle("🛡️ Sunday Burnout Protection", value=True, help="Reduces Sunday study load by 25% for mental recovery")
    
    st.divider()
    st.subheader("🎯 Quick Daily To-Do")
    new_task = st.text_input("Add today's micro-goal", placeholder="e.g., Revise Chapter 4")
    if st.button("➕ Add Goal") and new_task.strip():
        db["daily_tasks"].append({"task": new_task.strip(), "done": False})
        save_data(db)
        st.rerun()
        
    for i, t in enumerate(db["daily_tasks"]):
        col_chk, col_del = st.columns([4, 1])
        checked = col_chk.checkbox(t["task"], value=t["done"], key=f"task_{i}")
        if checked != t["done"]:
            db["daily_tasks"][i]["done"] = checked
            if checked:
                db["xp"] += 15
            save_data(db)
            st.rerun()
        if col_del.button("✖", key=f"del_t_{i}"):
            db["daily_tasks"].pop(i)
            save_data(db)
            st.rerun()

# --- TOP KPI HEADER ---
today = datetime.today().date()
total_topics = sum(s["Topics"] for s in db["subjects"])
comp_topics = sum(s["Completed"] for s in db["subjects"])
readiness = round((comp_topics / total_topics) * 100, 1) if total_topics > 0 else 0

upcoming_exams = [
    (datetime.strptime(s["Exam Date"], "%Y-%m-%d").date() - today).days
    for s in db["subjects"]
    if datetime.strptime(s["Exam Date"], "%Y-%m-%d").date() >= today
]
next_exam_days = min(upcoming_exams) if upcoming_exams else 0

st.title("🚀 AI-Based Smart Study Planner")
k1, k2, k3, k4 = st.columns(4)
k1.metric("📊 Syllabus Readiness", f"{readiness}%", f"{comp_topics}/{total_topics} Chapters")
k2.metric("⏳ Nearest Exam", f"{next_exam_days} Days", "Auto-Prioritized")
k3.metric("⚡ Daily Study Target", f"{daily_hours} Hrs", "Burnout Shield ON" if burnout_mode else "Full Grind")
k4.metric("⭐ Total XP Earned", f"{db['xp']} XP", f"Level {level}")

st.markdown("---")

# --- 5 MAIN FEATURE TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📅 AI Smart Timetable",
    "📈 Visual Analytics & Risk",
    "⏱️ Pomodoro Focus Zone",
    "🔁 Spaced Revision & Notes",
    "📚 Manage Subjects"
])

# ================= TAB 1: AI TIMETABLE =================
with tab1:
    st.subheader("🤖 Dynamic 7-Day AI Generated Schedule")
    if not db["subjects"]:
        st.warning("Koi subject nahi mila. 'Manage Subjects' tab mein jaakar subjects add karein.")
    else:
        df_plan = generate_ai_schedule(db["subjects"], daily_hours, today, burnout_mode)
        if not df_plan.empty:
            day_filter = st.selectbox("Filter by Day:", ["All 7 Days"] + list(df_plan["Date"].unique()))
            filtered_df = df_plan if day_filter == "All 7 Days" else df_plan[df_plan["Date"] == day_filter]
            
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            
            c_dl1, c_dl2 = st.columns(2)
            csv_data = df_plan.to_csv(index=False).encode("utf-8")
            c_dl1.download_button("📥 Download Schedule (CSV / Excel)", csv_data, "AI_Study_Timetable.csv", "text/csv")
            
            json_backup = json.dumps(db, indent=4).encode("utf-8")
            c_dl2.download_button("💾 Backup All Planner Data (JSON)", json_backup, "study_backup.json", "application/json")
        else:
            st.success("🎉 Saare subjects complete ho chuke hain! Revision tab check karein.")

# ================= TAB 2: ANALYTICS & RISK =================
with tab2:
    st.subheader("📊 AI Risk Predictor & Progress Visuals")
    if db["subjects"]:
        col_chart1, col_chart2 = st.columns(2)
        
        df_subs = pd.DataFrame(db["subjects"])
        df_subs["Remaining"] = df_subs["Topics"] - df_subs["Completed"]
        chart_df1 = df_subs.set_index("Subject")[["Completed", "Remaining"]]
        
        with col_chart1:
            st.markdown("**📚 Syllabus Completion vs Remaining**")
            st.bar_chart(chart_df1, color=["#10B981", "#EF4444"])
            
        with col_chart2:
            st.markdown("**⏱️ Weekly Study Hours Allocated per Subject**")
            df_plan_chart = generate_ai_schedule(db["subjects"], daily_hours, today, burnout_mode)
            if not df_plan_chart.empty:
                hours_by_sub = df_plan_chart.groupby("Subject")["Hours"].sum()
                st.bar_chart(hours_by_sub, color="#38BDF8")

        st.subheader("🚨 Subject-Wise Exam Risk Analysis")
        risk_rows = []
        for s in db["subjects"]:
            status, pace = calculate_risk(s, today)
            exam_dt = datetime.strptime(s["Exam Date"], "%Y-%m-%d").date()
            d_left = max((exam_dt - today).days, 0)
            risk_rows.append({
                "Subject": s["Subject"],
                "Exam Date": s["Exam Date"],
                "Days Left": d_left,
                "Topics Left": s["Topics"] - s["Completed"],
                "Required Speed": f"{round(pace, 2)} topics/day",
                "AI Risk Status": status
            })
        st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)

# ================= TAB 3: POMODORO FOCUS ZONE =================
with tab3:
    st.subheader("⏱️ Deep Work Pomodoro Timer")
    st.info("Ek session complete karne par aapko +50 XP milenge!")
    
    p_col1, p_col2 = st.columns([1, 2])
    with p_col1:
        sub_names = [s["Subject"] for s in db["subjects"]] if db["subjects"] else ["General Study"]
        focus_sub = st.selectbox("Kis subject par focus karna hai?", sub_names)
        mins = st.selectbox("Timer Duration (Minutes):", [25, 50, 15, 5, 1])
        
        start_timer = st.button("▶️ Start Focus Session", type="primary")
        if st.button("🏅 Log Completed Session (+50 XP)"):
            db["xp"] += 50
            save_data(db)
            st.success(f"Shabaash! {focus_sub} ke liye +50 XP add ho gaye!")
            st.rerun()

    with p_col2:
        timer_placeholder = st.empty()
        if start_timer:
            total_sec = mins * 60
            for sec in range(total_sec, -1, -1):
                m, s = divmod(sec, 60)
                timer_placeholder.markdown(f"# ⏳ `{m:02d}:{s:02d}` \n**Focusing on:** {focus_sub}")
                time.sleep(1)
            db["xp"] += 50
            save_data(db)
            st.balloons()
            st.success("🎉 Session Complete! +50 XP Earned!")
        else:
            timer_placeholder.markdown(f"# ⏳ `{mins:02d}:00` \nReady to start **{focus_sub}**")

# ================= TAB 4: SPACED REVISION & NOTES =================
with tab4:
    st.subheader("🔁 AI Spaced Repetition Alerts (Forgetting Curve Protection)")
    rev_col1, rev_col2 = st.columns([1, 1.2])
    
    with rev_col1:
        st.markdown("**Aaj kin subjects ka revision due hai?**")
        for idx, s in enumerate(db["subjects"]):
            last_rev = datetime.strptime(s["Last_Revised"], "%Y-%m-%d").date()
            gap = (today - last_rev).days
            
            if gap >= 3 and s["Completed"] > 0:
                st.error(f"⚠️ **{s['Subject']}** — {gap} din se revise nahi hua! (High forgetting risk)")
            else:
                st.success(f"✅ **{s['Subject']}** — {gap} din pehle revise kiya tha.")
                
            if st.button(f"🔄 Mark '{s['Subject']}' Revised Today (+25 XP)", key=f"rev_{idx}"):
                db["subjects"][idx]["Last_Revised"] = str(today)
                db["xp"] += 25
                save_data(db)
                st.rerun()

    with rev_col2:
        st.markdown("**📝 Quick Revision Flashcards & Formula Vault**")
        if db["subjects"]:
            note_sub_idx = st.selectbox(
                "Subject chunein:",
                range(len(db["subjects"])),
                format_func=lambda x: db["subjects"][x]["Subject"]
            )
            current_note = db["subjects"][note_sub_idx].get("Notes", "")
            updated_note = st.text_area("Important Formulas / Short Notes likhein:", value=current_note, height=200)
            if st.button("💾 Save Notes"):
                db["subjects"][note_sub_idx]["Notes"] = updated_note
                save_data(db)
                st.success("Notes save ho gaye!")

# ================= TAB 5: MANAGE SUBJECTS =================
with tab5:
    m_col1, m_col2 = st.columns([1, 1.5])
    
    with m_col1:
        st.subheader("➕ Naya Subject Add Karein")
        with st.form("new_sub_form", clear_on_submit=True):
            name = st.text_input("Subject Name")
            diff = st.slider("Difficulty (1=Easy, 5=Hard)", 1, 5, 3)
            e_date = st.date_input("Exam Date", min_value=today)
            tot_t = st.number_input("Total Chapters/Topics", 1, 100, 8)
            comp_t = st.number_input("Completed Chapters", 0, 100, 0)
            init_note = st.text_area("Initial Key Concepts (Optional)")
            
            if st.form_submit_button("Add Subject"):
                if not name.strip():
                    st.error("Subject ka naam likhein!")
                elif comp_t > tot_t:
                    st.error("Completed chapters total se zyada nahi ho sakte!")
                else:
                    db["subjects"].append({
                        "Subject": name.strip(),
                        "Difficulty": diff,
                        "Exam Date": str(e_date),
                        "Topics": int(tot_t),
                        "Completed": int(comp_t),
                        "Last_Revised": str(today),
                        "Notes": init_note
                    })
                    save_data(db)
                    st.success(f"{name} added!")
                    st.rerun()

    with m_col2:
        st.subheader("📚 Update Progress / Delete Subjects")
        for idx, s in enumerate(db["subjects"]):
            with st.expander(f"{s['Subject']} — ({s['Completed']}/{s['Topics']} Done) | Exam: {s['Exam Date']}", expanded=True):
                prog = s["Completed"] / s["Topics"] if s["Topics"] > 0 else 0
                st.progress(prog)
                b1, b2, b3 = st.columns([1.5, 1.5, 1])
                
                if s["Completed"] < s["Topics"]:
                    if b1.button("✅ Complete +1 Topic (+30 XP)", key=f"inc_{idx}"):
                        db["subjects"][idx]["Completed"] += 1
                        db["subjects"][idx]["Last_Revised"] = str(today)
                        db["xp"] += 30
                        save_data(db)
                        st.rerun()
                if s["Completed"] > 0:
                    if b2.button("↩️ Undo -1 Topic", key=f"dec_{idx}"):
                        db["subjects"][idx]["Completed"] -= 1
                        save_data(db)
                        st.rerun()
                if b3.button("🗑️ Delete", key=f"del_{idx}"):
                    db["subjects"].pop(idx)
                    save_data(db)
                    st.rerun()

    st.divider()
    if st.button("⚠️ Reset Entire App to Default"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.session_state.db = get_default_data()
        st.rerun()
