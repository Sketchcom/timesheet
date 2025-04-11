import streamlit as st
import mysql.connector
from fpdf import FPDF
import os
from datetime import datetime, timedelta, date

# MySQL Connection
def get_connection():
    return mysql.connector.connect(
        host="sg2plzcpnl490951.prod.sin2.secureserver.net",
        user="it",
        password="sketch@1234",
        database="Progress_report_calculation"
    )

# Initialize DB and Tables
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            password VARCHAR(50)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id INT,
            date DATE,
            punch_in DATETIME,
            punch_out DATETIME,
            man_hours FLOAT,
            UNIQUE (employee_id, date)
        )
    """)
    conn.commit()
    conn.close()

# Authenticate user
def login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM employees WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

# Register user
def register(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO employees (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
    except mysql.connector.IntegrityError:
        conn.close()
        return False
    conn.close()
    return True

# Punch In
def punch_in(emp_id):
    conn = get_connection()
    cursor = conn.cursor()
    today = date.today()
    now = datetime.now()
    try:
        cursor.execute("INSERT INTO attendance (employee_id, date, punch_in) VALUES (%s, %s, %s)",
                       (emp_id, today, now))
        conn.commit()
        return "Punched in at " + now.strftime("%H:%M:%S")
    except mysql.connector.IntegrityError:
        return "Already punched in today."
    finally:
        conn.close()

# Punch Out
def punch_out(emp_id):
    conn = get_connection()
    cursor = conn.cursor()
    today = date.today()
    now = datetime.now()

    cursor.execute("SELECT punch_in FROM attendance WHERE employee_id=%s AND date=%s", (emp_id, today))
    row = cursor.fetchone()
    if row and row[0]:
        punch_in_time = row[0]
        man_hours = round((now - punch_in_time).total_seconds() / 3600, 2)
        cursor.execute("UPDATE attendance SET punch_out=%s, man_hours=%s WHERE employee_id=%s AND date=%s",
                       (now, man_hours, emp_id, today))
        conn.commit()
        conn.close()
        return f"Punched out at {now.strftime('%H:%M:%S')} | Man-hours: {man_hours}"
    else:
        conn.close()
        return "Punch in first before punching out."

# Fetch timesheet
def fetch_timesheet(emp_id, month, year):
    conn = get_connection()
    cursor = conn.cursor()
    start_date = date(year, month, 1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    cursor.execute("""
        SELECT date, punch_in, punch_out, man_hours
        FROM attendance
        WHERE employee_id=%s AND date BETWEEN %s AND %s
        ORDER BY date
    """, (emp_id, start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Generate PDF
def format_date(date):
    return f"{date.strftime('%d %b %Y')}"
def generate_pdf(username, data, month, year):
    from fpdf import FPDF
    import pandas as pd
    import os

    # Ensure 'data' is a DataFrame
    if not isinstance(data, pd.DataFrame):
        raise ValueError("The 'data' parameter must be a pandas DataFrame.")

    # Ensure the 'date' column is in datetime format
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date'], errors='coerce')
    else:
        raise ValueError("The 'data' DataFrame must contain a 'date' column.")

    # Sort the data by the 'date' column
    data = data.sort_values(by='date', ascending=True).reset_index(drop=True)

    # Custom PDF class with header
    class PDF(FPDF):
        def __init__(self, username, month, year, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.username = username
            self.month = month
            self.year = year

        def header(self):
                self.set_y(4)
                self.set_fill_color(12, 12, 62)
                self.set_font("Arial", "B", 14)
                self.set_text_color(255, 255, 255)
                self.cell(0, 6, ("SKETCHCOM ENGINEERING & DESIGN PRIVATE LIMITED"), ln=True, align="C", fill=1)
                self.set_font("Arial", "B", 12)
                import calendar
                month_name = calendar.month_abbr[self.month]
                self.cell(0, 10, f"Timesheet Report - {self.username} - {month_name}-{self.year}", ln=True, align="C", fill=1)
                self.set_font("Arial", "B", 10)
                self.set_text_color(255, 255, 255)
                self.cell(0, 6, (f"Client Name:  L&T Energy Hydrocarbon (LTEH), Offshore, Mumbai, Maharashtra"), ln=True, fill=1)
                self.set_text_color(240, 240, 240)
                self.set_font("Arial", "IB", 8)
                self.cell(0, 4, (f"PO Number: 7200072525"), ln=True, align="L", fill=1)
                self.cell(0, 4,(f"Project Name: AVEVA E3D Modelling"), ln=True, align="L", fill=1)
                logo_path = "logo/sketch.png"
                self.image(logo_path, 11, 5, 15)

                self.ln(5)
    # Initialize the PDF
    pdf = PDF(username, month, year)
    pdf.add_page()

    # Add table headers
    pdf.set_fill_color(122, 121, 123)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "Date", 1, align="C", fill=1)
    pdf.cell(55, 10, "Punch In", 1,   align="C", fill=1)
    pdf.cell(55, 10, "Punch Out", 1,  align="C", fill=1)
    pdf.cell(40, 10, "Man Hours", 1, align="C", fill=1)
    pdf.ln()

    # Add table rows
    total_hours = 0
    pdf.set_font("Arial", '', 12)
    for _, row in data.iterrows():
        d = row['date']
        pin = row['punch_in']
        pout = row['punch_out']
        hrs = row['man_hours']

        pdf.cell(40, 7, format_date(d) if pd.notnull(d) else "-", 1, align="C")
        pdf.cell(55, 7, pin.strftime('%H:%M:%S') if pd.notnull(pin) else "-", 1, align="C")
        pdf.cell(55, 7, pout.strftime('%H:%M:%S') if pd.notnull(pout) else "-", 1, align="C")
        pdf.cell(40, 7, f"{hrs:.2f}" if pd.notnull(hrs) else "-", 1, align="C")
        pdf.ln()

        if pd.notnull(hrs):
            total_hours += hrs

    # Add total hours
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(12, 50, 13)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, f"Total Man Hours: {total_hours:.2f}", ln=True, align='C', fill=1)

    # Ensure the directory exists
    directory = os.path.join("employee_timesheets", username)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Generate a unique filename
    filename = os.path.join(directory, f"{username}_{month}_{year}.pdf")
    pdf.output(filename)
    return filename
# -------------------- Streamlit UI --------------------

st.set_page_config(page_title="Attendance Tracker", layout="centered")
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = ""

st.title("🕒 Employee Attendance Tracker")

# Login or Register
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔐 Login", "🆕 Register"])
    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user_id = login(username, password)
            if user_id:
                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.username = username
                st.success("Logged in successfully!")
            else:
                st.error("Invalid credentials!")

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Register"):
            if register(new_user, new_pass):
                st.success("User registered! Now log in.")
            else:
                st.error("Username already exists!")

else:
    st.success(f"Welcome, {st.session_state.username} 👋")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("☀️ Punch In"):
            msg = punch_in(st.session_state.user_id)
            st.info(msg)

    with col2:
        if st.button("🌙 Punch Out"):
            msg = punch_out(st.session_state.user_id)
            st.info(msg)

    st.divider()
    st.subheader("📅 Monthly Timesheet")
    today = datetime.today()
    month = st.selectbox("Select Month", range(1, 13), index=today.month - 1)
    year = st.selectbox("Select Year", range(2023, today.year + 1), index=1)

    if st.button("📤 Generate Timesheet PDF"):
        timesheet = fetch_timesheet(st.session_state.user_id, month, year)
        if timesheet:
            # Convert the timesheet to a pandas DataFrame
            import pandas as pd
            timesheet_df = pd.DataFrame(timesheet, columns=["date", "punch_in", "punch_out", "man_hours"])
            
            # Generate the PDF
            pdf_file = generate_pdf(st.session_state.username, timesheet_df, month, year)
            with open(pdf_file, "rb") as f:
                st.download_button("📥 Download PDF", data=f, file_name=os.path.basename(pdf_file))
        else:
            st.warning("No attendance data available for the selected month.")

    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = ""
        st.rerun()
