from flask import Flask, render_template_string, send_file, request
import requests
import pandas as pd
import io
from datetime import datetime
from functools import lru_cache
import os

app = Flask(__name__)

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

        .controls {
            margin-bottom: 10px;
        }

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
            text-align: left;
            top: 0;
        }

        tr:nth-child(even) {
            background: #fafafa;
        }

        button {
            padding: 6px 10px;
            cursor: pointer;
        }
    </style>
</head>

<body>
    <h2>Actually readable class schedule that NOCCCD bastards removed ({{ count }} rows)</h2>

    <div class="controls">
        <form method="get" action="/sections" style="display:inline;">
            <label for="term">Term:</label>
            <select name="term" onchange="this.form.submit()">
                <option value="202520" {% if term == "202520" %}selected{% endif %}>Spring 2026</option>
                <option value="202530" {% if term == "202530" %}selected{% endif %}>Summer 2026</option>
                <option value="202610" {% if term == "202610" %}selected{% endif %}>Fall 2026</option>
            </select>
        
            <label for="mathOnly">Subjects:</label>
            <select name="mathOnly" onchange="this.form.submit()">
                <option value="True" {% if mathOnly == "True" %}selected{% endif %}>MATH/STAT</option>
                <option value="False" {% if mathOnly == "False" %}selected{% endif %}>ALL</option>
            </select>
        
            <label for="fcOnly">Schools:</label>
            <select name="fcOnly" onchange="this.form.submit()">
                <option value="True" {% if fcOnly == "True" %}selected{% endif %}>FC</option>
                <option value="False" {% if fcOnly == "False" %}selected{% endif %}>FC+CC</option>
            </select>
        </form>
        
        <a href="/download?term={{ term }}&mathOnly={{ mathOnly }}&fcOnly={{ fcOnly }}">
            <button>Download Excel</button>
        </a>
    </div>

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
@lru_cache(maxsize=3)
def get_processed_rows(term, mathOnly, fcOnly):
    today = datetime.today()

    # --- COURSES ---
    courses_url = f"https://schedule.nocccd.edu/data/{term}/courses.json?p=FuckYouAllForBreakingThis"
    courses = requests.get(courses_url).json()

    course_dict = {}
    for c in courses:
        c_subj  = c.get("crseSubjCode", "")
        c_name  = c_subj + " " + c.get("crseCrseNumb", "")
        c_alias = c_subj + " " + c.get("crseAlias", "")
        c_title = c.get("crseTitle","")
        c_tidx = c_title.find( "(formerly" )
        if 0 < c_tidx:
            c_title = c_title[:c_tidx]
        course_dict[c_name] = {
            "Alias": c_alias,
            "Title": c_title,
            "CredLo": c.get("crseCredHrLow",""),
            "CredHi": c.get("crseCredHrHigh","")
        }

    # --- SECTIONS ---
    sections_url = f"https://schedule.nocccd.edu/data/{term}/sections.json?p=FuckYouAllForBreakingThis"
    data = requests.get(sections_url).json()

    modeCodes = {
        "02":  "Campus",
        "04":  "Campus",    #"Lab",
        "04E": "Campus",    #"Lab",
        "72":  "Online",
        "72L": "Online",
        "HY":  "Hybrid",
        "71":  "Zoom",
        "20":  "Work Exp",
        "90":  "Work Exp",
        "40":  "Ind Study"
    }

    costCodes = ["LTCP", "NSTC", "NTC", "OER", "MOER", "NOER"]

    rows = []

    for s in data:
        if "True"==mathOnly and s.get("sectSubjCode") not in ["MATH", "STAT"]:
            continue
        if "True"==fcOnly and s.get("sectCampCode") != "2":
            continue

        meetings = s.get("sectMeetings", [])
        if not meetings:
            continue  # prevent crash
        if 0==len(meetings):
            continue

        attribs = s.get("sectAttr", [])
        s_cost = ""
        for a in attribs:
            a_code = a.get("attrCode", "")
            if a_code in costCodes:
                s_cost += a.get("attrDesc", "")

        s_crn = s.get("sectCrn","")
        s_name = f"{s.get('sectSubjCode','')} {s.get('sectCrseNumb','')}"

        if s_name not in course_dict:
            continue

        s_alias  =  course_dict[s_name]["Alias"]
        s_title  = course_dict[s_name]["Title"]
        s_credlo = course_dict[s_name]["CredLo"]
        s_credhi = course_dict[s_name]["CredHi"]

        s_cap  = s.get("sectMaxEnrl",0)
        s_act  = s.get("sectEnrl",0)
        s_rem  = s.get("sectSeatsAvail",0)
        s_wait = s.get("sectWaitCount",0)
        s_wcap = s.get("sectWaitCapacity",0)
        s_instr = s.get("sectInstrName","")
        s_schd  = s.get("sectSchdCode","")
#        s_insm  = s.get("sectInsmCode","")
        s_desc = s.get("sectLongText","")

        s_mode = modeCodes.get(s_schd, "WTF?")
        s_loc1 = meetings[0].get("bldgCode","WTF???")
        if "Hybrid"==s_mode:
            if "ONLINE"==s_loc1:
                s_mode = "Online+Exams"

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

        s_xgrp  = ""
        s_xlst  = s.get("sectXlst", [])
        for x in s_xlst:
            s_xgrp += x.get("xlstGrp", "")
        
        m_row = 1
        for m in meetings:
            m_days = ''.join([m.get(day, '') for day in ["monDay","tueDay","wedDay","thuDay","friDay","satDay"]])
            m_time = f"{m.get('beginTime','')} - {m.get('endTime','')}" if m.get('beginTime') else ""

            m_bldg = m.get('bldgDesc',"")
            m_room = m.get('roomCode',"")
            m_loc  = m_bldg + " " + m_room
            if "ZOOM ZOOM" == m_loc:
                m_loc = "ZOOM"
            elif "ONLINE ONLINE" == m_loc:
                m_loc = "ONLINE"

            m_start = m.get("startDate","")
            m_end   = m.get("endDate","")
            m_delta = datetime.strptime(m_end, "%m/%d/%Y") - datetime.strptime(m_start, "%m/%d/%Y")
            m_wks   = int(round(m_delta.days / 7,0))

            m_instr = m.get("meetInstrName", s_instr)

            rows.append({
                "Course": s_alias if m_row==1 else "",
                "Title":  s_title if m_row==1 else "",
                "CRN":    s_crn,
                "Row":    m_row,
                "Status": s_status if m_row==1 else "",
                "Cred":   s_credlo if m_row==1 else "",
                "CredHi": s_credhi if m_row==1 else "",
                "Days":   m_days,
                "Time":   m_time,
                "Location": m_loc,
                "Cap":  s_cap if m_row==1 else "",
                "Act":  s_act if m_row==1 else "",
                "Rem":  s_rem if m_row==1 else "",
                "Wait": s_wait if m_row==1 else "",
                "WtCp": s_wcap if m_row==1 else "",
                "Instructor": m_instr,
                "Dates": m_start+"-"+m_end,
                "Weeks": m_wks,
                "Mode":  s_mode if m_row==1 else "",
                "X-list": s_xgrp,
                "Cost":   s_cost if m_row==1 else "",
                "Description": s_desc if m_row==1 else ""
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
    term = request.args.get("term", "202610")
    mathOnly = request.args.get("mathOnly", "True")
    fcOnly = request.args.get("fcOnly", "True")

    rows = get_processed_rows(term, mathOnly, fcOnly)
    if 0==len(rows):
        return '<h3>Empty data set. Go to <a href="/sections">/sections</a></h3>'

    columns = rows[0].keys()

    return render_template_string(
        HTML_TEMPLATE,
        rows=rows,
        columns=columns,
        count=len(rows),
        term=term,
        mathOnly=mathOnly,
        fcOnly=fcOnly
    )

@app.route("/download")
def download():
    term = request.args.get("term", "202610")
    mathOnly = request.args.get("mathOnly", "True")
    fcOnly = request.args.get("fcOnly", "True")

    rows = get_processed_rows(term, mathOnly, fcOnly)
    df = pd.DataFrame(rows)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name=f"sections_{term}.xlsx",
        as_attachment=True
    )

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
