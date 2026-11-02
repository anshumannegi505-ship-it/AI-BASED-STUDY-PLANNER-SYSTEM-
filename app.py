import streamlit as st
import pandas as pd
import sqlite3
import json
import time
import random
from datetime import date, datetime, timedelta
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

# =========================================================
# AI STUDY PLANNER PRO — SQLite-powered Streamlit application
# =========================================================
st.set_page_config(
    page_title="AI Study Planner Pro",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path(__file__).with_name("study_planner.db")

# ------------------------- DATABASE -------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            difficulty TEXT NOT NULL DEFAULT 'Medium',
            priority TEXT NOT NULL DEFAULT 'Medium',
            topics INTEGER NOT NULL DEFAULT 5,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_date TEXT NOT NULL,
            subject_id INTEGER,
            subject_name TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            task TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT 'General',
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            completed_at TEXT NOT NULL
        );
        """)
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('student_name','Student')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('points','0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('last_done','')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('streak','0')"
        )

def query_df(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def execute(sql, params=()):
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid

def get_setting(key, default=""):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )

def award_points(points=10):
    current = int(get_setting("points", "0"))
    set_setting("points", current + points)
    today = date.today()
    last = get_setting("last_done", "")
    streak = int(get_setting("streak", "0"))
    if last != today.isoformat():
        if last == (today - timedelta(days=1)).isoformat():
            streak += 1
        else:
            streak = 1
        set_setting("last_done", today.isoformat())
        set_setting("streak", streak)

init_db()

# ------------------------- THEME -------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root { --bg:#070d20; --panel:#101a39; --panel2:#14234a; --line:#263968; --blue:#4267ff; --cyan:#18d7d0; }
html, body, [class*="css"] { font-family:Inter, sans-serif; }
.stApp { background:radial-gradient(circle at 78% 0%, #182653 0%, #0a122b 38%, #070d20 78%); color:#f4f7ff; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#101a3b,#0b1430); border-right:1px solid #26345f; }
[data-testid="stSidebar"] * { color:#e8edff; }
.block-container { padding-top:1.35rem; padding-bottom:2rem; max-width:1600px; }
h1,h2,h3,h4,p,label,span { color:inherit; }
.hero {
 background:linear-gradient(105deg,rgba(12,24,57,.96),rgba(35,57,125,.82)),
 radial-gradient(circle at 85% 30%,#8c57e9,transparent 28%);
 border:1px solid #35477e; border-radius:22px; padding:26px 30px; margin-bottom:18px;
 box-shadow:0 12px 35px rgba(0,0,0,.22);
}
.hero h1 {font-size:30px; font-weight:800; margin:0; color:white;}
.hero p {color:#c9d6ff; margin:7px 0 0; font-size:15px;}
.eyebrow {color:#8ea9ff; text-transform:uppercase; letter-spacing:2px; font-size:11px; font-weight:700;}
.metric-card {
 background:linear-gradient(145deg,#17264e,#101a38); border:1px solid #2b3e70;
 border-radius:17px; padding:17px 18px; min-height:112px;
 box-shadow:0 8px 22px rgba(0,0,0,.18);
}
.metric-label {font-size:13px;color:#b9c8ef;margin-bottom:8px;}
.metric-value {font-size:28px;font-weight:800;color:#fff;line-height:1.1;}
.metric-note {font-size:11px;color:#54dfb2;margin-top:8px;}
.panel {
 background:linear-gradient(145deg,rgba(20,34,73,.97),rgba(13,23,51,.97));
 border:1px solid #2b3d70; border-radius:18px; padding:18px 20px; margin-bottom:16px;
 box-shadow:0 9px 25px rgba(0,0,0,.17);
}
.panel-title {font-size:18px;font-weight:750;color:#f4f7ff;margin:0 0 14px;}
.small-muted {color:#a9b8df;font-size:12px;}
.stButton>button, .stDownloadButton>button {
 background:linear-gradient(100deg,#475fff,#7b4cf5); color:white; border:0;
 border-radius:10px; font-weight:650; min-height:40px;
}
.stButton>button:hover,.stDownloadButton>button:hover {border:1px solid #a5b5ff;color:white;filter:brightness(1.12);}
.stTextInput input,.stNumberInput input,.stDateInput input,.stTextArea textarea,
.stSelectbox div[data-baseweb="select"]>div,.stMultiSelect div[data-baseweb="select"]>div {
 background:#101d40 !important;color:#f3f6ff !important;border:1px solid #344777 !important;border-radius:9px !important;
}
[data-testid="stDataFrame"] {border:1px solid #2b3d70;border-radius:12px;overflow:hidden;}
.stProgress>div>div>div>div {background:linear-gradient(90deg,#12d6c8,#5967ff);}
div[data-testid="stMetric"] {background:#14234a;border:1px solid #2b3d70;padding:12px 15px;border-radius:14px;}
div[data-testid="stMetric"] label,div[data-testid="stMetric"] [data-testid="stMetricValue"] {color:white;}
hr {border-color:#2a3a67;}
div[data-testid="stAlert"] {border-radius:12px;}
section[data-testid="stSidebar"] .stRadio label {padding:5px 0;}
</style>
""", unsafe_allow_html=True)

# ------------------------- HELPERS -------------------------
def panel_title(title, icon="✨"):
    st.markdown(f'<div class="panel-title">{icon} {title}</div>', unsafe_allow_html=True)

def get_subjects():
    return query_df("SELECT * FROM subjects ORDER BY name")

def get_plans():
    return query_df("SELECT * FROM plans ORDER BY study_date, id")

def get_tasks():
    return query_df("SELECT * FROM tasks ORDER BY due_date, id")

def subject_suggestions():
    subjects = get_subjects()
    if subjects.empty:
        return ["Add your subjects to receive personalised study suggestions."]
    tips = []
    hard = subjects[subjects["difficulty"] == "Hard"]["name"].tolist()
    high = subjects[subjects["priority"] == "High"]["name"].tolist()
    if hard:
        tips.append("Give extra practice time to: " + ", ".join(hard) + ".")
    if high:
        tips.append("Start with high-priority subjects: " + ", ".join(high) + ".")
    tips.extend([
        "Use active recall: close your notes and explain the topic from memory.",
        "Solve 5–10 practice questions after every learning session.",
        "Take a short break after each focused study block."
    ])
    return tips

def assistant_reply(question):
    q = question.lower()
    if any(x in q for x in ["timetable", "schedule", "plan"]):
        return "Open **Smart Timetable** and choose your exam date, daily study hours and available days. Add subjects first so the planner can distribute your time."
    if any(x in q for x in ["revision", "revise", "remember"]):
        return "Try active recall + spaced revision. Revise a topic after 1 day, 3 days and 7 days, then solve questions without looking at notes."
    if any(x in q for x in ["python", "coding"]):
        return "For Python, practise variables, conditions, loops, functions, lists, dictionaries and file handling. Write small programs daily instead of only watching tutorials."
    if any(x in q for x in ["dbms", "database", "sql"]):
        return "For DBMS, focus on keys, ER diagrams, normalization, SQL queries, joins and transactions. Practise writing queries by hand."
    if any(x in q for x in ["focus", "pomodoro", "concentration"]):
        return "Try one 25-minute focus session, keep your phone away, and take a 5-minute break. Repeat the cycle 3–4 times."
    if any(x in q for x in ["machine learning", "ml", "ai"]):
        return "Build your ML foundation in this order: Python, NumPy/Pandas, statistics, data visualization, train-test split, regression, classification and model evaluation."
    return "I can help with study planning, revision strategies, Python, DBMS, AI/ML and focus techniques. Tell me the subject or topic you are working on."

def make_plan(subjects, exam_date, hours, selected_days, break_mins):
    today = date.today()
    study_days = [
        today + timedelta(days=i)
        for i in range((exam_date - today).days + 1)
        if (today + timedelta(days=i)).strftime("%A") in selected_days
    ]
    if not study_days:
        return []
    difficulty_weight = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.2}
    priority_weight = {"Low": 1.0, "Medium": 1.5, "High": 2.0}
    weights = {
        row["name"]: difficulty_weight[row["difficulty"]] *
                     priority_weight[row["priority"]] * int(row["topics"])
        for _, row in subjects.iterrows()
    }
    total_weight = sum(weights.values()) or 1
    total_minutes = len(study_days) * hours * 60
    remaining = {name: max(25, int(total_minutes * weight / total_weight))
                 for name, weight in weights.items()}
    output = []
    for day in study_days:
        available = hours * 60
        safety = 0
        while available >= 25 and any(v >= 25 for v in remaining.values()) and safety < 100:
            safety += 1
            name = max(remaining, key=remaining.get)
            duration = min(60, remaining[name], available)
            if duration < 25:
                break
            output.append({
                "study_date": day.isoformat(),
                "subject_name": name,
                "minutes": int(duration),
                "task": f"Study {name}: learn, revise and practise questions"
            })
            remaining[name] -= duration
            available -= duration + break_mins
    return output

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.markdown("## 🎓 AI Study")
    st.markdown("### Planner **Pro**")
    st.caption("PLAN  •  LEARN  •  EXCEL")
    st.markdown("---")
    student_name = st.text_input("Student name", value=get_setting("student_name", "Student"))
    if student_name.strip() and student_name != get_setting("student_name", "Student"):
        set_setting("student_name", student_name.strip())
    st.markdown("""
    <div style="background:linear-gradient(140deg,#1b3c83,#302c78);padding:14px;border-radius:14px;text-align:center;margin:8px 0 16px">
    <div style="font-size:34px">🤖</div><b>Your Study Buddy</b><br>
    <span style="font-size:12px;color:#dce5ff">Always here to help you learn ✨</span>
    </div>""", unsafe_allow_html=True)
    pages = [
        "Dashboard", "My Subjects", "Smart Timetable", "Daily Tasks",
        "Track Progress", "Focus Timer", "Study Assistant", "Achievements", "Settings"
    ]
    page = st.radio("NAVIGATION", pages, label_visibility="collapsed")
    st.markdown("---")
    st.markdown(
        f"""<div style="background:#182650;padding:15px;border-radius:14px;text-align:center">
        <div style="font-size:13px">👑 Study Streak</div>
        <div style="font-size:26px;font-weight:800">{get_setting('streak','0')} Days 🔥</div>
        <span style="font-size:12px;color:#c6d4ff">Keep going!</span></div>""",
        unsafe_allow_html=True
    )
    st.caption("Data is saved in a local SQLite database.")

# ------------------------- HEADER -------------------------
now_hour = datetime.now().hour
greeting = "Good morning" if now_hour < 12 else "Good afternoon" if now_hour < 17 else "Good evening"
st.markdown(f"""
<div class="hero">
 <div class="eyebrow">AI STUDY PLANNER PRO</div>
 <h1>{greeting}, {student_name or 'Student'}! 👋</h1>
 <p>Let's make today productive and achieve your goals.</p>
 <div style="text-align:right;color:#d7ddff;font-style:italic;font-size:13px">“Dream Big, Study Hard, Achieve More!”</div>
</div>
""", unsafe_allow_html=True)

# ------------------------- DASHBOARD -------------------------
if page == "Dashboard":
    subjects = get_subjects()
    plans = get_plans()
    tasks = get_tasks()
    total_items = len(plans) + len(tasks)
    done_items = (int(plans["completed"].sum()) if not plans.empty else 0) + (int(tasks["completed"].sum()) if not tasks.empty else 0)
    progress = round(done_items / total_items * 100) if total_items else 0
    focus = query_df("SELECT COALESCE(SUM(minutes),0) AS mins FROM focus_sessions")
    study_hours = float(focus.iloc[0]["mins"]) / 60 if not focus.empty else 0
    cols = st.columns(4)
    metrics = [
        ("📚", "Total Subjects", len(subjects), "Your learning areas"),
        ("⏱️", "Study Hours", f"{study_hours:.1f} hrs", "Completed focus time"),
        ("✅", "Completed Tasks", f"{done_items} / {total_items}", "Plans + daily tasks"),
        ("🎯", "Progress", f"{progress}%", "Overall completion")
    ]
    for col, (icon, label, value, note) in zip(cols, metrics):
        with col:
            st.markdown(f"""<div class="metric-card"><div class="metric-label">{icon} {label}</div>
            <div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>""", unsafe_allow_html=True)
    st.markdown("")
    left, right = st.columns([1.65, 1])
    with left:
        with st.container():
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            panel_title("Your Study Timetable", "🗓️")
            if plans.empty:
                st.info("Your timetable is empty. Add subjects and generate your first smart timetable.")
            else:
                view = plans.copy()
                view["Date"] = pd.to_datetime(view["study_date"]).dt.strftime("%d-%m-%Y")
                view["Day"] = pd.to_datetime(view["study_date"]).dt.day_name()
                view["Duration"] = view["minutes"].astype(str) + " min"
                view["Status"] = view["completed"].map({1: "✅ Done", 0: "🟡 Pending"})
                st.dataframe(view[["Date", "Day", "subject_name", "Duration", "task", "Status"]].rename(
                    columns={"subject_name": "Subject", "task": "Study task"}),
                    use_container_width=True, hide_index=True)
                csv = view.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download timetable CSV", csv, "study_timetable.csv", "text/csv")
            st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        panel_title("Today's Focus", "🍅")
        today_plans = plans[plans["study_date"] == date.today().isoformat()] if not plans.empty else plans
        today_done = int(today_plans["completed"].sum()) if not today_plans.empty else 0
        st.markdown(f"<div style='font-size:48px;font-weight:800;text-align:center;color:#fff'>{today_done}/{len(today_plans)}</div><div style='text-align:center;color:#aebde6'>Today's sessions completed</div>", unsafe_allow_html=True)
        st.progress(today_done / len(today_plans) if len(today_plans) else 0)
        st.caption("Open Focus Timer to start a Pomodoro session.")
        if st.button("Open Focus Timer", use_container_width=True):
            st.session_state["navigate_focus"] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    lower1, lower2 = st.columns([1, 1])
    with lower1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        panel_title("Study Analytics", "📊")
        if not plans.empty:
            chart_data = plans.groupby("subject_name", as_index=False)["minutes"].sum()
            fig = px.bar(chart_data, x="subject_name", y="minutes", color="subject_name",
                         template="plotly_dark", labels={"subject_name": "Subject", "minutes": "Planned minutes"})
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(l=5,r=5,t=10,b=5), height=260)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Generate a timetable to see your study analytics.")
        st.markdown('</div>', unsafe_allow_html=True)
    with lower2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        panel_title("Smart Study Suggestions", "🤖")
        for tip in subject_suggestions():
            st.markdown("• " + tip)
        st.markdown('</div>', unsafe_allow_html=True)

# ------------------------- SUBJECTS -------------------------
elif page == "My Subjects":
    panel_title("Subject Manager", "📚")
    with st.form("add_subject_form", clear_on_submit=True):
        st.markdown("#### Add a new subject")
        a, b = st.columns(2)
        name = a.text_input("Subject name", placeholder="e.g. Python Programming")
        topics = b.number_input("Number of topics", min_value=1, max_value=100, value=5)
        c, d = st.columns(2)
        difficulty = c.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
        priority = d.selectbox("Priority", ["Low", "Medium", "High"], index=1)
        submitted = st.form_submit_button("➕ Save Subject", use_container_width=True)
    if submitted:
        if not name.strip():
            st.error("Please enter a subject name.")
        else:
            try:
                execute("INSERT INTO subjects(name,difficulty,priority,topics,created_at) VALUES(?,?,?,?,?)",
                        (name.strip(), difficulty, priority, int(topics), datetime.now().isoformat(timespec="seconds")))
                st.success(f"{name.strip()} saved successfully!")
                st.rerun()
            except sqlite3.IntegrityError:
                st.warning("This subject already exists. Try a different name.")
    subjects = get_subjects()
    if not subjects.empty:
        st.markdown("#### Your subjects")
        st.dataframe(subjects[["name", "difficulty", "priority", "topics"]].rename(
            columns={"name": "Subject", "difficulty": "Difficulty", "priority": "Priority", "topics": "Topics"}),
            use_container_width=True, hide_index=True)
        st.markdown("#### Edit or remove a subject")
        options = {f'{r["name"]} (ID {r["id"]})': int(r["id"]) for _, r in subjects.iterrows()}
        selected_label = st.selectbox("Choose subject", list(options.keys()))
        sid = options[selected_label]
        selected = subjects[subjects["id"] == sid].iloc[0]
        with st.form("edit_subject_form"):
            ename = st.text_input("Name", value=selected["name"])
            x, y, z = st.columns(3)
            ediff = x.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=["Easy","Medium","Hard"].index(selected["difficulty"]))
            epriority = y.selectbox("Priority", ["Low", "Medium", "High"], index=["Low","Medium","High"].index(selected["priority"]))
            etopics = z.number_input("Topics", 1, 100, int(selected["topics"]))
            save_edit = st.form_submit_button("💾 Update subject")
        if save_edit:
            try:
                execute("UPDATE subjects SET name=?,difficulty=?,priority=?,topics=? WHERE id=?",
                        (ename.strip(), ediff, epriority, int(etopics), sid))
                execute("UPDATE plans SET subject_name=? WHERE subject_id=?", (ename.strip(), sid))
                st.success("Subject updated.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("A subject with that name already exists.")
        if st.button("🗑️ Delete selected subject", type="secondary"):
            execute("DELETE FROM subjects WHERE id=?", (sid,))
            st.success("Subject deleted. Existing timetable entries are kept as history.")
            st.rerun()
    else:
        st.info("No subjects yet. Use the form above to add your first subject.")

# ------------------------- SMART TIMETABLE -------------------------
elif page == "Smart Timetable":
    panel_title("Smart Timetable Generator", "🗓️")
    subjects = get_subjects()
    if subjects.empty:
        st.warning("First add at least one subject in My Subjects.")
    else:
        with st.form("generate_plan_form"):
            c1, c2 = st.columns(2)
            exam_date = c1.date_input("Exam date", value=date.today() + timedelta(days=14), min_value=date.today())
            hours = c2.slider("Study hours per day", 1, 12, 4)
            days = st.multiselect("Available study days",
                ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
                default=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"])
            pause = st.select_slider("Break between sessions", options=[5,10,15,20], value=10)
            generate = st.form_submit_button("✨ Generate my timetable", use_container_width=True)
        if generate:
            if not days:
                st.error("Select at least one available day.")
            else:
                generated = make_plan(subjects, exam_date, hours, days, pause)
                if not generated:
                    st.warning("No study sessions found. Please check the date and selected days.")
                else:
                    with get_conn() as conn:
                        conn.execute("DELETE FROM plans")
                        for item in generated:
                            sid_row = subjects[subjects["name"] == item["subject_name"]]
                            sid = int(sid_row.iloc[0]["id"]) if not sid_row.empty else None
                            conn.execute(
                                "INSERT INTO plans(study_date,subject_id,subject_name,minutes,task,created_at) VALUES(?,?,?,?,?,?)",
                                (item["study_date"], sid, item["subject_name"], item["minutes"],
                                 item["task"], datetime.now().isoformat(timespec="seconds")))
                    st.success(f"Timetable generated with {len(generated)} study sessions.")
                    st.rerun()
    plans = get_plans()
    if not plans.empty:
        st.markdown("#### Your timetable")
        display = plans.copy()
        display["Date"] = pd.to_datetime(display["study_date"]).dt.strftime("%d %b %Y")
        display["Day"] = pd.to_datetime(display["study_date"]).dt.day_name()
        display["Duration"] = display["minutes"].astype(str) + " min"
        display["Status"] = display["completed"].map({1:"✅ Completed",0:"⏳ Pending"})
        st.dataframe(display[["Date","Day","subject_name","Duration","task","Status"]].rename(
            columns={"subject_name":"Subject","task":"Task"}), use_container_width=True, hide_index=True)
        st.markdown("#### Mark sessions complete")
        for _, row in plans.iterrows():
            label = f'{pd.to_datetime(row["study_date"]).strftime("%d %b")} · {row["subject_name"]} · {row["minutes"]} min'
            checked = st.checkbox(label, value=bool(row["completed"]), key=f'plan_done_{int(row["id"])}')
            if checked != bool(row["completed"]):
                execute("UPDATE plans SET completed=? WHERE id=?", (int(checked), int(row["id"])))
                if checked:
                    award_points(10)
                else:
                    set_setting("points", max(0, int(get_setting("points","0")) - 10))
                st.rerun()
        csv = display.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download timetable CSV", csv, "study_timetable.csv", "text/csv")
        if st.button("🧹 Clear and regenerate timetable"):
            execute("DELETE FROM plans")
            st.rerun()

# ------------------------- DAILY TASKS -------------------------
elif page == "Daily Tasks":
    panel_title("Daily Task Manager", "✅")
    with st.form("new_task_form", clear_on_submit=True):
        title = st.text_input("Task title", placeholder="Complete Python loops assignment")
        a, b = st.columns(2)
        subject = a.text_input("Subject", placeholder="Python")
        due = b.date_input("Due date", value=date.today())
        add_task = st.form_submit_button("➕ Add task", use_container_width=True)
    if add_task:
        if not title.strip():
            st.error("Task title cannot be empty.")
        else:
            execute("INSERT INTO tasks(title,subject,due_date,created_at) VALUES(?,?,?,?)",
                    (title.strip(), subject.strip() or "General", due.isoformat(), datetime.now().isoformat(timespec="seconds")))
            st.success("Task saved successfully.")
            st.rerun()
    tasks = get_tasks()
    if not tasks.empty:
        total = len(tasks)
        done = int(tasks["completed"].sum())
        st.progress(done/total, text=f"{done} of {total} tasks completed")
        for _, task in tasks.iterrows():
            c1, c2, c3 = st.columns([0.08, 0.72, 0.20])
            checked = c1.checkbox(" ", value=bool(task["completed"]), key=f'task_{int(task["id"])}', label_visibility="collapsed")
            text_style = "text-decoration:line-through;color:#8d9abd" if checked else "color:#f1f4ff"
            c2.markdown(f'<div style="{text_style};font-weight:600">{task["title"]}</div><div class="small-muted">{task["subject"]} · Due {pd.to_datetime(task["due_date"]).strftime("%d %b %Y")}</div>', unsafe_allow_html=True)
            if checked != bool(task["completed"]):
                execute("UPDATE tasks SET completed=? WHERE id=?", (int(checked), int(task["id"])))
                if checked: award_points(10)
                else: set_setting("points", max(0, int(get_setting("points","0")) - 10))
                st.rerun()
            if c3.button("🗑️ Delete", key=f'del_task_{int(task["id"])}'):
                execute("DELETE FROM tasks WHERE id=?", (int(task["id"]),))
                st.rerun()
            st.divider()
    else:
        st.info("No daily tasks yet. Add your first task above.")

# ------------------------- TRACK PROGRESS -------------------------
elif page == "Track Progress":
    panel_title("Your Learning Progress", "📈")
    plans = get_plans()
    tasks = get_tasks()
    total = len(plans) + len(tasks)
    done = (int(plans["completed"].sum()) if not plans.empty else 0) + (int(tasks["completed"].sum()) if not tasks.empty else 0)
    rate = done/total if total else 0
    a,b,c = st.columns(3)
    a.metric("Total study items", total)
    b.metric("Completed", done)
    c.metric("Completion rate", f"{rate*100:.1f}%")
    st.progress(rate)
    if not plans.empty:
        st.markdown("#### Planned minutes by subject")
        by_subject = plans.groupby("subject_name", as_index=False)["minutes"].sum()
        fig = px.bar(by_subject, x="subject_name", y="minutes", color="subject_name", template="plotly_dark")
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=350)
        st.plotly_chart(fig, use_container_width=True)
        status = plans.groupby("completed").size().reset_index(name="Sessions")
        status["Status"] = status["completed"].map({0:"Pending",1:"Completed"})
        pie = px.pie(status, names="Status", values="Sessions", hole=.58, template="plotly_dark")
        pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=320)
        st.plotly_chart(pie, use_container_width=True)
    else:
        st.info("Your charts will appear after you generate a timetable.")

# ------------------------- FOCUS TIMER -------------------------
elif page == "Focus Timer":
    panel_title("Pomodoro Focus Room", "🍅")
    mode = st.radio("Choose timer", ["Focus · 25 min", "Short break · 5 min", "Long break · 15 min"], horizontal=True)
    durations = {"Focus · 25 min":25, "Short break · 5 min":5, "Long break · 15 min":15}
    duration = durations[mode] * 60
    if "timer_end" not in st.session_state: st.session_state.timer_end = None
    if "timer_mode" not in st.session_state: st.session_state.timer_mode = mode
    if st.session_state.timer_mode != mode:
        st.session_state.timer_end = None
        st.session_state.timer_mode = mode
    if "timer_paused" not in st.session_state: st.session_state.timer_paused = duration
    if st.session_state.timer_end:
        remaining = max(0, int(st.session_state.timer_end - time.time()))
    else:
        remaining = st.session_state.timer_paused if st.session_state.timer_paused != duration else duration
    mm, ss = divmod(remaining, 60)
    st.markdown(f"""
    <div class="panel" style="text-align:center;padding:30px">
      <div class="small-muted">YOUR FOCUS SESSION</div>
      <div style="font-size:76px;font-weight:800;letter-spacing:3px;color:#a58cff">{mm:02d}:{ss:02d}</div>
      <div style="color:#b8c8ef">{mode}</div>
    </div>""", unsafe_allow_html=True)
    x,y,z = st.columns(3)
    if x.button("▶ Start / Resume", use_container_width=True):
        if not st.session_state.timer_end:
            st.session_state.timer_end = time.time() + remaining
            st.rerun()
    if y.button("⏸ Pause", use_container_width=True):
        if st.session_state.timer_end:
            st.session_state.timer_paused = max(0, int(st.session_state.timer_end-time.time()))
            st.session_state.timer_end = None
            st.rerun()
    if z.button("↻ Reset", use_container_width=True):
        st.session_state.timer_end = None
        st.session_state.timer_paused = duration
        st.rerun()
    if st.session_state.timer_end:
        if remaining <= 0:
            st.session_state.timer_end = None
            st.session_state.timer_paused = duration
            if mode.startswith("Focus"):
                execute("INSERT INTO focus_sessions(mode,minutes,completed_at) VALUES(?,?,?)",
                        ("Focus",25,datetime.now().isoformat(timespec="seconds")))
                award_points(15)
            st.success("Session completed! Great work. 🎉")
            st.rerun()
        else:
            st.info("Timer is running. The display refreshes every second.")
            time.sleep(1)
            st.rerun()
    focus_count = query_df("SELECT COUNT(*) AS n FROM focus_sessions")
    focus_minutes = query_df("SELECT COALESCE(SUM(minutes),0) AS n FROM focus_sessions")
    a,b = st.columns(2)
    a.metric("Completed focus sessions", int(focus_count.iloc[0]["n"]))
    b.metric("Total focus time", f'{int(focus_minutes.iloc[0]["n"])} min')

# ------------------------- STUDY ASSISTANT -------------------------
elif page == "Study Assistant":
    panel_title("Your Study Assistant", "🤖")
    st.markdown('<div class="panel"><b>Hi! I am your Study Buddy.</b><br><span class="small-muted">Ask me about study plans, revision, Python, DBMS, AI/ML or focus techniques.</span></div>', unsafe_allow_html=True)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role":"assistant","content":"Hi! 👋 What are you studying today?"}
        ]
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    prompt = st.chat_input("Ask anything about your studies...")
    if prompt:
        st.session_state.chat_history.append({"role":"user","content":prompt})
        response = assistant_reply(prompt)
        st.session_state.chat_history.append({"role":"assistant","content":response})
        st.rerun()
    st.markdown("#### Quick questions")
    q1,q2,q3 = st.columns(3)
    for col, q in zip([q1,q2,q3], ["Give me study tips", "Explain DBMS revision", "How do I learn Python?"]):
        if col.button(q, use_container_width=True):
            st.session_state.chat_history.append({"role":"user","content":q})
            st.session_state.chat_history.append({"role":"assistant","content":assistant_reply(q)})
            st.rerun()
    st.caption("Note: This is a rule-based assistant. No external AI API is connected yet.")

# ------------------------- ACHIEVEMENTS -------------------------
elif page == "Achievements":
    panel_title("Achievements & Rewards", "🏆")
    points = int(get_setting("points","0"))
    streak = int(get_setting("streak","0"))
    plans = get_plans()
    tasks = get_tasks()
    completed = (int(plans["completed"].sum()) if not plans.empty else 0) + (int(tasks["completed"].sum()) if not tasks.empty else 0)
    focus_count = int(query_df("SELECT COUNT(*) AS n FROM focus_sessions").iloc[0]["n"])
    a,b,c = st.columns(3)
    a.metric("⭐ Total points", points)
    b.metric("🔥 Current streak", f"{streak} days")
    c.metric("✅ Completed items", completed)
    badges = [
        ("🌟","Getting Started","Complete your first task", completed >= 1),
        ("📘","Study Star","Complete 7 study items", completed >= 7),
        ("🎯","Goal Getter","Earn 50 points", points >= 50),
        ("👑","Top Student","Earn 100 points", points >= 100),
        ("🍅","Focus Hero","Complete 5 focus sessions", focus_count >= 5),
        ("🔥","Consistency King","Build a 7-day streak", streak >= 7)
    ]
    cols = st.columns(3)
    for i,(emoji,title,desc,unlocked) in enumerate(badges):
        with cols[i%3]:
            st.markdown(f"""<div class="panel" style="text-align:center;min-height:155px">
            <div style="font-size:38px">{emoji}</div><b>{title}</b><div class="small-muted">{desc}</div>
            <div style="margin-top:10px;color:{'#50dfb1' if unlocked else '#f4bd55'};font-weight:700">{'UNLOCKED ✓' if unlocked else 'LOCKED 🔒'}</div>
            </div>""", unsafe_allow_html=True)

# ------------------------- SETTINGS -------------------------
elif page == "Settings":
    panel_title("Settings & Data", "⚙️")
    st.info("Your subjects, timetable, tasks, points and focus sessions are saved in study_planner.db in the same folder as app.py.")
    st.markdown("#### Student profile")
    new_name = st.text_input("Display name", value=get_setting("student_name","Student"))
    if st.button("Save profile"):
        set_setting("student_name", new_name.strip() or "Student")
        st.success("Profile saved.")
        st.rerun()
    st.markdown("#### Export your data")
    subjects = get_subjects()
    tasks = get_tasks()
    plans = get_plans()
    if not subjects.empty:
        st.download_button("Download subjects CSV", subjects.to_csv(index=False).encode("utf-8"), "subjects.csv", "text/csv")
    if not tasks.empty:
        st.download_button("Download tasks CSV", tasks.to_csv(index=False).encode("utf-8"), "daily_tasks.csv", "text/csv")
    if not plans.empty:
        st.download_button("Download timetable CSV", plans.to_csv(index=False).encode("utf-8"), "timetable.csv", "text/csv")
    st.markdown("---")
    st.markdown("#### Danger zone")
    st.warning("Reset permanently deletes all subjects, timetable entries, tasks, points and focus-session history.")
    confirm = st.checkbox("I understand. Delete all project data.")
    if st.button("Reset all data", disabled=not confirm):
        with get_conn() as conn:
            conn.executescript("DELETE FROM subjects; DELETE FROM plans; DELETE FROM tasks; DELETE FROM focus_sessions;")
        set_setting("points","0")
        set_setting("streak","0")
        set_setting("last_done","")
        st.success("All project data has been reset.")
        st.rerun()

st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#8192bd;font-size:12px">🎓 AI Study Planner Pro · Built with Python, Streamlit, Pandas, Plotly & SQLite</div>',
    unsafe_allow_html=True
)
