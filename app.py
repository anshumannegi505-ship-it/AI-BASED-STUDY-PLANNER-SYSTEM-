from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "study_planner.db"

st.set_page_config(page_title="AI Study Planner Pro", page_icon="🎓", layout="wide")

# ----------------------------- Database layer -----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS subjects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            difficulty TEXT NOT NULL, priority TEXT NOT NULL,
            topics INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL DEFAULT 'General',
            due_date TEXT NOT NULL, estimated_minutes INTEGER NOT NULL DEFAULT 30,
            importance TEXT NOT NULL DEFAULT 'Medium', status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, session_date TEXT NOT NULL, subject TEXT NOT NULL,
            title TEXT NOT NULL, minutes INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Pending'
        );
        CREATE TABLE IF NOT EXISTS focus_logs (
            id TEXT PRIMARY KEY, logged_at TEXT NOT NULL, minutes INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


def rows(query, params=()):
    with get_conn() as con:
        return [dict(r) for r in con.execute(query, params).fetchall()]


def execute(query, params=()):
    with get_conn() as con:
        con.execute(query, params)
        con.commit()


def add_subject(name, difficulty, priority, topics):
    execute("INSERT INTO subjects VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), name.strip(), difficulty, priority, int(topics), datetime.now().isoformat(timespec="seconds")))


def add_task(title, subject, due, minutes, importance):
    execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), title.strip(), subject.strip() or "General", due.isoformat(), int(minutes), importance,
             "Pending", datetime.now().isoformat(timespec="seconds")))


def completed_count():
    return len(rows("SELECT id FROM tasks WHERE status='Completed'")) + len(rows("SELECT id FROM sessions WHERE status='Completed'"))


init_db()

# ------------------------------- Styling ----------------------------------
st.markdown("""
<style>
.stApp {background: radial-gradient(circle at 10% 0%, #172554 0, #0b1224 36%, #080d19 100%); color:#edf2ff;}
[data-testid="stSidebar"] {background:#0c1427; border-right:1px solid #253252;}
.block-container {padding-top:1.5rem; max-width:1500px;}
.hero {padding:26px 30px;border:1px solid #354775;border-radius:20px;background:linear-gradient(115deg,#182b55,#3b2d75 65%,#14516a);margin-bottom:20px;}
.hero h1 {color:white;margin:0;font-size:2.1rem}.hero p{color:#dbeafe;margin:.4rem 0 0}
div[data-testid="stMetric"] {background:#121e36;border:1px solid #2a3b60;padding:14px;border-radius:15px;}
.stButton>button, .stDownloadButton>button {border-radius:10px;font-weight:600;}
section[data-testid="stSidebar"] .stRadio label {padding:3px 0;}
.small-note {color:#aab9d8;font-size:.88rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🎓 AI Study Planner Pro</h1><p>Plan smarter · Focus deeper · Track progress · Learn consistently</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("🎓 Study Planner Pro")
    student = st.text_input("Student name", value=st.session_state.get("student_name", "Anshuman"))
    st.session_state.student_name = student
    pages = ["Dashboard", "My Subjects", "Smart Timetable", "Daily Tasks", "Focus Room", "AI Study Assistant", "Analytics & Reports"]
    initial_page = st.session_state.get("quick_page", "Dashboard")
    page = st.radio("Navigate", pages, index=pages.index(initial_page) if initial_page in pages else 0, key="navigation")
    st.session_state.quick_page = page
    st.divider()
    st.caption("Your data is saved locally in study_planner.db")
    st.caption("AI answers use Gemini when an API key is configured; otherwise the built-in assistant remains available.")

subjects = rows("SELECT * FROM subjects ORDER BY name")
tasks = rows("SELECT * FROM tasks ORDER BY due_date, created_at")
sessions = rows("SELECT * FROM sessions ORDER BY session_date, subject")

# ----------------------------- Core utilities -----------------------------
def make_schedule(subject_list, end_date, hours_per_day, available_days, break_minutes):
    today = date.today()
    days = [today + timedelta(days=i) for i in range((end_date - today).days + 1)
            if (today + timedelta(days=i)).strftime("%A") in available_days]
    if not days or not subject_list:
        return []
    difficulty_weight = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.2}
    priority_weight = {"Low": 1.0, "Medium": 1.5, "High": 2.0}
    weighted = []
    for s in subject_list:
        score = difficulty_weight.get(s["difficulty"], 1) * priority_weight.get(s["priority"], 1) * max(1, int(s["topics"]))
        weighted.append({"subject": s["name"], "weight": score, "remaining": max(1, int(s["topics"])) * 45})
    total_weight = sum(x["weight"] for x in weighted)
    total_minutes = len(days) * int(hours_per_day) * 60
    for item in weighted:
        item["remaining"] = max(25, int(total_minutes * item["weight"] / total_weight))
    output = []
    for day in days:
        free = int(hours_per_day) * 60
        guard = 0
        while free >= 25 and any(x["remaining"] >= 25 for x in weighted) and guard < 100:
            guard += 1
            candidates = [x for x in weighted if x["remaining"] >= 25]
            # Rotate ties to avoid assigning every session to the same subject.
            chosen = max(candidates, key=lambda x: (x["weight"], x["remaining"], -len([p for p in output if p["subject"] == x["subject"]])))
            duration = min(50, chosen["remaining"], free)
            if duration < 25:
                break
            output.append({"id": str(uuid.uuid4()), "session_date": day.isoformat(), "subject": chosen["subject"],
                           "title": f"Study {chosen['subject']} · active recall and practice", "minutes": duration, "status": "Pending"})
            chosen["remaining"] -= duration
            free -= duration + int(break_minutes)
    return output


def local_advice(prompt):
    p = prompt.lower()
    if any(w in p for w in ["timetable", "schedule", "plan my day", "study plan"]):
        return "To build a balanced plan, add your subjects first, set their difficulty and priority, then open **Smart Timetable**. Choose your available days and daily study hours and generate the schedule."
    if any(w in p for w in ["revision", "revise", "remember", "memorize"]):
        return "Try spaced revision: review a topic on the same day, the next day, after 3 days, and after a week. Use active recall (close your notes and explain the idea) followed by practice questions."
    if any(w in p for w in ["focus", "concentrate", "distraction"]):
        return "Try one 25-minute focus block: choose one small task, silence notifications, keep only the required material open, then take a 5-minute break. Repeat 3–4 times and take a longer break."
    if any(w in p for w in ["exam", "deadline", "urgent"]):
        return "Prioritise topics with the nearest deadline, high importance, and weak understanding. Split each topic into a short learning block and a separate practice/revision block."
    return "I can help with study planning, revision methods, focus techniques, subject explanations, exam preparation, and time management. For a personalised schedule, add your subjects and deadlines in the planner."


def ask_gemini(prompt):
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if not api_key:
        return None, "No Gemini API key configured. Using the built-in study assistant."
    try:
        import requests
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + api_key
        payload = {"contents": [{"parts": [{"text": "You are a clear, supportive academic study assistant. Give accurate, structured answers. If unsure, say so.\n\nStudent question: " + prompt}]}],
                   "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1200}}
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"]
        return answer, None
    except Exception as exc:
        return None, f"AI service unavailable ({type(exc).__name__}). Showing built-in guidance instead."

# -------------------------------- Dashboard -------------------------------
if page == "Dashboard":
    st.subheader(f"Welcome back, {student or 'Student'} 👋")
    subject_count = len(subjects)
    pending = len([t for t in tasks if t["status"] == "Pending"]) + len([s for s in sessions if s["status"] == "Pending"])
    done = completed_count()
    total = pending + done
    focus_total = sum(x["minutes"] for x in rows("SELECT minutes FROM focus_logs"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📚 Subjects", subject_count)
    c2.metric("✅ Completed items", done)
    c3.metric("⏳ Pending items", pending)
    c4.metric("🔥 Focus time", f"{focus_total // 60}h {focus_total % 60}m")
    st.markdown("### Your progress")
    st.progress(done / total if total else 0.0, text=f"{(done / total * 100) if total else 0:.0f}% completed")
    left, right = st.columns(2)
    with left:
        st.markdown("### 📅 Upcoming deadlines")
        upcoming = [t for t in tasks if t["status"] == "Pending"]
        if upcoming:
            st.dataframe(pd.DataFrame([{"Task": t["title"], "Subject": t["subject"], "Due": t["due_date"], "Priority": t["importance"]} for t in upcoming[:6]]), use_container_width=True, hide_index=True)
        else:
            st.info("No pending tasks. Add an assignment or study task in Daily Tasks.")
    with right:
        st.markdown("### 💡 Smart recommendations")
        if not subjects:
            st.write("• Add your subjects to get personalised recommendations.")
        else:
            for s in sorted(subjects, key=lambda x: (x["priority"] != "High", x["difficulty"] != "Hard"))[:4]:
                st.write(f"• Give **{s['name']}** attention — {s['difficulty'].lower()} difficulty, {s['priority'].lower()} priority.")
            st.write("• Use active recall and solve practice questions after each topic.")
            st.write("• Review difficult topics again after 1, 3, and 7 days.")
    st.markdown("### ⚡ Quick actions")
    q1, q2, q3 = st.columns(3)
    if q1.button("➕ Add a subject", use_container_width=True): st.session_state.navigation = "My Subjects"; st.rerun()
    if q2.button("🗓️ Create timetable", use_container_width=True): st.session_state.navigation = "Smart Timetable"; st.rerun()
    if q3.button("📝 Add a task", use_container_width=True): st.session_state.navigation = "Daily Tasks"; st.rerun()

# ------------------------------ Subject page ------------------------------
elif page == "My Subjects":
    st.subheader("📚 Subject Manager")
    with st.form("add_subject_form", clear_on_submit=True):
        name = st.text_input("Subject name", placeholder="e.g. Python Programming")
        a, b, c = st.columns(3)
        difficulty = a.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
        priority = b.selectbox("Priority", ["Low", "Medium", "High"], index=1)
        topic_count = c.number_input("Number of topics", min_value=1, max_value=100, value=5)
        submitted = st.form_submit_button("➕ Add subject", use_container_width=True)
    if submitted:
        if not name.strip(): st.error("Please enter a subject name.")
        elif any(s["name"].casefold() == name.strip().casefold() for s in subjects): st.warning("That subject already exists.")
        else:
            try:
                add_subject(name, difficulty, priority, topic_count)
                st.success("Subject saved."); st.rerun()
            except sqlite3.IntegrityError: st.error("Could not add this subject. Check whether it already exists.")
    if subjects:
        st.markdown("### Your subjects")
        st.dataframe(pd.DataFrame([{ "Subject":s["name"], "Difficulty":s["difficulty"], "Priority":s["priority"], "Topics":s["topics"]} for s in subjects]), use_container_width=True, hide_index=True)
        names = [s["name"] for s in subjects]
        selected = st.selectbox("Select a subject to remove", names)
        if st.button("🗑️ Remove selected subject", type="secondary"):
            execute("DELETE FROM subjects WHERE name=?", (selected,))
            st.warning("Subject removed. Existing tasks and timetable sessions were kept as history."); st.rerun()
    else: st.info("No subjects yet. Add your first subject above.")

# ------------------------------ Timetable page ----------------------------
elif page == "Smart Timetable":
    st.subheader("🗓️ Smart Timetable Generator")
    if not subjects: st.warning("Add at least one subject in My Subjects before generating a timetable.")
    with st.form("schedule_form"):
        end_date = st.date_input("Plan until", value=date.today() + timedelta(days=14), min_value=date.today())
        hours = st.slider("Available study hours per day", 1, 10, 3)
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        available = st.multiselect("Days available", weekdays, default=weekdays[:6])
        pause = st.selectbox("Break between sessions", [5, 10, 15, 20], index=1, format_func=lambda x: f"{x} minutes")
        generate = st.form_submit_button("✨ Generate / Replace timetable", type="primary", use_container_width=True)
    if generate:
        if not subjects: st.error("Please add subjects first.")
        elif not available: st.error("Select at least one available day.")
        else:
            planned = make_schedule(subjects, end_date, hours, available, pause)
            if not planned: st.warning("No sessions could be created. Check the date range and available days.")
            else:
                with get_conn() as con:
                    con.execute("DELETE FROM sessions WHERE status='Pending'")
                    con.executemany("INSERT INTO sessions VALUES (?,?,?,?,?,?)", [(p["id"], p["session_date"], p["subject"], p["title"], p["minutes"], p["status"]) for p in planned])
                    con.commit()
                st.success(f"Created {len(planned)} study sessions. Previously completed sessions were preserved."); st.rerun()
    sessions = rows("SELECT * FROM sessions ORDER BY session_date, subject")
    if sessions:
        view = pd.DataFrame([{"Date":s["session_date"], "Subject":s["subject"], "Study task":s["title"], "Duration":f"{s['minutes']} min", "Status":s["status"]} for s in sessions])
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download timetable CSV", view.to_csv(index=False).encode("utf-8-sig"), "study_timetable.csv", "text/csv")
        st.markdown("### Update session progress")
        pending_sessions = [s for s in sessions if s["status"] == "Pending"]
        if pending_sessions:
            selected_session = st.selectbox("Pending session", pending_sessions, format_func=lambda s: f"{s['session_date']} · {s['subject']} · {s['minutes']} min")
            if st.button("✅ Mark selected session complete"):
                execute("UPDATE sessions SET status='Completed' WHERE id=?", (selected_session["id"],)); st.success("Session marked complete."); st.rerun()
        else: st.success("All timetable sessions are completed!")
        if st.button("🧹 Clear pending timetable sessions"):
            execute("DELETE FROM sessions WHERE status='Pending'"); st.rerun()
    else: st.info("Your timetable will appear here after generation.")

# -------------------------------- Tasks page -------------------------------
elif page == "Daily Tasks":
    st.subheader("✅ Daily Task Manager")
    subject_options = [s["name"] for s in subjects] + ["General"]
    with st.form("task_form", clear_on_submit=True):
        title = st.text_input("Task title", placeholder="Complete DBMS assignment")
        a, b, c = st.columns(3)
        task_subject = a.selectbox("Subject", subject_options)
        due = b.date_input("Due date", value=date.today())
        minutes = c.number_input("Estimated time (minutes)", min_value=5, max_value=600, value=30, step=5)
        importance = st.selectbox("Importance", ["Low", "Medium", "High"], index=1)
        add = st.form_submit_button("➕ Add task", use_container_width=True)
    if add:
        if not title.strip(): st.error("Task title cannot be empty.")
        else: add_task(title, task_subject, due, minutes, importance); st.success("Task added."); st.rerun()
    tasks = rows("SELECT * FROM tasks ORDER BY CASE status WHEN 'Pending' THEN 0 ELSE 1 END, due_date")
    if tasks:
        st.markdown("### Your tasks")
        filter_status = st.selectbox("Filter", ["All", "Pending", "Completed"])
        shown = [t for t in tasks if filter_status == "All" or t["status"] == filter_status]
        for task in shown:
            with st.container(border=True):
                left, mid, right = st.columns([5, 2, 1])
                left.markdown(f"**{task['title']}**  \n{task['subject']} · Due {task['due_date']} · {task['estimated_minutes']} min · {task['importance']} priority")
                mid.write(task["status"])
                if task["status"] == "Pending":
                    if right.button("Complete", key="done_" + task["id"]):
                        execute("UPDATE tasks SET status='Completed' WHERE id=?", (task["id"],)); st.rerun()
                else:
                    if right.button("Reopen", key="reopen_" + task["id"]):
                        execute("UPDATE tasks SET status='Pending' WHERE id=?", (task["id"],)); st.rerun()
                if st.button("Delete task", key="delete_" + task["id"]):
                    execute("DELETE FROM tasks WHERE id=?", (task["id"],)); st.rerun()
    else: st.info("No tasks yet. Add your first task above.")

# -------------------------------- Focus page -------------------------------
elif page == "Focus Room":
    st.subheader("⏱️ Focus Room · Pomodoro")
    if "focus_mode" not in st.session_state: st.session_state.focus_mode = "Focus"
    if "focus_end" not in st.session_state: st.session_state.focus_end = None
    if "focus_remaining" not in st.session_state: st.session_state.focus_remaining = 25 * 60
    mode = st.radio("Session type", ["Focus", "Short break", "Long break"], horizontal=True, key="focus_mode")
    duration = {"Focus":25, "Short break":5, "Long break":15}[mode] * 60
    if st.session_state.get("last_focus_mode") != mode and st.session_state.focus_end is None:
        st.session_state.focus_remaining = duration
        st.session_state.last_focus_mode = mode

    @st.fragment(run_every="1s")
    def timer_display():
        end = st.session_state.focus_end
        remaining = max(0, int(end - datetime.now().timestamp())) if end else int(st.session_state.focus_remaining)
        mm, ss = divmod(remaining, 60)
        st.markdown(f"<div style='text-align:center;font-size:76px;font-weight:800;letter-spacing:3px;color:#93c5fd'>{mm:02d}:{ss:02d}</div>", unsafe_allow_html=True)
        if end and remaining == 0:
            st.session_state.focus_end = None
            st.session_state.focus_remaining = 0
            if mode == "Focus":
                execute("INSERT INTO focus_logs VALUES (?,?,?)", (str(uuid.uuid4()), datetime.now().isoformat(timespec="seconds"), 25))
                st.session_state.focus_remaining = duration
                st.success("Focus session complete! Take a break.")
            else:
                st.session_state.focus_remaining = duration
                st.success("Break complete. Ready for the next session?")
            st.rerun()
    timer_display()
    a, b, c = st.columns(3)
    if a.button("▶ Start / Resume", use_container_width=True):
        if st.session_state.focus_end is None:
            st.session_state.focus_end = datetime.now().timestamp() + int(st.session_state.focus_remaining or duration)
            st.rerun()
    if b.button("⏸ Pause", use_container_width=True):
        if st.session_state.focus_end is not None:
            st.session_state.focus_remaining = max(0, int(st.session_state.focus_end - datetime.now().timestamp()))
            st.session_state.focus_end = None
            st.rerun()
    if c.button("↻ Reset", use_container_width=True):
        st.session_state.focus_end = None; st.session_state.focus_remaining = duration; st.rerun()
    total_focus = sum(x["minutes"] for x in rows("SELECT minutes FROM focus_logs"))
    st.metric("Total completed focus time", f"{total_focus} minutes")
    st.caption("The countdown updates automatically. Completed 25-minute focus blocks are saved in your study history.")

# ----------------------------- AI Assistant page --------------------------
elif page == "AI Study Assistant":
    st.subheader("🤖 AI Study Assistant")
    st.write("Ask questions about subjects, concepts, exam preparation, revision, or study planning.")
    history = rows("SELECT role, message FROM chat_history ORDER BY id DESC LIMIT 20")
    for item in reversed(history):
        with st.chat_message(item["role"]): st.markdown(item["message"])
    prompt = st.chat_input("Ask your study assistant anything...")
    if prompt:
        execute("INSERT INTO chat_history(role,message,created_at) VALUES (?,?,?)", ("user", prompt, datetime.now().isoformat(timespec="seconds")))
        answer, warning = ask_gemini(prompt)
        if warning: st.info(warning)
        if answer is None: answer = local_advice(prompt)
        execute("INSERT INTO chat_history(role,message,created_at) VALUES (?,?,?)", ("assistant", answer, datetime.now().isoformat(timespec="seconds")))
        st.rerun()
    col1, col2 = st.columns(2)
    if col1.button("🧹 Clear chat history"):
        execute("DELETE FROM chat_history"); st.rerun()
    col2.caption("Configure GEMINI_API_KEY to enable open-ended AI responses. The app works without it.")

# ------------------------------ Analytics page ----------------------------
elif page == "Analytics & Reports":
    st.subheader("📊 Analytics & Reports")
    tasks = rows("SELECT * FROM tasks")
    sessions = rows("SELECT * FROM sessions")
    focus = rows("SELECT * FROM focus_logs ORDER BY logged_at")
    total_items = len(tasks) + len(sessions)
    completed_items = sum(1 for x in tasks + sessions if x["status"] == "Completed")
    focus_minutes = sum(x["minutes"] for x in focus)
    a, b, c = st.columns(3)
    a.metric("Completion rate", f"{completed_items / total_items * 100:.0f}%" if total_items else "0%")
    b.metric("Completed focus blocks", len(focus))
    c.metric("Total focus hours", f"{focus_minutes / 60:.1f} h")
    if sessions:
        by_subject = pd.DataFrame(sessions).groupby("subject")["minutes"].sum().sort_values(ascending=False)
        st.markdown("### Planned study time by subject")
        st.bar_chart(by_subject)
    if tasks:
        status_counts = pd.Series([x["status"] for x in tasks]).value_counts()
        st.markdown("### Task status")
        st.bar_chart(status_counts)
    if focus:
        focus_df = pd.DataFrame(focus)
        focus_df["day"] = pd.to_datetime(focus_df["logged_at"]).dt.date.astype(str)
        daily = focus_df.groupby("day")["minutes"].sum()
        st.markdown("### Focus time by day")
        st.line_chart(daily)
    report_rows = ([{"Type":"Task", "Title":t["title"], "Subject":t["subject"], "Date":t["due_date"], "Minutes":t["estimated_minutes"], "Status":t["status"]} for t in tasks]
                   + [{"Type":"Study session", "Title":s["title"], "Subject":s["subject"], "Date":s["session_date"], "Minutes":s["minutes"], "Status":s["status"]} for s in sessions])
    if report_rows:
        report = pd.DataFrame(report_rows)
        st.download_button("⬇️ Download complete study report (CSV)", report.to_csv(index=False).encode("utf-8-sig"), "study_report.csv", "text/csv")
    else: st.info("Complete tasks and focus sessions to build your analytics report.")

st.sidebar.divider()
st.sidebar.caption("Built with Python · Streamlit · SQLite · Pandas")
