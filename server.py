from flask import Flask, render_template_string
import requests
#import pandas as pd
from datetime import date, datetime, timedelta


app = Flask(__name__)

TERM = "202610"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sections Table</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }

        h2 {
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
            text-align: left;
            white-space: nowrap;
        }

        th {
            background: #f4f4f4;
            position: sticky;
            top: 0;
            z-index: 2;
        }

        tr:nth-child(even) {
            background: #fafafa;
        }
    </style>
</head>

<body>
    <h2>FC MATH/STAT Sections, Fall 26 ({{ count }} rows)</h2>

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

@app.route("/")
def home():
    return '<h3>Go to <a href="/sections">/sections</a></h3>'

@app.route("/sections")
def sections():

    today = datetime.today()
    url     = f"https://schedule.nocccd.edu/data/{TERM}/courses.json?p=FuckYouAllForBreakingThis"
    courses = requests.get(url).json()      #array of structs, one for each COURSE

    course_dict = {}
    for c in courses:
        c_name  = f"{c['crseSubjCode']} {c['crseCrseNumb']}"
        c_alias = f"{c['crseSubjCode']} {c['crseAlias']}"
        course_dict[c_name] = {"Alias": c_alias, "Title": c["crseTitle"], "Credit": c["crseCredHrLow"]}

    rows = []

    url  = f"https://schedule.nocccd.edu/data/{TERM}/sections.json?p=FuckYouAllForBreakingThis"
    data = requests.get(url).json()      #array of structs, one for each SECTION

    for s in data:
        # Only include Fullerton College MATH/STAT courses
        if s.get("sectCampCode") != "2":  # 2 = Fullerton College
            continue
        if (s.get("sectSubjCode") != "MATH") and (s.get("sectSubjCode") != "STAT"):
            continue

        s_crn   = s.get("sectCrn","")
        s_name  = f"{s.get('sectSubjCode','')} {s.get('sectCrseNumb','')}"
#    if "STAT 120 F"==s_name:
#        s_name = "STAT C1000"
#    elif "STAT 120HF"==s_name:
#        s_name = "STAT C1000H"
#    elif "STAT 121 F"==s_name:
#        s_name = "STAT C1000E"

        s_alias = course_dict[s_name]["Alias"]
        s_title = course_dict[s_name]["Title"]
        s_cred  = course_dict[s_name]["Credit"]
        s_cap   = s.get("sectMaxEnrl",0)
        s_act   = s.get("sectEnrl",0)
        s_rem   = s.get("sectSeatsAvail",0)
        s_wait  = s.get("sectWaitCount",0)
        s_wcap  = s.get("sectWaitCapacity",0)
        s_instr = s.get("sectInstrName","")
        s_ssts  = s.get("sectSstsCode","")
        s_ptrm  = s.get("sectPtrmCode","")
        s_acct  = s.get("sectAcctCode","")
        s_schd  = s.get("sectSchdCode","")
        s_insm  = s.get("sectInsmCode","")

        meetings = s.get("sectMeetings", [])

        s_mode  = "Campus" if "02"==s_insm else "Online" if "72"==s_insm else "Tutoring" if "04"==s_insm else "Hybrid" if "HYA"==s_insm else "WTF?"

        s_loc1 = meetings[0].get("bldgCode","WTF???")

        if "WTF???"==s_loc1: print(s_crn)

        if "Hybrid"==s_mode:
            if "ONLINE"==s_loc1:
                s_mode = "Online+Exams"
        
#    if "22343"==s_crn: print("s_insm = ", s_insm, "02"==s_insm, 2==s_insm )
    
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

        # Loop through all meetings for this section
        m_row = 1
        for m in meetings:
            m_days = ''.join([m.get(day, '') for day in ["monDay","tueDay","wedDay","thuDay","friDay","satDay"]])
            m_time = f"{m.get('beginTime','')} - {m.get('endTime','')}" if m.get('beginTime') else ""
            m_room = f"{m.get('bldgDesc','')} {m.get('roomCode','')}" if m.get('bldgDesc') else ""
            m_start = m.get("startDate","")
            m_end = m.get("endDate","")
            m_delta = datetime.strptime(m_end, "%m/%d/%Y") - datetime.strptime(m_start, "%m/%d/%Y")
            m_numdays = m_delta.days
            m_wks = int(round(m_numdays / 7,0))
            m_instr = m.get("meetInstrName", s_instr)

            m_info = { "Course": s_alias+" - "+s_title if 1==m_row else "",
                "Status": s_status if 1==m_row else "",            
                "CRN": s_crn,
                "Z/Row": m_row,
#            "Title": s_title if 1==m_row else "",
#            "Z": "",
                "Cred": s_cred if 1==m_row else "",
                "M/Days": m_days,
                "T": "",
                "W": "",
                "R": "",
                "F": "",
                "S": "",
                "Su": "",
                "Time": m_time,
                "Loc": m_room,
                "Cap": s_cap if 1==m_row else "",
                "Act": s_act if 1==m_row else "",
                "Rem": s_rem if 1==m_row else "",
                "Wait": s_wait if 1==m_row else "",
#            "WtCp": s_wcap if 1==m_row else "",
                "Instr": m_instr,
                "Date": m_start+"-"+m_end,
#            "Start": m_start,
#            "End": m_end,
                "Weeks": m_wks,
                "Mode": s_mode if 1==m_row else ""
#            "Type": m.get("mtypDesc",""),
#            "Sched": m.get("schdDesc",""),
#            "Ssts": s_ssts if 1==m_row else "",
#            "Ptrm": s_ptrm if 1==m_row else "",
#            "Acct": s_acct if 1==m_row else "",
#            "Schd": s_schd if 1==m_row else "",
#            "Insm": s_insm if 1==m_row else ""
            }

            rows.append(m_info)

            m_row += 1

    columns = rows[0].keys()
#    columns = sorted({k for row in rows for k in row.keys()})

    return render_template_string(
        HTML_TEMPLATE,
        rows=rows,
        columns=columns,
        count=len(rows)
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
