# app.py
from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from config import db_config
import datetime

app = Flask(__name__)
app.secret_key = 'landbank_secret_key'

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def landingPage():
    return render_template('landingPage.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    if email == 'landbankADMIN@gmail.com' and password == 'LandBank2025':
        session['admin'] = True
        return redirect('/admin_dashboard')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer WHERE email_address = %s AND cust_no = %s", (email, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user'] = user['custname']
        return redirect('/home')
    else:
        flash('Invalid login credentials')
        return redirect('/')

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/')
    return render_template('home.html', user=session['user'])

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT cust_no, custname, email_address FROM Customer")
    customers = cursor.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', customers=customers)

@app.route('/admin/view/<cust_no>')
def admin_view_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer WHERE cust_no = %s", (cust_no,))
    customer = cursor.fetchone()
    conn.close()
    return render_template('admin_view_customer.html', customer=customer)

@app.route('/admin/edit/<cust_no>', methods=['GET', 'POST'])
def admin_edit_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        data = request.form
        cursor.execute("SELECT * FROM Customer WHERE cust_no = %s", (cust_no,))
        original = cursor.fetchone()

        cursor.execute("""
            UPDATE Customer SET
                custname=%s, datebirth=%s, nationality=%s, citizenship=%s,
                custsex=%s, placebirth=%s, civilstatus=%s, num_children=%s,
                mmaiden_name=%s, cust_address=%s, email_address=%s, contact_no=%s
            WHERE cust_no=%s
        """, (
            data['custname'], data['datebirth'], data['nationality'], data['citizenship'],
            data['custsex'], data['placebirth'], data['civilstatus'], data['num_children'],
            data['mmaiden_name'], data['cust_address'], data['email_address'], data['contact_no'],
            cust_no
        ))

        updated_fields = []
        for field in ['custname', 'datebirth', 'nationality', 'citizenship', 'custsex', 'placebirth',
                      'civilstatus', 'num_children', 'mmaiden_name', 'cust_address', 'email_address', 'contact_no']:
            old_value = original[field]
            new_value = data[field]
            if str(old_value) != new_value:
                updated_fields.append(f"{field}: '{old_value}' -> '{new_value}'")

        with open("admin_logs.txt", "a") as log:
            log.write(f"[{datetime.datetime.now()}] ADMIN UPDATED: {cust_no}\n")
            for change in updated_fields:
                log.write(f"  - {change}\n")

        conn.commit()
        conn.close()
        return redirect('/admin_dashboard')

    cursor.execute("SELECT * FROM Customer WHERE cust_no = %s", (cust_no,))
    customer = cursor.fetchone()
    conn.close()
    return render_template('admin_edit_customer.html', customer=customer)

@app.route('/admin/delete/<cust_no>', methods=['POST'])
def admin_delete_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Customer WHERE cust_no = %s", (cust_no,))
    conn.commit()

    with open("admin_logs.txt", "a") as log:
        log.write(f"[{datetime.datetime.now()}] ADMIN DELETED: {cust_no}\n")

    conn.close()
    return redirect('/admin_dashboard')

@app.route('/compute_customers', methods=['POST'])
def compute_customers():
    if 'admin' not in session:
        return redirect('/')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM Customer")
    total = cursor.fetchone()[0]
    conn.close()

    # Store the total in session
    session['total_customers'] = total
    return redirect('/admin_dashboard')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/customers')
def customer_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer")
    customers = cursor.fetchall()
    conn.close()
    return render_template('customer_list.html', customers=customers)

@app.route('/openAcc')
def openAcc():
    return render_template('openAcc.html')

@app.route('/my_record')
def my_record():
    if 'user' not in session:
        return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer WHERE custname = %s", (session['user'],))
    customer = cursor.fetchone()
    conn.close()
    return render_template('my_record.html', customer=customer)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.form
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check for duplicate Customer No or Email
    cursor.execute("SELECT * FROM Customer WHERE cust_no = %s OR email_address = %s", (data['cust_no'], data['email_address']))
    existing = cursor.fetchone()

    if existing:
        flash("Customer number or email address already exists!", "error")
        conn.close()
        return redirect('/openAcc')

    # Continue with insert if no duplicates
    cursor.execute("INSERT INTO SpouseCode () VALUES ()")
    spouse_code = cursor.lastrowid

    cursor.execute("INSERT INTO Occupation () VALUES ()")
    occ_id = cursor.lastrowid

    cursor.execute("INSERT INTO FinancialRecord () VALUES ()")
    fin_code = cursor.lastrowid

    cursor.execute("""
        INSERT INTO Customer (
            cust_no, custname, datebirth, nationality, citizenship,
            custsex, placebirth, civilstatus, num_children, mmaiden_name,
            cust_address, email_address, contact_no,
            spouse_code, occ_id, fin_code
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['cust_no'], data['custname'], data['datebirth'], data['nationality'], data['citizenship'],
        data['custsex'], data['placebirth'], data['civilstatus'], data['num_children'], data['mmaiden_name'],
        data['cust_address'], data['email_address'], data['contact_no'],
        spouse_code, occ_id, fin_code
    ))

    conn.commit()
    conn.close()
    flash("Customer successfully registered!", "success")
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
