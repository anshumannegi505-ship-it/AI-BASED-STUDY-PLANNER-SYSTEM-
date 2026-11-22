"""AI Study Planner Pro - Streamlit + SQLite + pandas + Plotly
Run:  pip install streamlit pandas plotly   (optional: anthropic)
      streamlit run app.py
"""
import os
import sqlite3
import time
from datetime import date, timedelta

import streamlit as st

try:
    import pandas as pd
    import plotly.express as px
except ModuleNotFoundError as e:
    st.error(f"Missing library: {e.name}. Add it to requirements.txt (streamlit, pandas, plotly) and reboot the app.")
    st.stop()

def _db_path():
    base = os.path.dirname(os.path.abspath(__file__))
    for folder in (base, "/tmp"):
        try:
            p = os.path.join(folder, "study_planner.db")
            sqlite3.connect(p).close()
            return p
        except Exception:
            continue
    return ":memory:"


DB = _db_path()
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
                                 title="Where to focus (priority share)"))
    if not sess.empty:
        daily = sess.groupby("day", as_index=False)["minutes"].sum()
        right.plotly_chart(px.bar(daily, x="day", y="minutes", title="Daily study minutes"),
                           )
        by_sub = sess.groupby("subject", as_index=False)["minutes"].sum()
        st.plotly_chart(px.bar(by_sub, x="subject", y="minutes", color="subject",
                               title="Time per subject"))
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
        st.dataframe(subjects.drop(columns="id"))
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
            checked = c[0].checkbox("done", bool(t["done"]), key=f"d{t['id']}", label_visibility="collapsed")
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
                        )
        st.dataframe(plan.pivot_table(index="Date", columns="Subject", values="Hours", fill_value=0),
                     )
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
