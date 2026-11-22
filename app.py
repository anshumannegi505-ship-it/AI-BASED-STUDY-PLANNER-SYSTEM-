"""AI Study Planner Pro - Streamlit + SQLite + pandas + Plotly
Run:  pip install streamlit pandas plotly   (optional: anthropic)
      streamlit run app.py
"""
import os
import sqlite3
import time
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

DB = "study_planner.db"
st.set_page_config(page_title="AI Study Planner Pro", page_icon="🎓", layout="wide")


# ---------- Database ----------
def conn():
    return sqlite3.connect(DB)


def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS subjects(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
            exam_date TEXT, difficulty INTEGER, confidence INTEGER);
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER,
            title TEXT, due TEXT, est_hours REAL, done INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER,
            day TEXT, minutes INTEGER);
        """)


def q(sql, params=()):
    with conn() as c:
        return pd.read_sql_query(sql, c, params=params)


def run(sql, params=()):
    with conn() as c:
        c.execute(sql, params)


# ---------- Smart (AI) planning engine ----------
def priority_table():
    """Priority = difficulty x weakness / days left (urgent, hard, weak subjects first)."""
    s = q("SELECT * FROM subjects")
    if s.empty:
        return s
    today = date.today()
    s["days_left"] = s["exam_date"].apply(lambda d: (date.fromisoformat(d) - today).days)
    s = s[s["days_left"] >= 0].copy()
    s["priority"] = s["difficulty"] * (6 - s["confidence"]) / (s["days_left"].clip(lower=1) ** 0.7)
    total = s["priority"].sum() or 1
    s["share"] = s["priority"] / total
    return s.sort_values("priority", ascending=False)


def generate_plan(days, hours_per_day):
    pt = priority_table()
    if pt.empty:
        return pd.DataFrame()
    rows = []
    for i in range(days):
        d = date.today() + timedelta(days=i)
        live = pt[pt["exam_date"].apply(lambda x: date.fromisoformat(x) >= d)]
        if live.empty:
            continue
        share = live["priority"] / live["priority"].sum()
        for (_, r), sh in zip(live.iterrows(), share):
            hrs = round(sh * hours_per_day * 4) / 4  # 15-min blocks
            if hrs > 0:
                rows.append({"Date": d, "Day": d.strftime("%a"), "Subject": r["name"], "Hours": hrs})
    return pd.DataFrame(rows)


def coach_tips():
    pt = priority_table()
    if pt.empty:
        return "Add subjects with exam dates to get personalised advice."
    top = pt.iloc[0]
    tips = [f"🎯 **Focus on {top['name']}** - it is your highest priority "
            f"({int(top['days_left'])} days left, difficulty {top['difficulty']}/5, confidence {top['confidence']}/5)."]
    for _, r in pt.iterrows():
        if r["days_left"] <= 7:
            tips.append(f"⏰ **{r['name']}** exam is in {int(r['days_left'])} days - switch to revision + past papers.")
        if r["confidence"] <= 2:
            tips.append(f"🧩 Low confidence in **{r['name']}**: split it into small topics and test yourself daily.")
    sess = q("SELECT day, minutes FROM sessions")
    if sess.empty:
        tips.append("🍅 Start a Pomodoro session today - consistency beats cramming.")
    else:
        week = sess[sess["day"] >= str(date.today() - timedelta(days=6))]["minutes"].sum()
        tips.append(f"📈 You studied **{week/60:.1f} h** in the last 7 days.")
    tips.append("💤 Sleep 7+ hours and review notes within 24 hours of learning (spaced repetition).")
    return "\n\n".join(tips)


def llm_advice(question):
    """Optional: uses Anthropic API if ANTHROPIC_API_KEY is set, else the rule-based coach."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return coach_tips()
    try:
        import anthropic
        pt = priority_table()[["name", "days_left", "difficulty", "confidence"]].to_string(index=False)
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model="claude-sonnet-4-6", max_tokens=600,
            messages=[{"role": "user", "content":
                       f"I am a student. My subjects:\n{pt}\n\n{question}\nGive a short, practical study answer."}])
        return msg.content[0].text
    except Exception as e:
        return f"AI unavailable ({e}).\n\n" + coach_tips()


def streak():
    s = q("SELECT DISTINCT day FROM sessions")
    days = set(s["day"])
    n, d = 0, date.today()
    while str(d) in days:
        n += 1
        d -= timedelta(days=1)
    return n


# ---------- UI ----------
init_db()
st.title("🎓 AI Study Planner Pro")
st.caption("Smart priorities · auto study plan · tasks · focus timer · analytics · AI coach")

page = st.sidebar.radio("Menu", ["📊 Dashboard", "📚 Subjects", "✅ Tasks", "🗓️ Smart Plan",
                                 "🍅 Focus Timer", "🤖 AI Coach", "⬇️ Export"])
st.sidebar.metric("🔥 Study streak", f"{streak()} days")

subjects = q("SELECT * FROM subjects")
sub_map = dict(zip(subjects["name"], subjects["id"])) if not subjects.empty else {}

if page == "📊 Dashboard":
    pt = priority_table()
    tasks = q("SELECT t.*, s.name AS subject FROM tasks t JOIN subjects s ON s.id=t.subject_id")
    sess = q("SELECT s.name AS subject, x.day, x.minutes FROM sessions x JOIN subjects s ON s.id=x.subject_id")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Subjects", len(subjects))
    c2.metric("Tasks done", f"{int(tasks['done'].sum()) if not tasks.empty else 0}/{len(tasks)}")
    c3.metric("Hours studied", f"{sess['minutes'].sum()/60:.1f}" if not sess.empty else "0.0")
    c4.metric("Next exam (days)", int(pt["days_left"].min()) if not pt.empty else "-")
    if not tasks.empty:
        st.progress(float(tasks["done"].mean()), text="Overall task completion")
    left, right = st.columns(2)
    if not pt.empty:
        left.plotly_chart(px.pie(pt, names="name", values="priority", hole=.45,
                                 title="Where to focus (priority share)"), use_container_width=True)
    if not sess.empty:
        daily = sess.groupby("day", as_index=False)["minutes"].sum()
        right.plotly_chart(px.bar(daily, x="day", y="minutes", title="Daily study minutes"),
                           use_container_width=True)
        by_sub = sess.groupby("subject", as_index=False)["minutes"].sum()
        st.plotly_chart(px.bar(by_sub, x="subject", y="minutes", color="subject",
                               title="Time per subject"), use_container_width=True)
    if subjects.empty:
        st.info("Start by adding a subject in the 📚 Subjects page.")

elif page == "📚 Subjects":
    with st.form("add_sub", clear_on_submit=True):
        c = st.columns(4)
        name = c[0].text_input("Subject name")
        exam = c[1].date_input("Exam date", date.today() + timedelta(days=30))
        diff = c[2].slider("Difficulty", 1, 5, 3)
        conf = c[3].slider("Confidence", 1, 5, 3)
        if st.form_submit_button("➕ Add subject") and name.strip():
            try:
                run("INSERT INTO subjects(name,exam_date,difficulty,confidence) VALUES(?,?,?,?)",
                    (name.strip(), str(exam), diff, conf))
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Subject already exists.")
    if not subjects.empty:
        st.dataframe(subjects.drop(columns="id"), use_container_width=True)
        c = st.columns(2)
        pick = c[0].selectbox("Update / delete", list(sub_map))
        new_conf = c[1].slider("New confidence", 1, 5, 3)
        b1, b2 = st.columns(2)
        if b1.button("💾 Update confidence"):
            run("UPDATE subjects SET confidence=? WHERE id=?", (new_conf, sub_map[pick]))
            st.rerun()
        if b2.button("🗑️ Delete subject"):
            for t in ("tasks", "sessions"):
                run(f"DELETE FROM {t} WHERE subject_id=?", (sub_map[pick],))
            run("DELETE FROM subjects WHERE id=?", (sub_map[pick],))
            st.rerun()

elif page == "✅ Tasks":
    if not sub_map:
        st.warning("Add a subject first.")
    else:
        with st.form("add_task", clear_on_submit=True):
            c = st.columns(4)
            sname = c[0].selectbox("Subject", list(sub_map))
            title = c[1].text_input("Task")
            due = c[2].date_input("Due", date.today() + timedelta(days=3))
            est = c[3].number_input("Est. hours", 0.25, 20.0, 1.0, 0.25)
            if st.form_submit_button("➕ Add task") and title.strip():
                run("INSERT INTO tasks(subject_id,title,due,est_hours) VALUES(?,?,?,?)",
                    (sub_map[sname], title.strip(), str(due), est))
                st.rerun()
        tasks = q("SELECT t.id,t.title,t.due,t.est_hours,t.done,s.name AS subject "
                  "FROM tasks t JOIN subjects s ON s.id=t.subject_id ORDER BY t.done, t.due")
        today = str(date.today())
        for _, t in tasks.iterrows():
            c = st.columns([0.07, 0.5, 0.2, 0.13, 0.1])
            checked = c[0].checkbox("", bool(t["done"]), key=f"d{t['id']}")
            if checked != bool(t["done"]):
                run("UPDATE tasks SET done=? WHERE id=?", (int(checked), t["id"]))
                st.rerun()
            late = (not t["done"]) and t["due"] < today
            c[1].markdown(("~~" + t["title"] + "~~") if t["done"] else t["title"])
            c[2].write(f"{t['subject']} · {'🔴 ' if late else ''}{t['due']}")
            c[3].write(f"{t['est_hours']} h")
            if c[4].button("🗑️", key=f"x{t['id']}"):
                run("DELETE FROM tasks WHERE id=?", (t["id"],))
                st.rerun()

elif page == "🗓️ Smart Plan":
    c = st.columns(2)
    days = c[0].slider("Plan for next N days", 3, 30, 7)
    hrs = c[1].slider("Study hours per day", 1.0, 12.0, 4.0, 0.5)
    plan = generate_plan(days, hrs)
    if plan.empty:
        st.info("Add subjects with upcoming exams to generate a plan.")
    else:
        st.plotly_chart(px.bar(plan, x="Date", y="Hours", color="Subject", title="Your AI-generated schedule"),
                        use_container_width=True)
        st.dataframe(plan.pivot_table(index="Date", columns="Subject", values="Hours", fill_value=0),
                     use_container_width=True)
        st.download_button("⬇️ Download plan (CSV)", plan.to_csv(index=False), "study_plan.csv")

elif page == "🍅 Focus Timer":
    if not sub_map:
        st.warning("Add a subject first.")
    else:
        sname = st.selectbox("Subject", list(sub_map))
        mins = st.number_input("Focus minutes", 1, 120, 25)
        if st.button("▶️ Start focus session"):
            bar, txt = st.progress(0.0), st.empty()
            total = int(mins * 60)
            for s in range(total):
                time.sleep(1)
                bar.progress((s + 1) / total)
                r = total - s - 1
                txt.markdown(f"### ⏳ {r // 60:02d}:{r % 60:02d}")
            run("INSERT INTO sessions(subject_id,day,minutes) VALUES(?,?,?)",
                (sub_map[sname], str(date.today()), int(mins)))
            st.balloons()
            st.success(f"Session logged: {mins} min of {sname}. Take a 5 min break!")
        with st.expander("Or log study time manually"):
            m = st.number_input("Minutes studied", 1, 600, 30, key="man")
            if st.button("Log time"):
                run("INSERT INTO sessions(subject_id,day,minutes) VALUES(?,?,?)",
                    (sub_map[sname], str(date.today()), int(m)))
                st.success("Logged.")

elif page == "🤖 AI Coach":
    st.markdown(coach_tips())
    st.divider()
    ask = st.text_input("Ask your coach (uses Claude if ANTHROPIC_API_KEY is set)",
                        "How should I revise this week?")
    if st.button("Ask") and ask:
        with st.spinner("Thinking..."):
            st.markdown(llm_advice(ask))

else:
    for name, sql in [("subjects", "SELECT * FROM subjects"), ("tasks", "SELECT * FROM tasks"),
                      ("sessions", "SELECT * FROM sessions")]:
        st.download_button(f"⬇️ {name}.csv", q(sql).to_csv(index=False), f"{name}.csv")

# import os
# import sqlite3
# from datetime import date, datetime, timedelta

# import pandas as pd
# import streamlit as st

# # ---------------- CONFIG ----------------
# st.set_page_config(
#     page_title="AI Smart Study Planner",
#     page_icon="🎓",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# DB_NAME = "study_planner.db"


# # ---------------- DATABASE ----------------
# def get_db():
#     return sqlite3.connect(DB_NAME, check_same_thread=False)


# def init_db():
#     with get_db() as conn:
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS subjects (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 name TEXT NOT NULL,
#                 target_hours REAL DEFAULT 5,
#                 color TEXT DEFAULT '#6C63FF'
#             )
#         """)

#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS tasks (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 title TEXT NOT NULL,
#                 subject TEXT,
#                 due_date TEXT,
#                 priority TEXT DEFAULT 'Medium',
#                 status TEXT DEFAULT 'Pending',
#                 estimated_minutes INTEGER DEFAULT 30,
#                 created_at TEXT
#             )
#         """)

#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS sessions (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 subject TEXT,
#                 duration INTEGER,
#                 session_date TEXT
#             )
#         """)

#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS notes (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 title TEXT,
#                 subject TEXT,
#                 content TEXT,
#                 created_at TEXT
#             )
#         """)

#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS revisions (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 topic TEXT,
#                 subject TEXT,
#                 revision_date TEXT,
#                 completed INTEGER DEFAULT 0
#             )
#         """)


# init_db()


# # ---------------- DATABASE HELPERS ----------------
# def query(sql, params=()):
#     with get_db() as conn:
#         return pd.read_sql_query(sql, conn, params=params)


# def execute(sql, params=()):
#     with get_db() as conn:
#         conn.execute(sql, params)
#         conn.commit()


# def get_subjects():
#     df = query("SELECT name FROM subjects ORDER BY name")
#     return df["name"].tolist() if not df.empty else []


# def save_session(subject, minutes):
#     execute(
#         "INSERT INTO sessions(subject, duration, session_date) VALUES (?, ?, ?)",
#         (subject, minutes, date.today().isoformat())
#     )


# # ---------------- STYLING ----------------
# st.markdown("""
# <style>
# .stApp {
#     background: linear-gradient(135deg, #101426, #171d35);
#     color: #ffffff;
# }
# [data-testid="stSidebar"] {
#     background: #11182b;
# }
# h1, h2, h3 {
#     color: #ffffff !important;
# }
# div[data-testid="stMetric"] {
#     background: #202944;
#     padding: 17px;
#     border-radius: 13px;
#     border: 1px solid #354365;
# }
# .stButton > button {
#     border-radius: 9px;
#     border: 1px solid #6678ff;
# }
# </style>
# """, unsafe_allow_html=True)


# # ---------------- SIDEBAR ----------------
# st.sidebar.title("🎓 Study Planner")
# st.sidebar.caption("Your personal AI learning assistant")

# page = st.sidebar.radio(
#     "NAVIGATION",
#     [
#         "🏠 Dashboard",
#         "📚 Subjects",
#         "✅ Daily Tasks",
#         "🗓️ Smart Timetable",
#         "⏱️ Focus Room",
#         "🔁 Revision Tracker",
#         "📝 Notes",
#         "📊 Analytics",
#         "🤖 AI Assistant"
#     ]
# )

# st.sidebar.divider()
# st.sidebar.caption("AI Smart Study Planner | Version 2.0")


# # ---------------- DASHBOARD ----------------
# if page == "🏠 Dashboard":
#     st.title("🏠 Welcome to Your Study Dashboard")
#     st.write(f"Today is **{date.today().strftime('%A, %d %B %Y')}**")

#     subjects_df = query("SELECT * FROM subjects")
#     tasks_df = query("SELECT * FROM tasks")
#     sessions_df = query("SELECT * FROM sessions")

#     total_subjects = len(subjects_df)
#     total_tasks = len(tasks_df)
#     completed_tasks = (
#         len(tasks_df[tasks_df["status"] == "Completed"])
#         if not tasks_df.empty else 0
#     )
#     study_minutes = (
#         int(sessions_df["duration"].sum())
#         if not sessions_df.empty else 0
#     )

#     c1, c2, c3, c4 = st.columns(4)
#     c1.metric("📚 Subjects", total_subjects)
#     c2.metric("📋 Total Tasks", total_tasks)
#     c3.metric("✅ Completed", completed_tasks)
#     c4.metric("⏱️ Study Hours", round(study_minutes / 60, 1))

#     st.divider()
#     left, right = st.columns(2)

#     with left:
#         st.subheader("Today's Tasks")
#         if not tasks_df.empty:
#             today_tasks = tasks_df[
#                 tasks_df["due_date"] == date.today().isoformat()
#             ]
#             if today_tasks.empty:
#                 st.info("No tasks scheduled for today.")
#             else:
#                 st.dataframe(
#                     today_tasks[["title", "subject", "priority", "status"]],
#                     use_container_width=True,
#                     hide_index=True
#                 )
#         else:
#             st.info("Add your first task from Daily Tasks.")

#     with right:
#         st.subheader("Recent Study Sessions")
#         if not sessions_df.empty:
#             recent = sessions_df.tail(5).iloc[::-1]
#             st.dataframe(
#                 recent[["subject", "duration", "session_date"]],
#                 use_container_width=True,
#                 hide_index=True
#             )
#         else:
#             st.info("Your study sessions will appear here.")

#     st.subheader("Overall Task Completion")
#     percentage = (
#         completed_tasks / total_tasks * 100 if total_tasks else 0
#     )
#     st.progress(int(percentage))
#     st.write(f"**{percentage:.1f}%** tasks completed")


# # ---------------- SUBJECTS ----------------
# elif page == "📚 Subjects":
#     st.title("📚 Subject Management")

#     with st.expander("➕ Add New Subject", expanded=True):
#         with st.form("add_subject_form"):
#             name = st.text_input("Subject Name")
#             hours = st.number_input(
#                 "Weekly Target Hours", min_value=1, max_value=60, value=5
#             )
#             color = st.color_picker("Choose Subject Color", "#6C63FF")
#             submitted = st.form_submit_button("Add Subject")

#             if submitted:
#                 if not name.strip():
#                     st.error("Please enter a subject name.")
#                 elif name.strip().lower() in [
#                     s.lower() for s in get_subjects()
#                 ]:
#                     st.warning("This subject already exists.")
#                 else:
#                     execute(
#                         "INSERT INTO subjects(name, target_hours, color) VALUES (?, ?, ?)",
#                         (name.strip(), hours, color)
#                     )
#                     st.success("Subject added successfully!")
#                     st.rerun()

#     subjects_df = query("SELECT * FROM subjects ORDER BY name")
#     st.subheader("Your Subjects")

#     if subjects_df.empty:
#         st.info("No subjects added yet.")
#     else:
#         st.dataframe(subjects_df, use_container_width=True, hide_index=True)

#         subject_to_delete = st.selectbox(
#             "Select a subject to delete",
#             subjects_df["name"].tolist()
#         )
#         if st.button("🗑️ Delete Selected Subject"):
#             execute("DELETE FROM subjects WHERE name = ?", (subject_to_delete,))
#             st.warning("Subject deleted.")
#             st.rerun()


# # ---------------- DAILY TASKS ----------------
# elif page == "✅ Daily Tasks":
#     st.title("✅ Daily Task Manager")

#     subjects = get_subjects()

#     with st.expander("➕ Create New Task", expanded=True):
#         with st.form("add_task_form"):
#             title = st.text_input("Task Title")
#             subject = st.selectbox(
#                 "Subject", subjects if subjects else ["General"]
#             )
#             due = st.date_input("Due Date", value=date.today())
#             priority = st.selectbox(
#                 "Priority", ["High", "Medium", "Low"]
#             )
#             estimate = st.number_input(
#                 "Estimated Time (minutes)",
#                 min_value=5, max_value=600, value=30, step=5
#             )

#             submitted = st.form_submit_button("Save Task")

#             if submitted:
#                 if not title.strip():
#                     st.error("Task title cannot be empty.")
#                 else:
#                     execute("""
#                         INSERT INTO tasks
#                         (title, subject, due_date, priority, status,
#                          estimated_minutes, created_at)
#                         VALUES (?, ?, ?, ?, 'Pending', ?, ?)
#                     """, (
#                         title.strip(), subject, due.isoformat(),
#                         priority, estimate, datetime.now().isoformat()
#                     ))
#                     st.success("Task created!")
#                     st.rerun()

#     tasks = query("SELECT * FROM tasks ORDER BY due_date")

#     st.subheader("Task List")
#     if tasks.empty:
#         st.info("No tasks available. Create your first task.")
#     else:
#         filter_status = st.selectbox(
#             "Filter Tasks",
#             ["All", "Pending", "Completed"]
#         )

#         visible = tasks.copy()
#         if filter_status != "All":
#             visible = visible[visible["status"] == filter_status]

#         st.dataframe(
#             visible[
#                 ["id", "title", "subject", "due_date",
#                  "priority", "status", "estimated_minutes"]
#             ],
#             use_container_width=True,
#             hide_index=True
#         )

#         task_ids = tasks["id"].tolist()
#         selected_id = st.selectbox("Select Task ID", task_ids)

#         selected_task = tasks[tasks["id"] == selected_id].iloc[0]
#         new_status = st.selectbox(
#             "Update Status",
#             ["Pending", "Completed"],
#             index=0 if selected_task["status"] == "Pending" else 1
#         )

#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("Update Task Status"):
#                 execute(
#                     "UPDATE tasks SET status = ? WHERE id = ?",
#                     (new_status, int(selected_id))
#                 )
#                 st.success("Task updated.")
#                 st.rerun()

#         with col2:
#             if st.button("Delete Selected Task"):
#                 execute("DELETE FROM tasks WHERE id = ?", (int(selected_id),))
#                 st.warning("Task deleted.")
#                 st.rerun()


# # ---------------- SMART TIMETABLE ----------------
# elif page == "🗓️ Smart Timetable":
#     st.title("🗓️ Smart Study Timetable")
#     st.write("Generate a study plan using pending tasks and their priorities.")

#     tasks = query("""
#         SELECT * FROM tasks
#         WHERE status = 'Pending'
#         ORDER BY
#         CASE priority
#             WHEN 'High' THEN 1
#             WHEN 'Medium' THEN 2
#             ELSE 3
#         END,
#         due_date ASC
#     """)

#     if tasks.empty:
#         st.info("No pending tasks. Add tasks to generate your timetable.")
#     else:
#         available_hours = st.number_input(
#             "How many hours can you study today?",
#             min_value=1, max_value=16, value=4
#         )
#         break_minutes = st.number_input(
#             "Break after each study block (minutes)",
#             min_value=0, max_value=60, value=10
#         )

#         if st.button("✨ Generate Smart Timetable"):
#             remaining = int(available_hours * 60)
#             plan = []
#             current_time = datetime.combine(date.today(), datetime.strptime(
#                 "09:00", "%H:%M"
#             ).time())

#             for _, task in tasks.iterrows():
#                 if remaining <= 0:
#                     break

#                 duration = min(
#                     int(task["estimated_minutes"]), remaining
#                 )

#                 start = current_time
#                 end = start + timedelta(minutes=duration)

#                 plan.append({
#                     "Start": start.strftime("%I:%M %p"),
#                     "End": end.strftime("%I:%M %p"),
#                     "Task": task["title"],
#                     "Subject": task["subject"],
#                     "Priority": task["priority"],
#                     "Duration": f"{duration} min"
#                 })

#                 current_time = end + timedelta(minutes=int(break_minutes))
#                 remaining -= duration + int(break_minutes)

#             if plan:
#                 st.session_state["generated_plan"] = pd.DataFrame(plan)

#         if "generated_plan" in st.session_state:
#             st.subheader("Your Generated Timetable")
#             st.dataframe(
#                 st.session_state["generated_plan"],
#                 use_container_width=True,
#                 hide_index=True
#             )
#             st.download_button(
#                 "⬇️ Download Timetable CSV",
#                 st.session_state["generated_plan"].to_csv(index=False),
#                 file_name="study_timetable.csv",
#                 mime="text/csv"
#             )


# # ---------------- FOCUS ROOM ----------------
# elif page == "⏱️ Focus Room":
#     st.title("⏱️ Focus Room – Pomodoro Study Session")
#     st.write("Choose a subject and complete a focused study session.")

#     subjects = get_subjects()
#     subject = st.selectbox(
#         "Select Subject", subjects if subjects else ["General"]
#     )

#     mode = st.radio(
#         "Session Type",
#         ["Focus Session", "Short Break", "Long Break"],
#         horizontal=True
#     )

#     durations = {
#         "Focus Session": 25,
#         "Short Break": 5,
#         "Long Break": 15
#     }

#     minutes = st.number_input(
#         "Session Duration (minutes)",
#         min_value=1, max_value=180,
#         value=durations[mode]
#     )

#     st.metric("Selected Duration", f"{minutes} minutes")

#     if st.button("▶️ Start / Complete Session"):
#         if mode == "Focus Session":
#             save_session(subject, int(minutes))
#             st.success(
#                 f"Great work! {minutes} minutes of study saved for {subject}."
#             )
#         else:
#             st.info("Break completed. Take a moment before your next session.")


# # ---------------- REVISION TRACKER ----------------
# elif page == "🔁 Revision Tracker":
#     st.title("🔁 Revision Tracker")
#     st.write("Schedule topics for revision and track what you have revised.")

#     subjects = get_subjects()

#     with st.form("revision_form"):
#         topic = st.text_input("Topic to Revise")
#         subject = st.selectbox(
#             "Subject", subjects if subjects else ["General"]
#         )
#         revision_date = st.date_input(
#             "Revision Date", value=date.today() + timedelta(days=1)
#         )
#         submitted = st.form_submit_button("Schedule Revision")

#         if submitted:
#             if not topic.strip():
#                 st.error("Enter a topic name.")
#             else:
#                 execute("""
#                     INSERT INTO revisions(topic, subject, revision_date)
#                     VALUES (?, ?, ?)
#                 """, (topic.strip(), subject, revision_date.isoformat()))
#                 st.success("Revision scheduled.")
#                 st.rerun()

#     revisions = query(
#         "SELECT * FROM revisions ORDER BY revision_date"
#     )

#     if revisions.empty:
#         st.info("No revisions scheduled.")
#     else:
#         st.dataframe(revisions, use_container_width=True, hide_index=True)

#         revision_id = st.selectbox(
#             "Select Revision ID",
#             revisions["id"].tolist()
#         )

#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("Mark Revision Completed"):
#                 execute(
#                     "UPDATE revisions SET completed = 1 WHERE id = ?",
#                     (int(revision_id),)
#                 )
#                 st.success("Revision completed!")
#                 st.rerun()

#         with col2:
#             if st.button("Delete Revision"):
#                 execute(
#                     "DELETE FROM revisions WHERE id = ?",
#                     (int(revision_id),)
#                 )
#                 st.rerun()


# # ---------------- NOTES ----------------
# elif page == "📝 Notes":
#     st.title("📝 Study Notes")

#     subjects = get_subjects()

#     with st.form("notes_form"):
#         note_title = st.text_input("Note Title")
#         subject = st.selectbox(
#             "Subject", subjects if subjects else ["General"]
#         )
#         content = st.text_area("Write Your Notes", height=180)

#         submitted = st.form_submit_button("Save Notes")

#         if submitted:
#             if not note_title.strip() or not content.strip():
#                 st.error("Please enter both a title and note content.")
#             else:
#                 execute("""
#                     INSERT INTO notes(title, subject, content, created_at)
#                     VALUES (?, ?, ?, ?)
#                 """, (
#                     note_title.strip(), subject, content.strip(),
#                     datetime.now().isoformat()
#                 ))
#                 st.success("Note saved!")
#                 st.rerun()

#     notes = query("SELECT * FROM notes ORDER BY id DESC")

#     st.subheader("Saved Notes")
#     if notes.empty:
#         st.info("Your notes will appear here.")
#     else:
#         for _, note in notes.iterrows():
#             with st.expander(
#                 f"📌 {note['title']} — {note['subject']}"
#             ):
#                 st.write(note["content"])
#                 st.caption(f"Created: {note['created_at']}")

#                 if st.button(
#                     "Delete This Note",
#                     key=f"delete_note_{note['id']}"
#                 ):
#                     execute(
#                         "DELETE FROM notes WHERE id = ?",
#                         (int(note["id"]),)
#                     )
#                     st.rerun()


# # ---------------- ANALYTICS ----------------
# elif page == "📊 Analytics":
#     st.title("📊 Study Analytics")

#     sessions = query("SELECT * FROM sessions")
#     tasks = query("SELECT * FROM tasks")

#     if sessions.empty:
#         st.info("Complete study sessions to see your analytics.")
#     else:
#         total_minutes = int(sessions["duration"].sum())
#         st.metric("Total Focus Time", f"{total_minutes / 60:.1f} hours")

#         sessions["session_date"] = pd.to_datetime(
#             sessions["session_date"], errors="coerce"
#         )

#         daily = (
#             sessions.groupby("session_date")["duration"]
#             .sum()
#             .reset_index()
#             .sort_values("session_date")
#         )

#         st.subheader("Daily Study Time")
#         st.bar_chart(
#             daily.set_index("session_date")["duration"]
#         )

#         subject_time = (
#             sessions.groupby("subject")["duration"]
#             .sum()
#             .sort_values(ascending=False)
#         )

#         st.subheader("Subject-wise Study Time")
#         st.bar_chart(subject_time)

#     if not tasks.empty:
#         completed = int((tasks["status"] == "Completed").sum())
#         pending = int((tasks["status"] == "Pending").sum())

#         st.subheader("Task Performance")
#         st.write(f"Completed tasks: **{completed}**")
#         st.write(f"Pending tasks: **{pending}**")

#         st.bar_chart(pd.DataFrame({
#             "Tasks": [completed, pending]
#         }, index=["Completed", "Pending"]))


# # ---------------- AI ASSISTANT ----------------
# elif page == "🤖 AI Assistant":
#     st.title("🤖 AI Study Assistant")
#     st.caption("Ask questions, plan your study, or get help with your subjects.")

#     api_key = st.secrets.get(
#         "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")
#     )

#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = []

#     for message in st.session_state.chat_history:
#         with st.chat_message(message["role"]):
#             st.markdown(message["content"])

#     prompt = st.chat_input("Ask your AI study assistant...")

#     def make_ai_reply(question):
#         subjects = get_subjects()
#         tasks = query(
#             "SELECT title, subject, due_date, priority, status FROM tasks"
#         )

#         context = f"""
#         You are an intelligent and friendly AI Study Assistant.
#         Help the student with study planning, concepts, productivity,
#         programming, exam preparation and time management.

#         Current subjects: {subjects}
#         Current tasks: {tasks.to_dict(orient='records')}

#         Give clear, accurate, student-friendly answers.
#         If the student asks for a timetable, use their pending tasks.
#         Do not claim to have changed database records unless an action
#         was actually performed.
#         """

#         if api_key:
#             try:
#                 from google import genai

#                 client = genai.Client(api_key=api_key)
#                 response = client.models.generate_content(
#                     model="gemini-2.0-flash",
#                     contents=context + "\n\nStudent question: " + question
#                 )
#                 if response.text:
#                     return response.text
#                 return "I couldn't generate a response. Please try again."
#             except Exception as error:
#                 return (
#                     "Gemini AI could not respond. Check your API key and "
#                     "internet connection. Technical detail: "
#                     + str(error)
#                 )

#         lower = question.lower()

#         if any(word in lower for word in ["hello", "hi", "hey"]):
#             return (
#                 "Hello! I am your Study Assistant. Ask me about your "
#                 "subjects, timetable, programming, or study strategy."
#             )

#         if "subject" in lower:
#             return (
#                 "Your current subjects are: "
#                 + (", ".join(subjects) if subjects else "No subjects added yet.")
#             )

#         if "task" in lower or "pending" in lower:
#             if tasks.empty:
#                 return "You have no tasks yet. Add tasks in Daily Tasks."
#             pending = tasks[tasks["status"] == "Pending"]
#             if pending.empty:
#                 return "Excellent! You have completed all recorded tasks."
#             return "Your pending tasks:\n" + "\n".join(
#                 f"- {row['title']} ({row['subject']}, due {row['due_date']})"
#                 for _, row in pending.iterrows()
#             )

#         if "timetable" in lower or "schedule" in lower:
#             return (
#                 "Open Smart Timetable and select your available study hours. "
#                 "I can generate a priority-based timetable from your pending tasks."
#             )

#         if "motivat" in lower:
#             return (
#                 "Stay consistent. You do not need to finish everything today. "
#                 "Choose one important task, focus on it, and build momentum."
#             )

#         return (
#             "Basic assistant mode is active. I can show your subjects and "
#             "pending tasks. For open-ended questions and detailed AI answers, "
#             "add your Gemini API key using the setup instructions."
#         )

#     if prompt:
#         st.session_state.chat_history.append({
#             "role": "user",
#             "content": prompt
#         })

#         with st.spinner("Thinking..."):
#             reply = make_ai_reply(prompt)

#         st.session_state.chat_history.append({
#             "role": "assistant",
#             "content": reply
#         })
#         st.rerun()

#     if st.button("🧹 Clear Chat"):
#         st.session_state.chat_history = []
#         st.rerun()


# # ---------------- FOOTER ----------------
# st.sidebar.divider()
# st.sidebar.caption("Built with Python + Streamlit + SQLite")
# st.sidebar.caption("AI Smart Study Planner v2.0")
