from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
import psycopg2.extras # For DictCursor
import os
import datetime
import re # Import regex module for robust SQL parsing

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_for_dev') # Get from env or use default

# Database connection function
def get_db_connection():
    # Render automatically provides a DATABASE_URL environment variable for linked databases
    # For local development, you might set this in a .env file or directly in config.py
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if not DATABASE_URL:
        # Fallback for local development if DATABASE_URL is not set
        # IMPORTANT: Replace with your actual local PostgreSQL credentials
        # This block should ideally be removed or secured in production
        try:
            from config import db_config
            conn_string = (
                f"host={db_config['host']} port={db_config['port']} "
                f"dbname={db_config['database']} user={db_config['user']} "
                f"password={db_config['password']}"
            )
            print("Using local db_config fallback.")
        except ImportError:
            print("Error: config.py not found and DATABASE_URL not set. Cannot connect to database.")
            raise # Re-raise to stop execution if no config is available
    else:
        conn_string = DATABASE_URL
        print("Using DATABASE_URL from environment.")

    try:
        conn = psycopg2.connect(conn_string)
        print("Successfully connected to PostgreSQL.")
        return conn
    except psycopg2.Error as err:
        print(f"Error connecting to PostgreSQL database: {err}")
        # In a production environment, you might want to log this error more formally
        # and display a generic error page to the user.
        raise # Re-raise the exception to stop execution if connection fails

# Function to execute SQL from a file (for initial database setup)
def execute_sql_file(filepath):
    conn = None
    cursor = None # Define cursor outside try for finally block
    try:
        conn = get_db_connection()
        conn.autocommit = False # Ensure explicit transaction control for DDL
        cursor = conn.cursor()
        
        with open(filepath, 'r') as f:
            sql_script = f.read()

            # Robustly split SQL by semicolons, handling comments and empty lines
            # Remove block comments /* ... */
            sql_script = re.sub(r'/\*.*?\*/', '', sql_script, flags=re.DOTALL)
            # Remove line comments -- ...
            sql_script = re.sub(r'--.*', '', sql_script)
            
            # Split by semicolon and filter out empty statements
            statements = [s.strip() for s in sql_script.split(';') if s.strip()]

        for statement in statements:
            # Skip CREATE DATABASE and USE commands as they are not needed for Render's managed PG
            if statement.upper().startswith("CREATE DATABASE") or statement.upper().startswith("USE "):
                print(f"Skipping: '{statement[:50]}...' (Not applicable for Render PostgreSQL)")
                continue
            
            try:
                cursor.execute(statement)
                print(f"Executed SQL: {statement[:70]}...")
            except psycopg2.ProgrammingError as err:
                # Catch specific programming errors (e.g., relation already exists)
                # This is common with CREATE TABLE IF NOT EXISTS and is usually benign.
                print(f"SQL statement error (might be benign due to IF NOT EXISTS): {statement[:100]}...\nError: {err}")
                # Do NOT rollback here, let the outer try/except handle critical failures
            except Exception as err:
                # Catch any other unexpected errors during statement execution that are critical
                print(f"CRITICAL Error executing statement: {statement[:100]}...\nError: {err}")
                raise # Re-raise critical errors to trigger the outer rollback for the entire transaction

        conn.commit() # Commit all successful DDL operations if no critical error occurred
        print(f"Successfully executed SQL from {filepath}")
        return True
    except Exception as e: # Catch broader exceptions during file reading, connection, or critical SQL errors
        print(f"Database setup error: {e}")
        if conn:
            conn.rollback() # Ensure rollback on any setup error
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- Flask Routes ---

@app.route('/')
def landingPage():
    return render_template('landing.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    if email == 'landbankADMIN@gmail.com' and password == 'LandBank2025':
        session['admin'] = True
        session['user_email'] = email # Store admin email for consistency
        flash('Admin login successful!', 'success')
        return redirect('/admin_dashboard')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        # Use DictCursor to get results as dictionaries
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Assuming email_address is unique for customer login
        # In a real app, 'password' should be hashed and compared securely
        cursor.execute("SELECT cust_no, custname, email_address, password FROM Customer WHERE email_address = %s", (email,))
        user = cursor.fetchone()

        if user:
            # IMPORTANT: In a real application, NEVER store plain passwords.
            # Use libraries like Flask-Bcrypt to hash and verify passwords.
            if user['password'] == password: # This is for demonstration only!
                session['user'] = user['custname']
                session['user_email'] = user['email_address']
                session['cust_no'] = user['cust_no'] # Store cust_no for my_record
                flash(f"Welcome, {user['custname']}!", 'success')
                return redirect('/home')
            else:
                flash('Invalid email or password.', 'danger')
        else:
            flash('Invalid email or password.', 'danger')
    except psycopg2.Error as err:
        flash(f"Database error during login: {err}", 'danger')
        print(f"Login DB error: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Login unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect('/')

@app.route('/home')
def home():
    if 'user' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect('/')
    return render_template('home.html', user=session['user'])

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        flash('Unauthorized access. Please login as admin.', 'danger')
        return redirect('/')

    customers = []
    total_customers = 'N/A'
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT cust_no, custname, email_address FROM Customer ORDER BY custname")
        customers = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) AS total FROM Customer")
        total_customers = cursor.fetchone()['total']

    except psycopg2.Error as err:
        flash(f"Database error fetching data for admin dashboard: {err}", 'danger')
        print(f"Admin dashboard DB error: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Admin dashboard unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('admin_dashboard.html', customers=customers, total_customers=total_customers)

@app.route('/admin/view/<cust_no>')
def admin_view_customer(cust_no):
    if 'admin' not in session:
        flash('Unauthorized access. Please login as admin.', 'danger')
        return redirect('/')

    customer = None
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("""
            SELECT c.*, s.name AS spouse_name, s.birthdate AS spouse_birthdate, s.profession AS spouse_profession
            FROM Customer c
            LEFT JOIN Spouse s ON c.spouse_code = s.spouse_code
            WHERE c.cust_no = %s
        """, (cust_no,))
        customer = cursor.fetchone()

        if not customer:
            flash("Customer not found.", 'warning')
            return redirect('/admin_dashboard')

    except psycopg2.Error as err:
        flash(f"Database error viewing customer: {err}", 'danger')
        print(f"Admin view customer DB error: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Admin view customer unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('admin_view_customer.html', customer=customer)

@app.route('/admin/edit/<cust_no>', methods=['GET', 'POST'])
def admin_edit_customer(cust_no):
    if 'admin' not in session:
        flash('Unauthorized access. Please login as admin.', 'danger')
        return redirect('/')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if request.method == 'POST':
            data = request.form
            cursor.execute("SELECT * FROM Customer WHERE cust_no = %s", (cust_no,))
            original_customer = cursor.fetchone()

            if not original_customer:
                flash("Customer not found for update.", 'danger')
                return redirect('/admin_dashboard')

            # Update Customer table
            update_customer_query = """
                UPDATE Customer SET
                    custname=%s, datebirth=%s, nationality=%s, citizenship=%s,
                    custsex=%s, placebirth=%s, civilstatus=%s, num_children=%s,
                    mmaiden_name=%s, cust_address=%s, email_address=%s, contact_no=%s
                WHERE cust_no=%s
            """
            cursor.execute(update_customer_query, (
                data['custname'], data['datebirth'], data['nationality'], data['citizenship'],
                data['custsex'], data['placebirth'], data['civilstatus'], data['num_children'],
                data['mmaiden_name'], data['cust_address'], data['email_address'], data['contact_no'],
                cust_no
            ))

            # Handle Spouse details update
            spouse_name = data.get('spouse_name')
            spouse_birthdate = data.get('spouse_birthdate')
            spouse_profession = data.get('spouse_profession')

            if original_customer['spouse_code']:
                # Update existing Spouse record
                cursor.execute("""
                    UPDATE Spouse SET
                        name=%s, birthdate=%s, profession=%s
                    WHERE spouse_code=%s
                """, (spouse_name, spouse_birthdate, spouse_profession, original_customer['spouse_code']))
            elif spouse_name: # If spouse data provided but no existing spouse_code
                # Create new SpouseCode and Spouse record
                cursor.execute("INSERT INTO SpouseCode DEFAULT VALUES RETURNING spouse_code")
                new_spouse_code = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO Spouse (spouse_code, name, birthdate, profession)
                    VALUES (%s, %s, %s, %s)
                """, (new_spouse_code, spouse_name, spouse_birthdate, spouse_profession))
                # Link the new spouse_code to the customer
                cursor.execute("UPDATE Customer SET spouse_code = %s WHERE cust_no = %s", (new_spouse_code, cust_no))

            conn.commit()

            # Log changes (simplified, a more robust log would compare old vs new values)
            with open("admin_logs.txt", "a") as log:
                log.write(f"[{datetime.datetime.now()}] ADMIN UPDATED Customer: {cust_no}\n")
                log.write(f"  - Fields updated based on form submission.\n")

            flash("Customer record updated successfully!", "success")
            return redirect('/admin_dashboard')

        # GET request: Fetch customer and spouse data for the form
        cursor.execute("""
            SELECT c.*, s.name AS spouse_name, s.birthdate AS spouse_birthdate, s.profession AS spouse_profession
            FROM Customer c
            LEFT JOIN Spouse s ON c.spouse_code = s.spouse_code
            WHERE c.cust_no = %s
        """, (cust_no,))
        customer = cursor.fetchone()

        if not customer:
            flash("Customer not found.", 'warning')
            return redirect('/admin_dashboard')

        return render_template('admin_edit_customer.html', customer=customer)

    except psycopg2.Error as err:
        flash(f"Database error during edit: {err}", 'danger')
        print(f"Admin edit customer DB error: {err}")
        if conn:
            conn.rollback()
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Admin edit customer unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect('/admin_dashboard') # Fallback redirect on error


@app.route('/admin/delete/<cust_no>', methods=['POST'])
def admin_delete_customer(cust_no):
    if 'admin' not in session:
        flash('Unauthorized access. Please login as admin.', 'danger')
        return redirect('/')

    conn = None
    cursor = None
    try:
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
            log.write(f"[{datetime.datetime.now()}] ADMIN DELETED Customer: {cust_no}\n")
            if spouse_code_to_delete:
                log.write(f"  - Also deleted associated Spouse and SpouseCode with ID: {spouse_code_to_delete}\n")

        flash(f"Customer {cust_no} and related records deleted successfully!", "success")
    except psycopg2.Error as err:
        flash(f"Database error deleting customer: {err}", 'danger')
        print(f"Admin delete customer DB error: {err}")
        if conn:
            conn.rollback()
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Admin delete customer unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect('/admin_dashboard')

@app.route('/compute_customers', methods=['POST'])
def compute_customers():
    if 'admin' not in session:
        flash('Unauthorized access. Please login as admin.', 'danger')
        return redirect('/')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM Customer")
        total = cursor.fetchone()[0]
        session['total_customers'] = total
        flash(f"Total customers computed: {total}", "info")
    except psycopg2.Error as err:
        flash(f"Database error computing customers: {err}", 'danger')
        print(f"Compute customers DB error: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Compute customers unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect('/admin_dashboard')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect('/')

@app.route('/customers')
def customer_list():
    # This route might be for general viewing or debugging, not necessarily admin-only
    # You might want to add a login check or make it public based on requirements
    customers = []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT cust_no, custname, email_address, contact_no FROM Customer ORDER BY custname")
        customers = cursor.fetchall()
    except psycopg2.Error as err:
        flash(f"Database error fetching customer list: {err}", 'danger')
        print(f"Customer list DB error: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"Customer list unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return render_template('customer_list.html', customers=customers)

@app.route('/openAcc')
def openAcc():
    return render_template('openAcc.html')

@app.route('/my_record')
def my_record():
    if 'user' not in session or 'cust_no' not in session:
        flash('Please log in to view your record.', 'warning')
        return redirect('/')

    cust_no = session['cust_no']
    customer = None
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("""
            SELECT c.*, s.name AS spouse_name, s.birthdate AS spouse_birthdate, s.profession AS spouse_profession
            FROM Customer c
            LEFT JOIN Spouse s ON c.spouse_code = s.spouse_code
            WHERE c.cust_no = %s
        """, (cust_no,))
        customer = cursor.fetchone()

        if not customer:
            flash("Your record was not found.", "error")
            return redirect('/home')

    except psycopg2.Error as err:
        flash(f"Database error fetching your record: {err}", 'danger')
        print(f"My record DB error: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'danger')
        print(f"My record unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return render_template('my_record.html', customer=customer)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.form
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # Use DictCursor for existing check

        # Check for duplicate Customer No or Email
        cursor.execute("SELECT cust_no FROM Customer WHERE cust_no = %s OR email_address = %s", (data['cust_no'], data['email_address']))
        existing = cursor.fetchone()

        if existing:
            flash("Customer number or email address already exists!", "danger")
            return redirect('/openAcc')

        spouse_code = None
        occ_id = None
        fin_code = None

        # Handle Spouse, Occupation, FinancialRecord creation/linking
        # Spouse is optional, so only create if spouse_name is provided
        if data.get('spouse_name'):
            cursor.execute("INSERT INTO SpouseCode DEFAULT VALUES RETURNING spouse_code")
            spouse_code = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO Spouse (spouse_code, name, birthdate, profession)
                VALUES (%s, %s, %s, %s)
            """, (spouse_code, data.get('spouse_name'), data.get('spouse_birthdate'), data.get('spouse_profession')))

        # For Occupation and FinancialRecord, creating empty records if no specific data is provided
        # These are always created to get an ID for the customer record
        cursor.execute("INSERT INTO Occupation DEFAULT VALUES RETURNING occ_id")
        occ_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO FinancialRecord DEFAULT VALUES RETURNING fin_code")
        fin_code = cursor.fetchone()[0]

        insert_customer_query = """
            INSERT INTO Customer (
                cust_no, custname, datebirth, nationality, citizenship,
                custsex, placebirth, civilstatus, num_children, mmaiden_name,
                cust_address, email_address, contact_no,
                spouse_code, occ_id, fin_code, password -- Added password field
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        # IMPORTANT: In a real app, hash the password before inserting!
        # For now, using plain text for demonstration matching your login logic.
        # The 'password' field is not directly in your openAcc.html form,
        # so you might need to add it or generate a default/temporary one.
        # For this example, I'm assuming you'll add a password field to the form
        # or handle it in some other way. If not, this will fail.
        # For demonstration, let's use cust_no as a temporary password if not provided.
        customer_password = data.get('password', data['cust_no']) # Fallback to cust_no if password field is missing

        cursor.execute(insert_customer_query, (
            data['cust_no'], data['custname'], data['datebirth'], data['nationality'], data['citizenship'],
            data['custsex'], data['placebirth'], data['civilstatus'], data['num_children'], data['mmaiden_name'],
            data['cust_address'], data['email_address'], data['contact_no'],
            spouse_code, occ_id, fin_code, customer_password # Pass the password
        ))

        conn.commit()
        flash("Customer successfully registered!", "success")
        return redirect('/')
    except psycopg2.Error as err:
        flash(f"Database error during registration: {err}", "danger")
        print(f"Add customer DB error: {err}")
        if conn:
            conn.rollback()
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        print(f"Add customer unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect('/openAcc') # Redirect back to form on error

# --- Main Application Run ---
if __name__ == '__main__':
    print("Starting Flask application...")
    # Attempt to set up the database schema on application startup
    # This is ideal for development/testing environments.
    # In production, consider using database migration tools.
    sql_file_path = 'landbank.sql'
    if os.path.exists(sql_file_path):
        print(f"Found {sql_file_path}. Attempting to execute SQL for database setup...")
        execute_sql_file(sql_file_path)
    else:
        print(f"Warning: {sql_file_path} not found. Database tables will not be created automatically.")

    # Flask development server settings
    app.run(host='0.0.0.0', port=5000, debug=True)
