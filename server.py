from flask import Flask, render_template_string, send_file
import requests
import pandas as pd
import io
from datetime import datetime
from functools import lru_cache

app = Flask(__name__)

TERM = "202610"

# -----------------------------
# HTML TEMPLATE
# -----------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sections Table</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        h2 { margin-bottom: 10px; }

        .table-container {
            max-height: 80vh;
            overflow: auto;
            border: 1px solid #ccc;
        }

        table {
            border-collapse: collapse;
            width: 100%;
            font-size: 13px;
        }

        th, td {
            border: 1px solid #ddd;
            padding: 6px;
            white-space: nowrap;
        }

        th {
            background: #f4f4f4;
            position: sticky;
            top: 0;
        }

        tr:nth-child(even) {
            background: #fafafa;
        }

        button {
            margin-bottom: 10px;
            padding: 8px 12px;
            cursor: pointer;
        }
    </style>
</head>

<body>
    <h2>FC MATH/STAT Sections, Fall 26 ({{ count }} rows)</h2>

    <a href="/download">
        <button>Download Excel</button>
    </a>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    {% for col in columns %}
                    <th>{{ col }}</th>
                    {% endfor %}
                </tr>
            </thead>

            <tbody>
                {% for row in rows %}
                <tr>
                    {% for col in columns %}
                    <td>{{ row.get(col, "") }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

# -----------------------------
# CORE DATA FUNCTION (CACHED)
# -----------------------------
@lru_cache(maxsize=1)
def get_processed_rows():
    today = datetime.today()

    # --- COURSES ---
    url = f"https://schedule.nocccd.edu/data/{TERM}/courses.json?p=FuckYouAllForBreakingThis"
    courses = requests.get(url).json()

    course_dict = {}
    for c in courses:
        c_name  = f"{c['crseSubjCode']} {c['crseCrseNumb']}"
        c_alias = f"{c['crseSubjCode']} {c['crseAlias']}"
        course_dict[c_name] = {
            "Alias": c_alias,
            "Title": c["crseTitle"],
            "Credit": c["crseCredHrLow"]
        }

    # --- SECTIONS ---
    url = f"https://schedule.nocccd.edu/data/{TERM}/sections.json?p=FuckYouAllForBreakingThis"
    data = requests.get(url).json()

    rows = []

    for s in data:
        if s.get("sectCampCode") != "2":
            continue
        if s.get("sectSubjCode") not in ["MATH", "STAT"]:
            continue

        s_crn = s.get("sectCrn","")
        s_name = f"{s.get('sectSubjCode','')} {s.get('sectCrseNumb','')}"

        if s_name not in course_dict:
            continue

        s_alias = course_dict[s_name]["Alias"]
        s_title = course_dict[s_name]["Title"]
        s_cred  = course_dict[s_name]["Credit"]

        s_cap  = s.get("sectMaxEnrl",0)
        s_act  = s.get("sectEnrl",0)
        s_rem  = s.get("sectSeatsAvail",0)
        s_wait = s.get("sectWaitCount",0)
        s_wcap = s.get("sectWaitCapacity",0)
        s_instr = s.get("sectInstrName","")
        s_insm  = s.get("sectInsmCode","")

        meetings = s.get("sectMeetings", [])

        s_mode = (
            "Campus" if s_insm=="02" else
            "Online" if s_insm=="72" else
            "Tutoring" if s_insm=="04" else
            "Hybrid" if s_insm=="HYA" else
            "WTF?"
        )

        s_start = datetime.strptime(meetings[0]["startDate"], "%m/%d/%Y")
        s_end   = datetime.strptime(meetings[0]["endDate"], "%m/%d/%Y")

        if s_end < today:
            s_status = "Completed"
        elif s_start <= today:
            s_status = "In Progress"
        elif s_rem > 0:
            s_status = "OPEN"
        elif s_wcap > s_wait:
            s_status = "Waitlisted"
        else:
            s_status = "CLOSED"

        m_row = 1
        for m in meetings:
            m_days = ''.join([m.get(day, '') for day in ["monDay","tueDay","wedDay","thuDay","friDay","satDay"]])
            m_time = f"{m.get('beginTime','')} - {m.get('endTime','')}" if m.get('beginTime') else ""
            m_room = f"{m.get('bldgDesc','')} {m.get('roomCode','')}" if m.get('bldgDesc') else ""

            m_start = m.get("startDate","")
            m_end   = m.get("endDate","")
            m_delta = datetime.strptime(m_end, "%m/%d/%Y") - datetime.strptime(m_start, "%m/%d/%Y")
            m_wks   = int(round(m_delta.days / 7,0))

            m_instr = m.get("meetInstrName", s_instr)

            rows.append({
                "Course": s_alias+" - "+s_title if m_row==1 else "",
                "Status": s_status if m_row==1 else "",
                "CRN": s_crn,
                "Z/Row": m_row,
                "Cred": s_cred if m_row==1 else "",
                "M/Days": m_days,
                "Time": m_time,
                "Loc": m_room,
                "Cap": s_cap if m_row==1 else "",
                "Act": s_act if m_row==1 else "",
                "Rem": s_rem if m_row==1 else "",
                "Wait": s_wait if m_row==1 else "",
                "Instr": m_instr,
                "Date": m_start+"-"+m_end,
                "Weeks": m_wks,
                "Mode": s_mode if m_row==1 else ""
            })

            m_row += 1

    return rows

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return '<h3>Go to <a href="/sections">/sections</a></h3>'

@app.route("/sections")
def sections():
    rows = get_processed_rows()
    columns = rows[0].keys()

    return render_template_string(
        HTML_TEMPLATE,
        rows=rows,
        columns=columns,
        count=len(rows)
    )

@app.route("/download")
def download():
    rows = get_processed_rows()

    df = pd.DataFrame(rows)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name="sections.xlsx",
        as_attachment=True
    )

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
