# app.py
from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
import psycopg2.extras # IMPORT THIS FOR DICTCURSOR
from config import db_config
import datetime
import os

app = Flask(__name__)
app.secret_key = 'landbank_secret_key'

def get_db_connection():
    try:
        print(f"Attempting to connect to PostgreSQL with: host={db_config['host']} port={db_config['port']} dbname={db_config['database']} user={db_config['user']}")
        return psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
    except psycopg2.Error as err:
        print(f"Error connecting to PostgreSQL database: {err}")
        raise

# Function to execute SQL from a file
def execute_sql_file(filepath):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # Default cursor is fine for DDL (CREATE TABLE)
        with open(filepath, 'r') as f:
            sql_script = f.read()
            statements = [s.strip() for s in sql_script.split(';') if s.strip()]
            for statement in statements:
                try:
                    # As discussed, 'CREATE DATABASE' and 'USE' are not for Render managed PG
                    if statement.upper().startswith("CREATE DATABASE") or statement.upper().startswith("USE "):
                        print(f"Skipping: '{statement}' (Not applicable for Render PostgreSQL)")
                        continue

                    cursor.execute(statement)
                except psycopg2.Error as err:
                    print(f"Error executing statement: {statement}\nError: {err}")
                    # You might want more sophisticated error handling here,
                    # e.g., if a table already exists and IF NOT EXISTS isn't used,
                    # it will error. But for initial setup, this is okay.
        conn.commit()
        print(f"Successfully executed SQL from {filepath}")
        return True
    except psycopg2.Error as err:
        print(f"Error during SQL file execution: {err}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

@app.route('/setup_database')
def setup_database():
    if app.debug:
        sql_filepath = 'landbank.sql'
        if os.path.exists(sql_filepath):
            print(f"Attempting to run database setup from {sql_filepath}")
            if execute_sql_file(sql_filepath):
                flash("Database setup completed successfully!", "success")
            else:
                flash("Database setup failed. Check server logs.", "error")
        else:
            flash(f"SQL file '{sql_filepath}' not found.", "error")
        return redirect('/')
    else:
        flash("Database setup not allowed in production mode.", "error")
        return redirect('/')

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
    # Use DictCursor for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE
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
    # Use DictCursor for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE
    cursor.execute("SELECT cust_no, custname, email_address FROM Customer")
    customers = cursor.fetchall()
    conn.close()

    total_customers = session.get('total_customers', 'N/A')
    return render_template('admin_dashboard.html', customers=customers, total_customers=total_customers)

@app.route('/admin/view/<cust_no>')
def admin_view_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')
    conn = get_db_connection()
    # Use DictCursor for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE

    cursor.execute("""
        SELECT c.*, s.name AS spouse_name, s.birthdate AS spouse_birthdate, s.profession AS spouse_profession
        FROM Customer c
        LEFT JOIN Spouse s ON c.spouse_code = s.spouse_code
        WHERE c.cust_no = %s
    """, (cust_no,))
    customer = cursor.fetchone()
    conn.close()
    return render_template('admin_view_customer.html', customer=customer)

@app.route('/admin/edit/<cust_no>', methods=['GET', 'POST'])
def admin_edit_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')

    conn = get_db_connection()
    # Use DictCursor for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE

    if request.method == 'POST':
        data = request.form
        cursor.execute("SELECT * FROM Customer WHERE cust_no = %s", (cust_no,))
        original = cursor.fetchone()

        # Update customer table
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

        # Handle Spouse details update (if spouse_code exists)
        if 'spouse_code' in original and original['spouse_code']:
            cursor.execute("""
                UPDATE Spouse SET
                    name=%s, birthdate=%s, profession=%s
                WHERE spouse_code=%s
            """, (data.get('spouse_name'), data.get('spouse_birthdate'), data.get('spouse_profession'), original['spouse_code']))
        elif data.get('spouse_name'):
            cursor.execute("INSERT INTO SpouseCode DEFAULT VALUES RETURNING spouse_code") # PostgreSQL specific for SERIAL primary key
            new_spouse_code = cursor.fetchone()[0] # Get the returned ID
            cursor.execute("""
                INSERT INTO Spouse (spouse_code, name, birthdate, profession)
                VALUES (%s, %s, %s, %s)
            """, (new_spouse_code, data.get('spouse_name'), data.get('spouse_birthdate'), data.get('spouse_profession')))
            cursor.execute("UPDATE Customer SET spouse_code = %s WHERE cust_no = %s", (new_spouse_code, cust_no))

        updated_fields = []
        for field in ['custname', 'datebirth', 'nationality', 'citizenship', 'custsex', 'placebirth',
                      'civilstatus', 'num_children', 'mmaiden_name', 'cust_address', 'email_address', 'contact_no']:
            old_value = original.get(field) # Use .get() for safety
            new_value = data[field]
            if str(old_value) != new_value:
                updated_fields.append(f"{field}: '{old_value}' -> '{new_value}'")

        with open("admin_logs.txt", "a") as log:
            log.write(f"[{datetime.datetime.now()}] ADMIN UPDATED: {cust_no}\n")
            for change in updated_fields:
                log.write(f"  - {change}\n")

        conn.commit()
        conn.close()
        flash("Customer record updated successfully!", "success")
        return redirect('/admin_dashboard')

    # GET request
    cursor.execute("""
        SELECT c.*, s.name AS spouse_name, s.birthdate AS spouse_birthdate, s.profession AS spouse_profession
        FROM Customer c
        LEFT JOIN Spouse s ON c.spouse_code = s.spouse_code
        WHERE c.cust_no = %s
    """, (cust_no,))
    customer = cursor.fetchone()
    conn.close()
    return render_template('admin_edit_customer.html', customer=customer)


@app.route('/admin/delete/<cust_no>', methods=['POST'])
def admin_delete_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor() # Default cursor is fine here

    cursor.execute("SELECT spouse_code FROM Customer WHERE cust_no = %s", (cust_no,))
    spouse_code_to_delete = cursor.fetchone()
    if spouse_code_to_delete:
        spouse_code_to_delete = spouse_code_to_delete[0]

    cursor.execute("DELETE FROM Customer WHERE cust_no = %s", (cust_no,))

    if spouse_code_to_delete:
        cursor.execute("DELETE FROM Spouse WHERE spouse_code = %s", (spouse_code_to_delete,))
        cursor.execute("DELETE FROM SpouseCode WHERE spouse_code = %s", (spouse_code_to_delete,))

    conn.commit()

    with open("admin_logs.txt", "a") as log:
        log.write(f"[{datetime.datetime.now()}] ADMIN DELETED: {cust_no}\n")
        if spouse_code_to_delete:
            log.write(f"  - Also deleted associated Spouse and SpouseCode with ID: {spouse_code_to_delete}\n")

    conn.close()
    flash(f"Customer {cust_no} and related records deleted successfully!", "success")
    return redirect('/admin_dashboard')

@app.route('/compute_customers', methods=['POST'])
def compute_customers():
    if 'admin' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor() # Default cursor is fine here
    cursor.execute("SELECT COUNT(*) AS total FROM Customer")
    total = cursor.fetchone()[0]
    conn.close()

    session['total_customers'] = total
    flash(f"Total customers computed: {total}", "info")
    return redirect('/admin_dashboard')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect('/')

@app.route('/customers')
def customer_list():
    conn = get_db_connection()
    # Use DictCursor for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE
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
    # Use DictCursor for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE

    cursor.execute("""
        SELECT c.*, s.name AS spouse_name, s.birthdate AS spouse_birthdate, s.profession AS spouse_profession
        FROM Customer c
        LEFT JOIN Spouse s ON c.spouse_code = s.spouse_code
        WHERE c.custname = %s
    """, (session['user'],))
    customer = cursor.fetchone()
    conn.close()
    if not customer:
        flash("Your record was not found.", "error")
        return redirect('/home')
    return render_template('my_record.html', customer=customer)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.form
    conn = None
    try:
        conn = get_db_connection()
        # Use DictCursor for dictionary-like results for 'existing' check
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # CHANGE THIS LINE

        cursor.execute("SELECT * FROM Customer WHERE cust_no = %s OR email_address = %s", (data['cust_no'], data['email_address']))
        existing = cursor.fetchone()

        if existing:
            flash("Customer number or email address already exists!", "error")
            return redirect('/openAcc')

        spouse_code = None
        occ_id = None
        fin_code = None

        if data.get('spouse_name'):
            # For SERIAL primary keys in PostgreSQL, you use RETURNING
            cursor.execute("INSERT INTO SpouseCode DEFAULT VALUES RETURNING spouse_code")
            spouse_code = cursor.fetchone()[0] # Get the returned ID
            cursor.execute("""
                INSERT INTO Spouse (spouse_code, name, birthdate, profession)
                VALUES (%s, %s, %s, %s)
            """, (spouse_code, data['spouse_name'], data['spouse_birthdate'], data['spouse_profession']))

        cursor.execute("INSERT INTO Occupation DEFAULT VALUES RETURNING occ_id") # PostgreSQL specific
        occ_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO FinancialRecord DEFAULT VALUES RETURNING fin_code") # PostgreSQL specific
        fin_code = cursor.fetchone()[0]

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
        flash("Customer successfully registered!", "success")
        return redirect('/')
    except psycopg2.Error as err: # CHANGE THIS to psycopg2.Error
        flash(f"Database error: {err}", "error")
        if conn:
            conn.rollback()
        return redirect('/openAcc')
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
