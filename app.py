# app.py
from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from config import db_config
import datetime
import os # Import os for file path checking

app = Flask(__name__)
app.secret_key = 'landbank_secret_key'

# app.py
def get_db_connection():
    try:
        print(f"Attempting to connect with db_config: {db_config['host']}:{db_config['port']}/{db_config['database']} (user: {db_config['user']})")
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        raise

# Function to execute SQL from a file
def execute_sql_file(filepath):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        with open(filepath, 'r') as f:
            sql_script = f.read()
            # Split by semicolon to execute multiple statements
            statements = [s.strip() for s in sql_script.split(';') if s.strip()]
            for statement in statements:
                try:
                    cursor.execute(statement)
                except mysql.connector.Error as err:
                    # Print error for specific statement but continue if possible
                    print(f"Error executing statement: {statement}\nError: {err}")
                    # Decide if you want to stop on first error or try to continue
                    # For CREATE TABLE, you might want to continue, but for other DDL/DML, stop.
                    # For this setup, we'll continue for robustness with IF NOT EXISTS.
        conn.commit()
        print(f"Successfully executed SQL from {filepath}")
        return True
    except mysql.connector.Error as err:
        print(f"Error during SQL file execution: {err}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

@app.route('/setup_database')
def setup_database():
    # This route is intended for initial setup or development.
    # It should be protected in a production environment.
    if app.debug: # Only allow in debug mode for safety
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
    cursor = conn.cursor(dictionary=True)
    # The original query used cust_no for password. Assuming cust_no is the password for non-admin users.
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
    
    # Retrieve total customers from session if computed
    total_customers = session.get('total_customers', 'N/A')
    return render_template('admin_dashboard.html', customers=customers, total_customers=total_customers)

@app.route('/admin/view/<cust_no>')
def admin_view_customer(cust_no):
    if 'admin' not in session:
        return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Joining with Spouse table to get spouse details
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
    cursor = conn.cursor(dictionary=True)

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
        elif data.get('spouse_name'): # If spouse data is provided but no spouse_code linked yet
            # Create a new SpouseCode entry and then a Spouse record
            cursor.execute("INSERT INTO SpouseCode () VALUES ()")
            new_spouse_code = cursor.lastrowid
            cursor.execute("""
                INSERT INTO Spouse (spouse_code, name, birthdate, profession)
                VALUES (%s, %s, %s, %s)
            """, (new_spouse_code, data.get('spouse_name'), data.get('spouse_birthdate'), data.get('spouse_profession')))
            # Link the new spouse_code to the customer
            cursor.execute("UPDATE Customer SET spouse_code = %s WHERE cust_no = %s", (new_spouse_code, cust_no))


        updated_fields = []
        for field in ['custname', 'datebirth', 'nationality', 'citizenship', 'custsex', 'placebirth',
                      'civilstatus', 'num_children', 'mmaiden_name', 'cust_address', 'email_address', 'contact_no']:
            old_value = original[field]
            new_value = data[field]
            if str(old_value) != new_value:
                updated_fields.append(f"{field}: '{old_value}' -> '{new_value}'")

        # Log spouse changes if implemented

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
    cursor = conn.cursor()

    # Get spouse_code before deleting customer to potentially delete spouse record
    cursor.execute("SELECT spouse_code FROM Customer WHERE cust_no = %s", (cust_no,))
    spouse_code_to_delete = cursor.fetchone()
    if spouse_code_to_delete:
        spouse_code_to_delete = spouse_code_to_delete[0]

    cursor.execute("DELETE FROM Customer WHERE cust_no = %s", (cust_no,))

    if spouse_code_to_delete:
        # Delete related Spouse and SpouseCode records
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
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM Customer")
    total = cursor.fetchone()[0]
    conn.close()

    # Store the total in session
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
    # Assuming email_address is unique and can be used for lookup
    # You might want to store cust_no in session for a more robust lookup
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
        return redirect('/home') # Or to a more appropriate error page
    return render_template('my_record.html', customer=customer)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.form
    conn = None # Initialize conn to None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check for duplicate Customer No or Email
        cursor.execute("SELECT * FROM Customer WHERE cust_no = %s OR email_address = %s", (data['cust_no'], data['email_address']))
        existing = cursor.fetchone()

        if existing:
            flash("Customer number or email address already exists!", "error")
            return redirect('/openAcc')

        spouse_code = None
        occ_id = None
        fin_code = None

        # Handle Spouse, Occupation, FinancialRecord creation/linking more robustly
        # For Spouse: Create a new SpouseCode and Spouse record if spouse_name is provided
        if data.get('spouse_name'):
            cursor.execute("INSERT INTO SpouseCode () VALUES ()")
            spouse_code = cursor.lastrowid
            cursor.execute("""
                INSERT INTO Spouse (spouse_code, name, birthdate, profession)
                VALUES (%s, %s, %s, %s)
            """, (spouse_code, data['spouse_name'], data['spouse_birthdate'], data['spouse_profession']))

        # For Occupation and FinancialRecord, if they are meant to be simple ID generators
        # or if specific data for them is not collected during customer registration,
        # creating empty records might be acceptable for now, but usually they'd have data.
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
        flash("Customer successfully registered!", "success")
        return redirect('/')
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        if conn:
            conn.rollback() # Ensure rollback on error
        return redirect('/openAcc')
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # You might want to consider running setup_database on startup only in a controlled dev environment.
    # For example:
    # if app.debug and not os.path.exists('landbank.sql'): # Only create if not exists
    #     print("Creating landbank.sql and setting up database...")
    #     # You'd need to programmatically write landbank.sql here or ensure it's pre-existing.
    #     # Then call execute_sql_file('landbank.sql')
    app.run(host='0.0.0.0', port=5000, debug=True) # Changed port to 5000 for standard practice
