from flask import Flask, render_template_string, send_file, request
import requests
import pandas as pd
import io
from datetime import datetime
# from functools import lru_cache
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
# CORE DATA FUNCTION (NO LONGER CACHED)
# -----------------------------
# @lru_cache(maxsize=3)
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
        if "True"==fcOnly and s.get("sectCampCode") not in [ "2", "2NH" ]:
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
        s_instr = s.get("sectInstrName","")
        s_enrl = s.get("sectEnrlCutOffDate","12/31/2999") #proxy for start date
        s_drop = s.get("sectDropCutOffDate","01/01/2000") #proxy for end date
        

        
        meetings = s.get("sectMeetings", [])
#        if not meetings:
#            continue  # prevent crash
#        if 0==len(meetings):
#            continue
            
        s_mode = modeCodes.get(s_schd, "WTF?")
        if "Hybrid"==s_mode:
            if len(meetings) > 0:
                if "ONLINE"==meetings[0].get("bldgCode","WTF???"):
                    s_mode = "Online+Exams"

        s_xgrp  = ""
        s_xlst  = s.get("sectXlst", [])
        for x in s_xlst:
            s_xgrp += x.get("xlstGrp", "")
        
        s_rows = []
        s_topRow = {
            "Course": s_alias,
            "Title":  s_title,
            "CRN":    s_crn,
            "Row":    0,
            "Status":   "", # to be filled in from meetings-
            "Cred":   s_credlo,
            "CredHi": s_credhi,
            "Days":     "", # to be filled in from meetings-
            "Time":     "", # to be filled in from meetings-
            "Location": "", # to be filled in from meetings-
            "Cap":  s_cap,
            "Act":  s_act,
            "Rem":  s_rem,
            "Wait": s_wait,
            "WtCp": s_wcap,
            "Instructor": s_instr,
            "Start": s_enrl, # to be updated from meetings-
            "End": s_drop, # to be updated from meetings-
            "Weeks": "", # to be computed from Start/End-
            "Mode":  s_mode,
            "X-list": s_xgrp,
            "Cost":   s_cost,
            "Description": s_desc
        }

        m_row = 1
        for m in meetings:
            m_days = ''.join([m.get(day, '') for day in ["monDay","tueDay","wedDay","thuDay","friDay","satDay","sunDay"]])
            if m_row > 1:
                s_topRow["Days"] += "/"
            s_topRow["Days"] += m_days
                
            m_time = f"{m.get('beginTime','')} - {m.get('endTime','')}" if m.get('beginTime') else ""
            if m_row > 1:
                s_topRow["Time"] += "/"
            s_topRow["Time"] += m_time

            m_bldg = m.get('bldgDesc',"")
            m_room = m.get('roomCode',"")
            m_loc  = m_bldg + " " + m_room
            if "ZOOM ZOOM" == m_loc:
                m_loc = "ZOOM"
            elif "ONLINE ONLINE" == m_loc:
                m_loc = "ONLINE"
            if m_row > 1:
                s_topRow["Location"] += "/"
            s_topRow["Location"] += m_loc

            m_start  = m.get("startDate","")
            m_end    = m.get("endDate","")
            m_startx = datetime.strptime(m_start, "%m/%d/%Y")
            m_endx   = datetime.strptime(m_end, "%m/%d/%Y")
            m_delta = m_endx - m_startx
            m_wks   = int(round(m_delta.days / 7,0))

            if m_startx < datetime.strptime(s_topRow["Start"], "%m/%d/%Y"): 
                s_topRow["Start"] = m_start
            if m_endx > datetime.strptime(s_topRow["End"], "%m/%d/%Y"): 
                s_topRow["End"] = m_end
                                                        
            m_instr = m.get("meetInstrName", s_instr)

            s_rows.append({
                "Course": "",
                "Title":  "",
                "CRN":    s_crn,
                "Row":    m_row,
                "Status": "",
                "Cred":   "",
                "CredHi": "",
                "Days":   m_days,
                "Time":   m_time,
                "Location": m_loc,
                "Cap":  "",
                "Act":  "",
                "Rem":  "",
                "Wait": "",
                "WtCp": "",
                "Instructor": m_instr,
                "Start": m_start,
                "End":   m_end,
                "Weeks": m_wks,
                "Mode": "",
                "X-list": s_xgrp,
                "Cost": "",
                "Description": ""
            })

            m_row += 1

        s_start = s_topRow.get("Start","")
        s_end   = s_topRow.get("End","")        
        s_startx = datetime.strptime( s_start, "%m/%d/%Y")
        s_endx   = datetime.strptime( s_end, "%m/%d/%Y")
        s_delta = s_endx - s_startx
        s_wks   = int(round(s_delta.days / 7,0))

        if 0==len(meetings):
            s_status = "NO MEETINGS"
        elif s_endx < today:
            s_status = "Completed"
        elif s_startx <= today:
            s_status = "In Progress"
        elif s_rem > 0:
            s_status = "OPEN" if 0 == s_wait else "Waitlisted"
        else:
            s_status = "Waitlisted" if s_wait < s_wcap else "CLOSED"

        s_topRow["Weeks"] = s_wks
        s_topRow["Status"] = s_status
        
        rows.append(s_topRow)
        if len(s_rows) > 1:
            rows.extend(s_rows)
    
    return rows

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return '<h3>Go to <a href="/sections">/sections</a></h3>'

@app.route("/ping")
def ping():
    return "ok", 200
    
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
