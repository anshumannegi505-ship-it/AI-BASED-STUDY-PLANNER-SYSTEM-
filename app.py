
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time

st.set_page_config(page_title="AI Study Planner Pro", page_icon="🎓", layout="wide")

# Session data
defaults = {
    "subjects": [], "plan": [], "tasks": [], "completed": set(),
    "points": 0, "streak": 0, "last_done": None, "task_no": 0,
    "focus_end": None, "focus_running": False, "focus_sessions": 0
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v.copy() if isinstance(v, (list, set, dict)) else v

st.markdown("""
<style>
.stApp {background:#f4f7fc}
.hero {background:linear-gradient(110deg,#101c3c,#2457c5);padding:24px;border-radius:17px;color:white}
.hero h1 {color:white;margin:0}
.hero p {color:#dce8ff;margin:6px 0 0}
div[data-testid="stMetric"] {background:white;border:1px solid #e6eaf2;padding:12px;border-radius:12px}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🎓 AI Study Planner Pro</h1><p>Plan smarter • Focus deeper • Track your progress</p></div>', unsafe_allow_html=True)
st.sidebar.title("🎓 Study Planner Pro")
student = st.sidebar.text_input("Student name", "Student")
page = st.sidebar.radio("Navigation", ["Dashboard", "My Subjects", "Smart Timetable", "Daily Tasks", "Focus Room", "Analytics"])
st.sidebar.caption("Data is kept in this browser session. Download your timetable to keep a copy.")

def award(task_id, points=10):
    if task_id not in st.session_state.completed:
        st.session_state.completed.add(task_id)
        st.session_state.points += points
        today = date.today()
        if st.session_state.last_done != today:
            if st.session_state.last_done == today - timedelta(days=1):
                st.session_state.streak += 1
            elif st.session_state.last_done is None or st.session_state.last_done < today - timedelta(days=1):
                st.session_state.streak = 1
            st.session_state.last_done = today

def build_plan(subjects, exam_date, hours, days, break_mins):
    usable = [date.today()+timedelta(days=i)
              for i in range((exam_date-date.today()).days+1)
              if (date.today()+timedelta(days=i)).strftime("%A") in days]
    if not usable:
        return []
    dw = {"Easy":1, "Medium":1.5, "Hard":2.2}
    pw = {"Low":1, "Medium":1.5, "High":2}
    weights = {s["name"]: dw[s["difficulty"]]*pw[s["priority"]]*s["topics"] for s in subjects}
    total = sum(weights.values())
    minutes = len(usable)*hours*60
    remaining = {n:int(minutes*w/total) for n,w in weights.items()}
    result, number = [], 0
    for day in usable:
        left = hours*60
        while left >= 25 and any(v >= 25 for v in remaining.values()):
            name = max(remaining, key=remaining.get)
            duration = min(60, remaining[name], left)
            if duration < 25:
                break
            number += 1
            result.append({"id":f"p{number}", "date":day, "subject":name,
                           "minutes":duration, "task":f"Revise {name} and practise questions"})
            remaining[name] -= duration
            left -= duration + break_mins
    return result

def suggestions():
    if not st.session_state.subjects:
        return ["Add subjects to get tailored suggestions."]
    tips = []
    hard = [s["name"] for s in st.session_state.subjects if s["difficulty"] == "Hard"]
    high = [s["name"] for s in st.session_state.subjects if s["priority"] == "High"]
    if hard: tips.append("Give extra practice time to: " + ", ".join(hard) + ".")
    if high: tips.append("Prioritise these subjects early: " + ", ".join(high) + ".")
    tips += ["Use active recall: close your notes and explain the topic from memory.",
             "Solve practice questions after learning each concept."]
    return tips

if page == "Dashboard":
    st.subheader(f"Welcome back, {student} 👋")
    total = len(st.session_state.plan) + len(st.session_state.tasks)
    done = len(st.session_state.completed)
    a,b,c,d = st.columns(4)
    a.metric("📚 Subjects", len(st.session_state.subjects))
    b.metric("📝 Tasks", total)
    c.metric("⭐ Points", st.session_state.points)
    d.metric("🔥 Streak", f'{st.session_state.streak} day(s)')
    st.markdown("### Overall progress")
    st.progress(done/total if total else 0, text=f"{(done/total*100) if total else 0:.0f}% completed")
    left,right = st.columns(2)
    with left:
        st.markdown("### Your subjects")
        if st.session_state.subjects:
            st.dataframe(pd.DataFrame(st.session_state.subjects), use_container_width=True, hide_index=True)
        else: st.info("Add subjects from My Subjects.")
    with right:
        st.markdown("### 🧠 Smart study suggestions")
        for tip in suggestions(): st.markdown("- "+tip)
    st.info("Pro tip: Consistent focused sessions are more useful than irregular long study sessions.")

elif page == "My Subjects":
    st.subheader("📚 Subject Manager")
    with st.form("subject_form", clear_on_submit=True):
        name = st.text_input("Subject name", placeholder="Python Programming")
        x,y,z = st.columns(3)
        difficulty = x.selectbox("Difficulty", ["Easy","Medium","Hard"])
        priority = y.selectbox("Priority", ["Low","Medium","High"])
        topics = z.number_input("Number of topics", 1, 50, 5)
        submit = st.form_submit_button("➕ Add subject", use_container_width=True)
    if submit:
        if not name.strip(): st.error("Enter a subject name.")
        elif any(s["name"].lower()==name.strip().lower() for s in st.session_state.subjects):
            st.warning("Subject already exists.")
        else:
            st.session_state.subjects.append({"name":name.strip(),"difficulty":difficulty,"priority":priority,"topics":int(topics)})
            st.success("Subject added.")
    if st.session_state.subjects:
        st.dataframe(pd.DataFrame(st.session_state.subjects), use_container_width=True, hide_index=True)
        remove = st.selectbox("Choose subject to remove", ["Select"]+[s["name"] for s in st.session_state.subjects])
        if st.button("Remove subject", disabled=remove=="Select"):
            st.session_state.subjects = [s for s in st.session_state.subjects if s["name"] != remove]
            st.session_state.plan = [p for p in st.session_state.plan if p["subject"] != remove]
            st.rerun()

elif page == "Smart Timetable":
    st.subheader("🗓️ Smart Timetable Generator")
    with st.form("plan_form"):
        exam = st.date_input("Exam date", date.today()+timedelta(days=14), min_value=date.today())
        hours = st.slider("Study hours per day", 1, 12, 4)
        days = st.multiselect("Available days", ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
                              default=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"])
        pause = st.selectbox("Break between sessions (minutes)", [5,10,15,20], index=1)
        make = st.form_submit_button("✨ Generate timetable", type="primary", use_container_width=True)
    if make:
        if not st.session_state.subjects: st.error("Add subjects first.")
        elif not days: st.error("Select at least one available day.")
        else:
            st.session_state.plan = build_plan(st.session_state.subjects, exam, hours, days, pause)
            st.session_state.completed = set()
            if st.session_state.plan: st.success("Timetable generated!")
            else: st.warning("No sessions found. Check your exam date and selected days.")
    if st.session_state.plan:
        rows = [{"Date":p["date"].strftime("%d %b %Y"),"Subject":p["subject"],
                 "Duration":f'{p["minutes"]} min',"Task":p["task"],
                 "Status":"Completed" if p["id"] in st.session_state.completed else "Pending"}
                for p in st.session_state.plan]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("### Mark sessions complete")
        for p in st.session_state.plan:
            done = p["id"] in st.session_state.completed
            checked = st.checkbox(f'{p["date"].strftime("%d %b")} · {p["subject"]} · {p["minutes"]} min',
                                  value=done, key="check_"+p["id"])
            if checked and not done:
                award(p["id"]); st.rerun()
            elif not checked and done:
                st.session_state.completed.remove(p["id"])
                st.session_state.points = max(0, st.session_state.points-10)
                st.rerun()
        csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download timetable CSV", csv, "study_timetable.csv", "text/csv")

elif page == "Daily Tasks":
    st.subheader("✅ Daily Task Manager")
    with st.form("task_form", clear_on_submit=True):
        title = st.text_input("Task", placeholder="Complete Python loops")
        subject = st.text_input("Subject (optional)")
        due = st.date_input("Due date", date.today())
        add = st.form_submit_button("Add task")
    if add:
        if title.strip():
            st.session_state.task_no += 1
            st.session_state.tasks.append({"id":f"t{st.session_state.task_no}","title":title.strip(),
                                           "subject":subject.strip() or "General","due":due})
            st.success("Task added.")
        else: st.error("Enter a task.")
    for task in st.session_state.tasks:
        tid = task["id"]
        done = tid in st.session_state.completed
        checked = st.checkbox(f'{task["title"]} — {task["subject"]} — Due {task["due"].strftime("%d %b")}',
                              value=done, key="daily_"+tid)
        if checked and not done: award(tid); st.rerun()
        elif not checked and done:
            st.session_state.completed.remove(tid)
            st.session_state.points = max(0, st.session_state.points-10)
            st.rerun()

elif page == "Focus Room":
    st.subheader("⏱️ Focus Room — Pomodoro Timer")
    mode = st.radio("Timer mode", ["Focus 25 min","Short break 5 min","Long break 15 min"], horizontal=True)
    duration = {"Focus 25 min":25,"Short break 5 min":5,"Long break 15 min":15}[mode]*60
    if st.session_state.focus_running and st.session_state.focus_end:
        remaining = max(0, int(st.session_state.focus_end-time.time()))
    else: remaining = duration
    mm,ss = divmod(remaining,60)
    st.markdown(f"<h1 style='text-align:center;font-size:78px;color:#2457c5'>{mm:02d}:{ss:02d}</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    if c1.button("▶ Start / Resume", use_container_width=True):
        if not st.session_state.focus_running:
            st.session_state.focus_end = time.time()+remaining
            st.session_state.focus_running = True
            st.rerun()
    if c2.button("⏸ Pause", use_container_width=True):
        st.session_state.focus_running = False
        st.session_state.focus_end = None
        st.rerun()
    if c3.button("↻ Reset", use_container_width=True):
        st.session_state.focus_running = False
        st.session_state.focus_end = None
        st.rerun()
    if st.session_state.focus_running:
        if remaining <= 0:
            st.session_state.focus_running = False
            st.session_state.focus_end = None
            if mode == "Focus 25 min":
                st.session_state.focus_sessions += 1
                st.session_state.points += 15
            st.success("Timer finished! Take a break.")
            st.rerun()
        else:
            st.info("Timer is running. Click Refresh to update the countdown.")
            if st.button("🔄 Refresh timer"): st.rerun()
    st.metric("Completed focus sessions", st.session_state.focus_sessions)
    st.caption("Simple session-based timer. Refresh the timer display to see the latest countdown.")

elif page == "Analytics":
    st.subheader("📊 Performance Analytics")
    if st.session_state.plan:
        chart = pd.DataFrame(st.session_state.plan).groupby("subject")["minutes"].sum()
        st.markdown("### Planned study time by subject")
        st.bar_chart(chart)
    total = len(st.session_state.plan)+len(st.session_state.tasks)
    done = len(st.session_state.completed)
    a,b = st.columns(2)
    a.metric("⭐ Total points", st.session_state.points)
    b.metric("Completion rate", f"{done/total*100:.0f}%" if total else "0%")
    if st.session_state.points >= 100: st.success("🏆 Study Champion unlocked!")
    elif st.session_state.points >= 50: st.success("🥇 Focus Learner unlocked!")
    elif st.session_state.points >= 10: st.success("🌟 Getting Started achievement unlocked!")
    else: st.info("Complete tasks and focus sessions to unlock achievements.")

st.sidebar.divider()
st.sidebar.caption("Built with Python + Streamlit + Pandas")
st.sidebar.caption("Smart recommendations are rule-based; no external AI API is connected.")
