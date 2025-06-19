import psycopg2 
from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid 
import os 
import psycopg2.extras 

from db_config import get_db_url

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_here') 
debug_mode = os.environ.get('FLASK_DEBUG', 'True') == 'True'

def get_db_connection():
    """Establishes and returns a database connection using psycopg2 for PostgreSQL."""
    try:
        conn_url = get_db_url()
        conn = psycopg2.connect(conn_url)
        print("Successfully connected to PostgreSQL database.")
        return conn
    except psycopg2.Error as err:
        print(f"Error connecting to PostgreSQL database: {err}")
        return None

# --- Function to Ensure Database Schema (for development/initial setup) ---
def _ensure_database_schema():
    """
    Ensures that necessary tables exist and have appropriate types for PostgreSQL.
    This function should typically be run only once, or managed by a proper migration tool.
    For development, it runs on app startup.
    
    This version includes logic to ALTER specific column types if they are not as expected.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to get database connection for schema update.")
            return

        cursor = conn.cursor()
        conn.autocommit = True # Set to True for schema operations outside of explicit transactions
        print("Attempting to ensure PostgreSQL database schema...\n")

        # Define table creation SQL for PostgreSQL
        # Tables are ordered to respect foreign key dependencies:
        # Parent tables (no FKs or FKs to already defined tables) come first.
        schema_sql = {
            'occupation': """
                CREATE TABLE IF NOT EXISTS occupation (
                    occ_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    occ_type VARCHAR(255),
                    bus_nature VARCHAR(255)
                );
            """,
            'financial_record': """
                CREATE TABLE IF NOT EXISTS financial_record (
                    fin_code UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_wealth TEXT,
                    mon_income TEXT, 
                    ann_income TEXT 
                );
            """,
            'bank_details': """
                CREATE TABLE IF NOT EXISTS bank_details (
                    bank_code VARCHAR(10) PRIMARY KEY, 
                    bank_name VARCHAR(255),
                    branch VARCHAR(255)
                );
            """,
            'public_official_details': """
                CREATE TABLE IF NOT EXISTS public_official_details (
                    gov_int_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    gov_int_name VARCHAR(255),
                    official_position VARCHAR(255),
                    branch_orgname VARCHAR(255)
                );
            """,
            'customer': """
                CREATE TABLE IF NOT EXISTS customer (
                    cust_no UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    custname VARCHAR(255),
                    datebirth DATE,
                    nationality VARCHAR(255),
                    citizenship VARCHAR(255),
                    custsex VARCHAR(50),
                    placebirth VARCHAR(255),
                    civilstatus VARCHAR(50),
                    num_children INTEGER DEFAULT 0,
                    mmaiden_name VARCHAR(255),
                    cust_address TEXT,
                    email_address VARCHAR(255) UNIQUE, 
                    contact_no VARCHAR(20),
                    occ_id UUID,
                    fin_code UUID,
                    registration_status VARCHAR(50) DEFAULT 'Pending', 
                    FOREIGN KEY (occ_id) REFERENCES occupation (occ_id) ON DELETE SET NULL,
                    FOREIGN KEY (fin_code) REFERENCES financial_record (fin_code) ON DELETE SET NULL
                );
            """,
            'employer_details': """
                CREATE TABLE IF NOT EXISTS employer_details (
                    emp_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    occ_id UUID REFERENCES occupation (occ_id) ON DELETE SET NULL,
                    tin_id VARCHAR(50),
                    empname VARCHAR(255),
                    emp_address TEXT,
                    phonefax_no VARCHAR(50),
                    job_title VARCHAR(255),
                    emp_date DATE
                );
            """,
            'credentials': """
                CREATE TABLE IF NOT EXISTS credentials (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    PRIMARY KEY (cust_no, username) 
                );
            """,
            'spouse': """
                CREATE TABLE IF NOT EXISTS spouse (
                    cust_no UUID PRIMARY KEY REFERENCES customer (cust_no) ON DELETE CASCADE,
                    sp_name VARCHAR(255),
                    sp_datebirth DATE,
                    sp_profession VARCHAR(255)
                );
            """,
            'company_affiliation': """
                CREATE TABLE IF NOT EXISTS company_affiliation (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    depositor_role VARCHAR(255),
                    dep_compname VARCHAR(255),
                    PRIMARY KEY (cust_no, depositor_role, dep_compname) 
                );
            """,
            'existing_bank': """
                CREATE TABLE IF NOT EXISTS existing_bank (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    bank_code VARCHAR(10) REFERENCES bank_details (bank_code) ON DELETE CASCADE,
                    acc_type VARCHAR(255),
                    PRIMARY KEY (cust_no, bank_code, acc_type) 
                );
            """,
            'cust_po_relationship': """
                CREATE TABLE IF NOT EXISTS cust_po_relationship (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    gov_int_id UUID REFERENCES public_official_details (gov_int_id) ON DELETE CASCADE,
                    relation_desc VARCHAR(255),
                    PRIMARY KEY (cust_no, gov_int_id) 
                );
            """,
            'employment_details': """
                CREATE TABLE IF NOT EXISTS employment_details (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    emp_id UUID REFERENCES employer_details (emp_id) ON DELETE CASCADE,
                    PRIMARY KEY (cust_no, emp_id) 
                );
            """
        }

        # Enable UUID generation extension if not already enabled
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            conn.commit()
            print("  - Ensured 'uuid-ossp' extension is enabled.")
        except psycopg2.Error as e:
            print(f"  - WARNING: Could not enable 'uuid-ossp' extension (might already exist or permission issue): {e}")
            conn.rollback() 

        for table_name, create_sql in schema_sql.items():
            try:
                print(f"  - Ensuring table: {table_name}")
                cursor.execute(create_sql)
                conn.commit() 
                print(f"  - Table '{table_name}' checked/created successfully.")
            except psycopg2.Error as err:
                print(f"  - ERROR creating/checking table {table_name}: {err}")
                conn.rollback() 
        
        # --- ALTER TABLE LOGIC (for financial_record income types and customer status) ---
        try:
            # Check and alter mon_income to TEXT
            cursor.execute("""
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'financial_record' AND column_name = 'mon_income';
            """)
            current_mon_income_type = cursor.fetchone()
            if current_mon_income_type and current_mon_income_type[0] != 'text':
                print("  - Altering 'financial_record.mon_income' to TEXT...")
                cursor.execute("ALTER TABLE financial_record ALTER COLUMN mon_income TYPE TEXT USING mon_income::text;")
                conn.commit()
                print("  - Successfully altered 'financial_record.mon_income' to TEXT.")

            # Check and alter ann_income to TEXT
            cursor.execute("""
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'financial_record' AND column_name = 'ann_income';
            """)
            current_ann_income_type = cursor.fetchone()
            if current_ann_income_type and current_ann_income_type[0] != 'text':
                print("  - Altering 'financial_record.ann_income' to TEXT...")
                cursor.execute("ALTER TABLE financial_record ALTER COLUMN ann_income TYPE TEXT USING ann_income::text;")
                conn.commit()
                print("  - Successfully altered 'financial_record.ann_income' to TEXT.")

            # Check and add registration_status to customer if it doesn't exist
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'customer' AND column_name = 'registration_status';
            """)
            status_column_exists = cursor.fetchone()
            if not status_column_exists:
                print("  - Adding 'registration_status' column to 'customer' table...")
                cursor.execute("ALTER TABLE customer ADD COLUMN registration_status VARCHAR(50) DEFAULT 'Pending';")
                conn.commit()
                print("  - Successfully added 'registration_status' to 'customer' table.")

        except psycopg2.Error as alter_err:
            print(f"  - ERROR during ALTER TABLE for schema updates: {alter_err}")
            conn.rollback()
        except Exception as e:
            print(f"  - Unexpected error during ALTER TABLE check: {e}")
            conn.rollback()
        # --- END ALTER TABLE LOGIC ---

        print("\nPostgreSQL database schema check/update completed.")
    except psycopg2.Error as err:
        print(f"Error during PostgreSQL database schema update: {err}")
    except Exception as e:
        print(f"An unexpected error occurred during schema update: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # --- DEBUG: Print all registered Flask endpoints after schema setup ---
    print("\n--- Flask URL Map Endpoints (after schema setup) ---")
    for rule in app.url_map.iter_rules():
        print(f"Endpoint: {rule.endpoint}, Methods: {rule.methods}, Rule: {rule.rule}")
    print("---------------------------------------------------\n")


# --- Page Routes ---
@app.route('/')
def landing():
    """Renders the landing page."""
    return render_template('landing.html')

@app.route('/home')
def home():
    """Renders the home page."""
    return render_template('home.html')

@app.route('/about')
def about():
    """Renders the about page."""
    return render_template('about.html')

@app.route('/services')
def services():
    """Renders the services page."""
    return render_template('services.html')

@app.route('/contact')
def contact():
    """Renders the contact page."""
    return render_template('contact.html')

@app.route('/registrationPrint')
def registrationPrint():
    """Renders the registration print/summary page."""
    return render_template('registrationPrint.html')

@app.route('/register')
def register():
    """Renders the registration page (initial entry point)."""
    return render_template('register.html')

# --- Registration Flow Pages (GET requests only, data handled by JS) ---
@app.route('/registration1', methods=['GET'])
def registration1():
    """Renders the first step of the registration form."""
    return render_template('registration1.html')

@app.route('/registration2', methods=['GET'])
def registration2():
    """Renders the second step of the registration form."""
    return render_template('registration2.html')

@app.route('/registration3', methods=['GET'])
def registration3():
    """Renders the third step of the registration form."""
    return render_template('registration3.html')


@app.route('/submitRegistration', methods=['POST'])
def submit_registration():
    """
    Receives all registration data as JSON from the frontend (registration.js)
    and handles the complete database insertion, including credentials.
    Generates UUIDs for primary keys.
    """
    conn = None
    cursor = None
    try:
        # Get JSON data sent from the frontend
        data = request.get_json()
        r1 = data.get('registration1', {})
        r2 = data.get('registration2', {})
        r3 = data.get('registration3', {})

        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()
        conn.autocommit = False # Start a transaction

        # --- 1. Insert into occupation table ---
        occ_type = r2.get('occupation')
        bus_nature = r2.get('natureOfBusiness')
        sql_occ = "INSERT INTO occupation (occ_type, bus_nature) VALUES (%s, %s) RETURNING occ_id;"
        cursor.execute(sql_occ, (occ_type, bus_nature))
        occ_id = cursor.fetchone()[0] # Fetch the generated UUID

        # --- 2. Insert into financial_record table ---
        source_wealth_list = r2.get('sourceOfWealth', [])
        source_wealth = ', '.join(source_wealth_list) if isinstance(source_wealth_list, list) else source_wealth_list
        mon_income = r2.get('monthlyIncome')
        ann_income = r2.get('annualIncome')
        sql_fin = "INSERT INTO financial_record (source_wealth, mon_income, ann_income) VALUES (%s, %s, %s) RETURNING fin_code;"
        cursor.execute(sql_fin, (source_wealth, mon_income, ann_income))
        fin_code = cursor.fetchone()[0] # Fetch the generated UUID

        # --- 3. Insert into customer table ---
        custname = f"{r1.get('firstName', '')} {r1.get('lastName', '')}"
        datebirth = r1.get('dob')
        nationality = r1.get('nationality')
        citizenship = r1.get('citizenship')
        custsex = r1.get('sex')
        placebirth = r1.get('placeOfBirth')
        civilstatus = r1.get('civilStatus')
        num_children = int(r1.get('children', 0) or 0)
        mmaiden_name = r1.get('motherMaidenName')
        cust_address = r1.get('address')
        email_address = r1.get('email')
        contact_no = r1.get('telephone')
        # New customer registration always defaults to 'Pending'
        registration_status = 'Pending' 

        sql_cust = """INSERT INTO customer (custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, occ_id, fin_code, registration_status)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING cust_no;"""
        customer_data = (
            custname, datebirth, nationality, citizenship, custsex,
            placebirth, civilstatus, num_children, mmaiden_name,
            cust_address, email_address, contact_no, occ_id, fin_code,
            registration_status
        )
        cursor.execute(sql_cust, customer_data)
        cust_no = cursor.fetchone()[0] # Fetch the generated UUID for cust_no
        print(f"--- DEBUG: Successfully inserted customer. New cust_no: {cust_no} (Type: {type(cust_no)}) ---")

        # --- 4. Insert into employer_details and employment_details if applicable ---
        if r2.get('occupation') == 'Employed':
            tin_id = r2.get('tinId', '')
            empname = r2.get('companyName', '')
            emp_address = r2.get('employerAddress', '')
            phonefax_no = r2.get('employerPhone', '')
            emp_date_str = r2.get('employmentDate')
            emp_date = emp_date_str if emp_date_str else None # Handle empty date string
            job_title = r2.get('jobTitle', '')

            sql_emp_details = "INSERT INTO employer_details (occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING emp_id;"
            cursor.execute(sql_emp_details, (occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))
            emp_id = cursor.fetchone()[0] # Fetch the generated UUID

            sql_emp_link = "INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s)"
            cursor.execute(sql_emp_link, (cust_no, emp_id))

        # --- 5. Insert into spouse table if married ---
        if r1.get('civilStatus') == 'Married':
            sp_name = f"{r1.get('spouseFirstName', '')} {r1.get('spouseLastName', '')}"
            sp_datebirth_str = r1.get('spouseDob')
            sp_datebirth = sp_datebirth_str if sp_datebirth_str else None # Handle empty date string
            sp_profession = r1.get('spouseProfession')

            if sp_name.strip() and sp_profession and sp_datebirth: # Only insert if all spouse fields are non-empty
                sql_spouse = "INSERT INTO spouse (cust_no, sp_name, sp_datebirth, sp_profession) VALUES (%s, %s, %s, %s);"
                cursor.execute(sql_spouse, (cust_no, sp_name, sp_datebirth, sp_profession))

        # --- 6. Insert into company_affiliation if applicable ---
        depositor_role = r3.get('depositorRole')
        dep_compname = r3.get('companyName')
        if depositor_role or dep_compname:
            sql_company = "INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname) VALUES (%s, %s, %s);"
            cursor.execute(sql_company, (cust_no, depositor_role, dep_compname))

        # --- 7. Insert into existing_bank if applicable ---
        bank_code = r3.get('bankCode')
        acc_type = r3.get('accountType')
        if bank_code and acc_type:
            # You might want to validate bank_code against your bank_details table here
            sql_bank = "INSERT INTO existing_bank (cust_no, bank_code, acc_type) VALUES (%s, %s, %s);"
            cursor.execute(sql_bank, (cust_no, bank_code, acc_type))
            
        # --- 8. Insert into public_official_details and cust_po_relationship if applicable ---
        gov_int_name = r3.get('governmentOfficialName')
        official_position = r3.get('officialPosition')
        branch_orgname = r3.get('branchOrgName')
        relation_desc = r3.get('relationshipNature')

        if gov_int_name or official_position or branch_orgname or relation_desc:
            # Check if this public official already exists to avoid duplicates
            cursor.execute("SELECT gov_int_id FROM public_official_details WHERE gov_int_name = %s AND official_position = %s;",
                           (gov_int_name, official_position))
            existing_po = cursor.fetchone()
            
            gov_int_id = None
            if existing_po:
                gov_int_id = existing_po[0]
            else:
                # If not, insert new public official
                sql_po = "INSERT INTO public_official_details (gov_int_name, official_position, branch_orgname) VALUES (%s, %s, %s) RETURNING gov_int_id;"
                cursor.execute(sql_po, (gov_int_name, official_position, branch_orgname))
                gov_int_id = cursor.fetchone()[0]

            # Link customer to public official
            if gov_int_id:
                sql_po_rel = "INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc) VALUES (%s, %s, %s);"
                cursor.execute(sql_po_rel, (cust_no, gov_int_id, relation_desc))


        conn.commit() # Commit all changes if everything is successful
        flash('Registration successful! Please proceed to login.', 'success')
        return jsonify(success=True, cust_no=str(cust_no)), 200

    except psycopg2.IntegrityError as err:
        conn.rollback()
        print(f"Database Integrity Error during registration: {err}")
        if "customer_email_address_key" in str(err):
            flash('Email address already registered. Please use a different email or login.', 'danger')
            return jsonify(success=False, message='Email address already registered.'), 409 # Conflict
        elif "credentials_username_key" in str(err):
            flash('Username already taken. Please choose a different username.', 'danger')
            return jsonify(success=False, message='Username already taken.'), 409
        elif "bank_details" in str(err):
            flash('Invalid Bank Code provided.', 'danger')
            return jsonify(success=False, message='Invalid Bank Code.'), 400
        else:
            flash(f'A database integrity error occurred: {err}', 'danger')
            return jsonify(success=False, message='A database integrity error occurred.'), 500
    except psycopg2.Error as err:
        conn.rollback() # Rollback on any database error
        print(f"Database error during registration: {err}")
        if debug_mode:
            raise # Re-raise in debug mode to see full traceback
        flash(f'An error occurred during registration: {err}', 'danger')
        return jsonify(success=False, message='An error occurred during registration.'), 500
    except Exception as e:
        if conn: # Ensure conn exists before trying to rollback
            conn.rollback()
        print(f"Unexpected error during registration: {e}")
        if debug_mode:
            raise # Re-raise in debug mode to see full traceback
        flash('An unexpected error occurred during registration.', 'danger')
        return jsonify(success=False, message='An unexpected error occurred during registration.'), 500
    finally:
        # Ensure cursor and connection are closed
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if not conn:
                flash('Database connection failed.', 'danger')
                return redirect(url_for('login'))

            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # Use DictCursor for easy column access
            
            # Fetch user credentials along with customer and user_role details
            cursor.execute("""
                SELECT 
                    cred.cust_no, cred.username, cred.password, 
                    c.custname, c.registration_status,
                    CASE 
                        WHEN EXISTS (SELECT 1 FROM admins WHERE cust_no = cred.cust_no) THEN 'Admin'
                        ELSE 'Customer'
                    END as user_role
                FROM credentials cred
                JOIN customer c ON cred.cust_no = c.cust_no
                WHERE cred.username = %s;
            """, (username,))
            user = cursor.fetchone()

            if user:
                # In a real application, use bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
                # For this example, we'll do a direct string compare (NOT SECURE FOR PRODUCTION)
                if password == user['password']: # Replace with secure password hashing check
                    session['logged_in'] = True
                    session['username'] = user['username']
                    session['cust_no'] = str(user['cust_no'])
                    session['user_role'] = user['user_role']
                    flash('Logged in successfully!', 'success')
                    if session['user_role'] == 'Admin':
                        return redirect(url_for('admin_dashboard_page'))
                    else:
                        return redirect(url_for('customer_dashboard_page')) # Redirect regular customers
                else:
                    flash('Invalid username or password.', 'danger')
            else:
                flash('Invalid username or password.', 'danger')

        except psycopg2.Error as err:
            print(f"Database error during login: {err}")
            flash(f'An error occurred: {err}', 'danger')
        except Exception as e:
            print(f"Error during login: {e}")
            flash('An unexpected error occurred during login.', 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('cust_no', None)
    session.pop('user_role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Placeholder for a simple login_required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Placeholder for roles_required decorator
from functools import wraps

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('home')) # Redirect to a generic home or error page
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Admin Dashboard ---
@app.route('/admin_dashboard')
@login_required
@roles_required('Admin')
def admin_dashboard_page():
    conn = None
    cursor = None
    customers = []
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return render_template('admin_dashboard.html', customers=[])

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT cust_no, custname, email_address, contact_no, registration_status FROM customer ORDER BY custname;")
        customers = cursor.fetchall()
    except psycopg2.Error as err:
        print(f"Database error fetching customers: {err}")
        flash(f'Error loading customers: {err}', 'danger')
    except Exception as e:
        print(f"Error: {e}")
        flash('An unexpected error occurred.', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return render_template('admin_dashboard.html', customers=customers)


@app.route('/admin/customer/<uuid:cust_no>')
@login_required
@roles_required('Admin')
def admin_customer_details(cust_no):
    conn = None
    cursor = None
    customer = {}
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page'))

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Fetch all related details using LEFT JOINs
        cursor.execute("""
            SELECT
                c.cust_no, c.custname, c.datebirth, c.nationality, c.citizenship, c.custsex, c.placebirth,
                c.civilstatus, c.num_children, c.mmaiden_name, c.cust_address, c.email_address,
                c.contact_no, c.registration_status,
                o.occ_type, o.bus_nature,
                f.source_wealth, f.mon_income, f.ann_income,
                e.tin_id, e.empname, e.emp_address, e.phonefax_no, e.job_title, e.emp_date,
                s.sp_name, s.sp_datebirth, s.sp_profession,
                comp.depositor_role, comp.dep_compname,
                eb.bank_code, eb.acc_type,
                po.gov_int_name, po.official_position, po.branch_orgname,
                cpr.relation_desc
            FROM customer c
            LEFT JOIN occupation o ON c.occ_id = o.occ_id
            LEFT JOIN financial_record f ON c.fin_code = f.fin_code
            LEFT JOIN employment_details emd ON c.cust_no = emd.cust_no
            LEFT JOIN employer_details e ON emd.emp_id = e.emp_id
            LEFT JOIN spouse s ON c.cust_no = s.cust_no
            LEFT JOIN company_affiliation comp ON c.cust_no = comp.cust_no
            LEFT JOIN existing_bank eb ON c.cust_no = eb.cust_no
            LEFT JOIN cust_po_relationship cpr ON c.cust_no = cpr.cust_no
            LEFT JOIN public_official_details po ON cpr.gov_int_id = po.gov_int_id
            WHERE c.cust_no = %s;
        """, (str(cust_no),))
        
        customer = cursor.fetchone()

        if not customer:
            flash('Customer not found.', 'danger')
            return redirect(url_for('admin_dashboard_page'))
        
        # Format dates for display
        if customer.get('datebirth'):
            customer['datebirth_formatted'] = customer['datebirth'].strftime('%Y-%m-%d')
        if customer.get('emp_date'):
            customer['emp_date_formatted'] = customer['emp_date'].strftime('%Y-%m-%d')
        if customer.get('sp_datebirth'):
            customer['sp_datebirth_formatted'] = customer['sp_datebirth'].strftime('%Y-%m-%d')

    except psycopg2.Error as err:
        print(f"Database error fetching customer details: {err}")
        flash(f'An error occurred: {err}', 'danger')
        return redirect(url_for('admin_dashboard_page'))
    except Exception as e:
        print(f"Error fetching customer details: {e}")
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('admin_dashboard_page'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return render_template('admin_customer_details.html', customer=customer)


@app.route('/admin/add_customer', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def admin_add_customer():
    conn = None
    cursor = None
    if request.method == 'POST':
        try:
            # Collect data from form
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            custname = f"{first_name} {last_name}".strip() if first_name and last_name else request.form.get('custname')
            if not custname: # Fallback if combination is empty or not provided
                custname = request.form.get('custname', 'N/A') # Ensure it's never empty

            datebirth = request.form.get('dob')
            nationality = request.form.get('nationality')
            citizenship = request.form.get('citizenship')
            custsex = request.form.get('sex')
            placebirth = request.form.get('placeOfBirth')
            civilstatus = request.form.get('civilStatus')
            num_children = int(request.form.get('children', 0) or 0)
            mmaiden_name = request.form.get('motherMaidenName')
            cust_address = request.form.get('address')
            email_address = request.form.get('email')
            contact_no = request.form.get('telephone')
            registration_status = request.form.get('registrationStatus', 'Pending') # Default to Pending

            # Occupation details
            occ_type = request.form.get('occupation')
            bus_nature = request.form.get('natureOfBusiness')

            # Financial details
            source_wealth_list = request.form.getlist('sourceOfWealth')
            source_wealth = ', '.join(source_wealth_list) if isinstance(source_wealth_list, list) else request.form.get('sourceOfWealth', '')
            mon_income = request.form.get('monthlyIncome')
            ann_income = request.form.get('annualIncome')

            conn = get_db_connection()
            if not conn:
                flash('Database connection failed.', 'danger')
                return redirect(url_for('admin_add_customer'))

            cursor = conn.cursor()
            conn.autocommit = False # Start a transaction

            occ_id = None
            if occ_type or bus_nature:
                cursor.execute("INSERT INTO occupation (occ_type, bus_nature) VALUES (%s, %s) RETURNING occ_id;",
                               (occ_type, bus_nature))
                occ_id_row = cursor.fetchone()
                if occ_id_row:
                    occ_id = occ_id_row[0]
                else:
                    flash('Failed to create occupation record.', 'warning')


            fin_code = None
            if source_wealth or mon_income or ann_income:
                cursor.execute("INSERT INTO financial_record (source_wealth, mon_income, ann_income) VALUES (%s, %s, %s) RETURNING fin_code;",
                               (source_wealth, mon_income, ann_income))
                fin_code_row = cursor.fetchone()
                if fin_code_row:
                    fin_code = fin_code_row[0]
                else:
                    flash('Failed to create financial record.', 'warning')


            # Insert into customer table
            sql_cust = """INSERT INTO customer (custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, occ_id, fin_code, registration_status)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING cust_no;"""
            customer_data = (
                custname, datebirth, nationality, citizenship, custsex,
                placebirth, civilstatus, num_children, mmaiden_name,
                cust_address, email_address, contact_no, occ_id, fin_code, registration_status
            )
            cursor.execute(sql_cust, customer_data)
            cust_no = cursor.fetchone()[0] # Get the newly generated cust_no

            # Employer details if applicable
            if occ_type == 'Employed' and occ_id:
                tin_id = request.form.get('tinId', '')
                empname = request.form.get('companyName', '')
                emp_address = request.form.get('employerAddress', '')
                phonefax_no = request.form.get('employerPhone', '')
                emp_date_str = request.form.get('employmentDate')
                emp_date = emp_date_str if emp_date_str else None
                job_title = request.form.get('jobTitle', '')

                cursor.execute("""
                    INSERT INTO employer_details (occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING emp_id;
                """, (occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))
                emp_id_row = cursor.fetchone()
                if emp_id_row:
                    emp_id = emp_id_row[0]
                    cursor.execute("INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s);",
                                   (cust_no, emp_id))
                else:
                    flash('Failed to create employer details record.', 'warning')


            # Spouse details if married
            if civilstatus == 'Married':
                sp_name = f"{request.form.get('spouseFirstName', '')} {request.form.get('spouseLastName', '')}".strip()
                sp_datebirth_str = request.form.get('spouseDob')
                sp_datebirth = sp_datebirth_str if sp_datebirth_str else None
                sp_profession = request.form.get('spouseProfession', '')

                if sp_name or sp_datebirth or sp_profession:
                    cursor.execute("""
                        INSERT INTO spouse (cust_no, sp_name, sp_datebirth, sp_profession)
                        VALUES (%s, %s, %s, %s);
                    """, (cust_no, sp_name, sp_datebirth, sp_profession))

            # Company affiliation
            depositor_role = request.form.get('depositorRole')
            dep_compname = request.form.get('companyNameAffiliation')
            if depositor_role or dep_compname:
                cursor.execute("""
                    INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname)
                    VALUES (%s, %s, %s);
                """, (cust_no, depositor_role, dep_compname))

            # Existing bank details
            bank_code = request.form.get('bankCode')
            acc_type = request.form.get('accountType')
            if bank_code and acc_type:
                # Basic check if bank_code exists in bank_details (foreign key constraint will also catch)
                cursor.execute("SELECT bank_name FROM bank_details WHERE bank_code = %s;", (bank_code,))
                if cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO existing_bank (cust_no, bank_code, acc_type)
                        VALUES (%s, %s, %s);
                    """, (cust_no, bank_code, acc_type))
                else:
                    flash(f'Bank Code {bank_code} does not exist. Please add it first.', 'danger')

            # Public Official relationship
            gov_int_name = request.form.get('governmentOfficialName')
            official_position = request.form.get('officialPosition')
            branch_orgname = request.form.get('branchOrgName')
            relation_desc = request.form.get('relationshipNature')

            if gov_int_name or official_position or branch_orgname or relation_desc:
                gov_int_id = None
                cursor.execute("SELECT gov_int_id FROM public_official_details WHERE gov_int_name = %s AND official_position = %s;",
                               (gov_int_name, official_position))
                existing_gov_int = cursor.fetchone()
                if existing_gov_int:
                    gov_int_id = existing_gov_int[0]
                else:
                    cursor.execute("""
                        INSERT INTO public_official_details (gov_int_name, official_position, branch_orgname)
                        VALUES (%s, %s, %s) RETURNING gov_int_id;
                    """, (gov_int_name, official_position, branch_orgname))
                    gov_int_id_row = cursor.fetchone()
                    if gov_int_id_row:
                        gov_int_id = gov_int_id_row[0]
                    else:
                        flash('Failed to create public official details record.', 'warning')
                
                if gov_int_id:
                    cursor.execute("""
                        INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc)
                        VALUES (%s, %s, %s);
                    """, (cust_no, gov_int_id, relation_desc))


            conn.commit()
            flash(f'Customer {cust_no} added successfully!', 'success')
            return redirect(url_for('admin_dashboard_page'))

        except psycopg2.IntegrityError as err:
            conn.rollback()
            print(f"Database Integrity Error during customer addition: {err}")
            if "customer_email_address_key" in str(err):
                flash('Email address already exists for another customer.', 'danger')
            else:
                flash(f'A database integrity error occurred: {err}', 'danger')
            if debug_mode:
                raise
            return redirect(url_for('admin_add_customer'))
        except psycopg2.Error as err:
            conn.rollback()
            print(f"Database error during customer addition: {err}")
            if debug_mode:
                raise
            flash(f'An error occurred: {err}', 'danger')
            return redirect(url_for('admin_add_customer'))
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error during customer addition: {e}")
            if debug_mode:
                raise
            flash('An unexpected error occurred during customer addition.', 'danger')
            return redirect(url_for('admin_add_customer'))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('admin_add_customer.html')


@app.route('/admin/edit_customer/<uuid:cust_no>', methods=['GET', 'POST'])
# @login_required # Assuming you have a login_required decorator
# @roles_required('Admin') # Assuming roles_required decorator
def admin_edit_customer(cust_no):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page'))

        cursor = conn.cursor()
        conn.autocommit = False # Start a transaction

        if request.method == 'POST':
            # Collect data from form
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            # Ensure custname is always set, combine first and last if available, else use existing/fallback
            custname = f"{first_name} {last_name}".strip() if first_name and last_name else request.form.get('custname')
            if not custname: # Fallback if combination is empty or not provided
                custname = request.form.get('custname', 'N/A')

            datebirth = request.form.get('dob')
            nationality = request.form.get('nationality')
            citizenship = request.form.get('citizenship')
            custsex = request.form.get('sex')
            placebirth = request.form.get('placeOfBirth')
            civilstatus = request.form.get('civilStatus')
            num_children = int(request.form.get('children', 0) or 0)
            mmaiden_name = request.form.get('motherMaidenName')
            cust_address = request.form.get('address')
            email_address = request.form.get('email')
            contact_no = request.form.get('telephone')
            registration_status = request.form.get('registrationStatus') # Get from form

            occ_type = request.form.get('occupation')
            bus_nature = request.form.get('natureOfBusiness')

            source_wealth_list = request.form.getlist('sourceOfWealth')
            source_wealth = ', '.join(source_wealth_list) if isinstance(source_wealth_list, list) else request.form.get('sourceOfWealth', '')
            mon_income = request.form.get('monthlyIncome')
            ann_income = request.form.get('annualIncome')

            # Fetch current occ_id and fin_code from the customer record
            cursor.execute("SELECT occ_id, fin_code FROM customer WHERE cust_no = %s;", (str(cust_no),))
            current_customer_fk_info = cursor.fetchone()
            
            if not current_customer_fk_info:
                flash(f'Customer with ID {cust_no} not found for update.', 'danger')
                conn.rollback()
                return redirect(url_for('admin_dashboard_page'))

            current_occ_id, current_fin_code = current_customer_fk_info

            # --- Update Occupation Table (or insert if new) ---
            occ_id_to_use = None
            if current_occ_id:
                # Try to update the existing occupation record
                cursor.execute("""
                    UPDATE occupation SET occ_type = %s, bus_nature = %s
                    WHERE occ_id = %s RETURNING occ_id;
                """, (occ_type, bus_nature, current_occ_id))
                updated_occ_row = cursor.fetchone()
                if updated_occ_row:
                    occ_id_to_use = updated_occ_row[0]
                else:
                    # If update failed (occ_id from customer didn't exist in occupation table)
                    # and new occupation data is provided, insert new.
                    if occ_type or bus_nature:
                        new_occ_id = uuid.uuid4() # Generate new UUID for new occupation
                        cursor.execute("""
                            INSERT INTO occupation (occ_id, occ_type, bus_nature) 
                            VALUES (%s, %s, %s) RETURNING occ_id;
                        """, (str(new_occ_id), occ_type, bus_nature))
                        inserted_occ_row = cursor.fetchone()
                        if inserted_occ_row:
                            occ_id_to_use = inserted_occ_row[0]
                            # Update customer to link to this new occupation
                            cursor.execute("""
                                UPDATE customer SET occ_id = %s WHERE cust_no = %s;
                            """, (occ_id_to_use, str(cust_no)))
                        else:
                            flash('Failed to insert new occupation record after old one not found.', 'warning')
                    else:
                        # If no new occupation data and old occ_id was invalid, set customer's occ_id to NULL
                        cursor.execute("""
                            UPDATE customer SET occ_id = NULL WHERE cust_no = %s;
                        """, (str(cust_no),))
            elif occ_type or bus_nature: # If customer had no occ_id, or old one was invalid, and new data is provided
                new_occ_id = uuid.uuid4() # Generate new UUID for new occupation
                cursor.execute("""
                    INSERT INTO occupation (occ_id, occ_type, bus_nature) 
                    VALUES (%s, %s, %s) RETURNING occ_id;
                """, (str(new_occ_id), occ_type, bus_nature))
                inserted_occ_row = cursor.fetchone()
                if inserted_occ_row:
                    occ_id_to_use = inserted_occ_row[0]
                    # Update customer to link to this new occupation
                    cursor.execute("""
                        UPDATE customer SET occ_id = %s WHERE cust_no = %s;
                    """, (occ_id_to_use, str(cust_no)))
                else:
                    flash('Failed to insert new occupation record.', 'warning')
            else: # No current occ_id, and no new occupation data provided
                occ_id_to_use = None
                # Ensure customer's occ_id is NULL if no occupation data
                cursor.execute("""
                    UPDATE customer SET occ_id = NULL WHERE cust_no = %s;
                """, (str(cust_no),))
            current_occ_id = occ_id_to_use # Update current_occ_id for subsequent use (e.g., employer details)


            # --- Update Financial Record Table (or insert if new) ---
            fin_code_to_use = None
            if current_fin_code:
                cursor.execute("""
                    UPDATE financial_record SET source_wealth = %s, mon_income = %s, ann_income = %s
                    WHERE fin_code = %s RETURNING fin_code;
                """, (source_wealth, mon_income, ann_income, current_fin_code))
                updated_fin_row = cursor.fetchone()
                if updated_fin_row:
                    fin_code_to_use = updated_fin_row[0]
                else:
                    # If update failed (fin_code from customer didn't exist in financial_record table)
                    # and new financial data is provided, insert new.
                    if source_wealth or mon_income or ann_income:
                        new_fin_code = uuid.uuid4() # Generate new UUID for new financial record
                        cursor.execute("""
                            INSERT INTO financial_record (fin_code, source_wealth, mon_income, ann_income)
                            VALUES (%s, %s, %s, %s) RETURNING fin_code;
                        """, (str(new_fin_code), source_wealth, mon_income, ann_income))
                        inserted_fin_row = cursor.fetchone()
                        if inserted_fin_row:
                            fin_code_to_use = inserted_fin_row[0]
                            # Update customer to link to this new financial record
                            cursor.execute("""
                                UPDATE customer SET fin_code = %s WHERE cust_no = %s;
                            """, (fin_code_to_use, str(cust_no)))
                        else:
                            flash('Failed to insert new financial record after old one not found.', 'warning')
                    else:
                        # If no new financial data and old fin_code was invalid, set customer's fin_code to NULL
                        cursor.execute("""
                            UPDATE customer SET fin_code = NULL WHERE cust_no = %s;
                        """, (str(cust_no),))
            elif source_wealth or mon_income or ann_income: # If customer had no fin_code, or old one was invalid, and new data is provided
                new_fin_code = uuid.uuid4() # Generate new UUID for new financial record
                cursor.execute("""
                    INSERT INTO financial_record (fin_code, source_wealth, mon_income, ann_income)
                    VALUES (%s, %s, %s, %s) RETURNING fin_code;
                """, (str(new_fin_code), source_wealth, mon_income, ann_income))
                inserted_fin_row = cursor.fetchone()
                if inserted_fin_row:
                    fin_code_to_use = inserted_fin_row[0]
                    # Update customer to link to this new financial record
                    cursor.execute("""
                        UPDATE customer SET fin_code = %s WHERE cust_no = %s;
                    """, (fin_code_to_use, str(cust_no)))
                else:
                    flash('Failed to insert new financial record.', 'warning')
            else: # No current fin_code, and no new financial data provided
                fin_code_to_use = None
                # Ensure customer's fin_code is NULL if no financial data
                cursor.execute("""
                    UPDATE customer SET fin_code = NULL WHERE cust_no = %s;
                """, (str(cust_no),))
            current_fin_code = fin_code_to_use # Update current_fin_code for subsequent use if any


            # --- Update Customer Table ---
            cursor.execute("""
                UPDATE customer
                SET custname = %s, datebirth = %s, nationality = %s, citizenship = %s, custsex = %s,
                    placebirth = %s, civilstatus = %s, num_children = %s, mmaiden_name = %s,
                    cust_address = %s, email_address = %s, contact_no = %s, registration_status = %s,
                    occ_id = %s, fin_code = %s
                WHERE cust_no = %s;
            """, (custname, datebirth, nationality, citizenship, custsex,
                  placebirth, civilstatus, int(num_children), mmaiden_name,
                  cust_address, email_address, contact_no, registration_status,
                  current_occ_id, current_fin_code, # Use the potentially new/updated IDs
                  str(cust_no)))
            
            # --- Update Employer Details if applicable ---
            # Only proceed if the occupation type is 'Employed' AND there's a valid occupation ID
            if occ_type == 'Employed' and current_occ_id:
                tin_id = request.form.get('tinId', '')
                empname = request.form.get('companyName', '')
                emp_address = request.form.get('employerAddress', '')
                phonefax_no = request.form.get('employerPhone', '')
                emp_date_str = request.form.get('employmentDate')
                emp_date = emp_date_str if emp_date_str else None
                job_title = request.form.get('jobTitle', '')

                # Check if an employer_details record already exists for this occ_id
                cursor.execute("SELECT emp_id FROM employer_details WHERE occ_id = %s;", (current_occ_id,))
                existing_emp_id_row = cursor.fetchone()

                emp_id_to_use = None
                if existing_emp_id_row:
                    emp_id = existing_emp_id_row[0]
                    # Update existing employer details
                    cursor.execute("""
                        UPDATE employer_details SET
                            tin_id = %s, empname = %s, emp_address = %s, phonefax_no = %s,
                            job_title = %s, emp_date = %s
                        WHERE emp_id = %s RETURNING emp_id;
                    """, (tin_id, empname, emp_address, phonefax_no,
                          job_title, emp_date, emp_id))
                    updated_emp_row = cursor.fetchone()
                    if updated_emp_row:
                        emp_id_to_use = updated_emp_row[0]
                    else:
                        flash('Failed to update existing employer details. Data inconsistency possible.', 'warning')
                else:
                    # Insert new employer details if not existing and current_occ_id is valid
                    new_emp_id = uuid.uuid4()
                    cursor.execute("""
                        INSERT INTO employer_details (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING emp_id;
                    """, (str(new_emp_id), current_occ_id, tin_id, empname, emp_address, phonefax_no,
                          job_title, emp_date))
                    inserted_emp_row = cursor.fetchone()
                    if inserted_emp_row:
                        emp_id_to_use = inserted_emp_row[0]
                    else:
                        flash('Failed to insert new employer details.', 'warning')

                # Update employment_details (link customer to employer)
                if emp_id_to_use:
                    cursor.execute("SELECT COUNT(*) FROM employment_details WHERE cust_no = %s AND emp_id = %s;",
                                   (str(cust_no), emp_id_to_use))
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s);",
                                       (str(cust_no), emp_id_to_use))
            elif occ_type != 'Employed': # If occupation is no longer 'Employed', remove related employer details
                # Remove links in employment_details
                cursor.execute("DELETE FROM employment_details WHERE cust_no = %s;", (str(cust_no),))
                # Remove employer_details if no other customer or no_occ_id points to it
                if current_occ_id: # Only try to delete if there was an occ_id
                    cursor.execute("""
                        DELETE FROM employer_details WHERE occ_id = %s AND NOT EXISTS (
                            SELECT 1 FROM employment_details WHERE emp_id = employer_details.emp_id
                        );
                    """, (current_occ_id,))


            # --- Update Spouse Details if civil status is Married ---
            if civilstatus == 'Married':
                sp_name = f"{request.form.get('spouseFirstName', '')} {request.form.get('spouseLastName', '')}".strip()
                sp_datebirth_str = request.form.get('spouseDob')
                sp_datebirth = sp_datebirth_str if sp_datebirth_str else None
                sp_profession = request.form.get('spouseProfession', '')

                if sp_name or sp_datebirth or sp_profession: # Only update/insert if spouse data is provided
                    # Check if spouse record already exists for this customer
                    cursor.execute("SELECT cust_no FROM spouse WHERE cust_no = %s;", (str(cust_no),))
                    existing_spouse = cursor.fetchone()

                    if existing_spouse:
                        cursor.execute("""
                            UPDATE spouse SET sp_name = %s, sp_datebirth = %s, sp_profession = %s
                            WHERE cust_no = %s;
                        """, (sp_name, sp_datebirth, sp_profession, str(cust_no)))
                    else:
                        cursor.execute("""
                            INSERT INTO spouse (cust_no, sp_name, sp_datebirth, sp_profession)
                            VALUES (%s, %s, %s, %s);
                        """, (str(cust_no), sp_name, sp_datebirth, sp_profession))
                else: # Civil status is Married, but no spouse details provided, delete if exists
                    cursor.execute("DELETE FROM spouse WHERE cust_no = %s;", (str(cust_no),))
            else: # Civil status is not Married, delete spouse record if exists
                cursor.execute("DELETE FROM spouse WHERE cust_no = %s;", (str(cust_no),))

            # --- Update Company Affiliation ---
            depositor_role = request.form.get('depositorRole')
            dep_compname = request.form.get('companyNameAffiliation')

            if depositor_role or dep_compname:
                cursor.execute("SELECT COUNT(*) FROM company_affiliation WHERE cust_no = %s;", (str(cust_no),))
                if cursor.fetchone()[0] > 0:
                    cursor.execute("""
                        UPDATE company_affiliation SET depositor_role = %s, dep_compname = %s
                        WHERE cust_no = %s;
                    """, (depositor_role, dep_compname, str(cust_no)))
                else:
                    cursor.execute("""
                        INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname)
                        VALUES (%s, %s, %s);
                    """, (str(cust_no), depositor_role, dep_compname))
            else:
                cursor.execute("DELETE FROM company_affiliation WHERE cust_no = %s;", (str(cust_no),))

            # --- Update Existing Bank Details ---
            bank_code = request.form.get('bankCode')
            acc_type = request.form.get('accountType')

            if bank_code and acc_type: # Bank code is a FK, must exist in bank_details
                # First, ensure the bank_code exists in bank_details table
                cursor.execute("SELECT bank_name FROM bank_details WHERE bank_code = %s;", (bank_code,))
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM existing_bank WHERE cust_no = %s AND bank_code = %s;",
                                   (str(cust_no), bank_code))
                    if cursor.fetchone()[0] > 0:
                        cursor.execute("""
                            UPDATE existing_bank SET acc_type = %s
                            WHERE cust_no = %s AND bank_code = %s;
                        """, (acc_type, str(cust_no), bank_code))
                    else:
                        cursor.execute("""
                            INSERT INTO existing_bank (cust_no, bank_code, acc_type)
                            VALUES (%s, %s, %s);
                        """, (str(cust_no), bank_code, acc_type))
                else:
                    flash('Invalid Bank Code. Please ensure the bank exists in the system.', 'danger')
            else:
                # If bank details are removed from form, delete them from DB
                cursor.execute("DELETE FROM existing_bank WHERE cust_no = %s;", (str(cust_no),))

            # --- Update Public Official Relationship ---
            gov_int_name = request.form.get('governmentOfficialName')
            official_position = request.form.get('officialPosition')
            branch_orgname = request.form.get('branchOrgName')
            relation_desc = request.form.get('relationshipNature')

            if gov_int_name or official_position or branch_orgname or relation_desc:
                # Check if public official detail exists or insert new
                gov_int_id_to_use = None
                cursor.execute("SELECT gov_int_id FROM public_official_details WHERE gov_int_name = %s AND official_position = %s;",
                               (gov_int_name, official_position))
                existing_gov_int = cursor.fetchone()

                if existing_gov_int:
                    gov_int_id_to_use = existing_gov_int[0]
                else:
                    new_gov_int_id = uuid.uuid4()
                    cursor.execute("""
                        INSERT INTO public_official_details (gov_int_id, gov_int_name, official_position, branch_orgname)
                        VALUES (%s, %s, %s, %s) RETURNING gov_int_id;
                    """, (str(new_gov_int_id), gov_int_name, official_position, branch_orgname))
                    inserted_gov_int_row = cursor.fetchone()
                    if inserted_gov_int_row:
                        gov_int_id_to_use = inserted_gov_int_row[0]
                    else:
                        flash('Failed to insert new public official details.', 'warning')

                if gov_int_id_to_use:
                    # Update or insert cust_po_relationship
                    cursor.execute("SELECT COUNT(*) FROM cust_po_relationship WHERE cust_no = %s AND gov_int_id = %s;",
                                   (str(cust_no), gov_int_id_to_use))
                    if cursor.fetchone()[0] > 0:
                        cursor.execute("""
                            UPDATE cust_po_relationship SET relation_desc = %s
                            WHERE cust_no = %s AND gov_int_id = %s;
                        """, (relation_desc, str(cust_no), gov_int_id_to_use))
                    else:
                        cursor.execute("""
                            INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc)
                            VALUES (%s, %s, %s);
                        """, (str(cust_no), gov_int_id_to_use, relation_desc))
            else:
                # If no public official details, delete any existing relationship
                cursor.execute("DELETE FROM cust_po_relationship WHERE cust_no = %s;", (str(cust_no),))
            
            conn.commit()
            flash(f'Customer {cust_no} updated successfully!', 'success')
            return redirect(url_for('admin_dashboard_page'))

        else: # GET request: Populate form with existing data
            cursor.execute("""
                SELECT
                    c.custname, c.datebirth, c.nationality, c.citizenship, c.custsex, c.placebirth,
                    c.civilstatus, c.num_children, c.mmaiden_name, c.cust_address, c.email_address,
                    c.contact_no, c.registration_status,
                    o.occ_type, o.bus_nature,
                    f.source_wealth, f.mon_income, f.ann_income,
                    e.tin_id, e.empname, e.emp_address, e.phonefax_no, e.job_title, e.emp_date,
                    s.sp_name, s.sp_datebirth, s.sp_profession,
                    comp.depositor_role, comp.dep_compname,
                    eb.bank_code, eb.acc_type,
                    po.gov_int_name, po.official_position, po.branch_orgname,
                    cpr.relation_desc
                FROM customer c
                LEFT JOIN occupation o ON c.occ_id = o.occ_id
                LEFT JOIN financial_record f ON c.fin_code = f.fin_code
                LEFT JOIN employment_details emd ON c.cust_no = emd.cust_no
                LEFT JOIN employer_details e ON emd.emp_id = e.emp_id
                LEFT JOIN spouse s ON c.cust_no = s.cust_no
                LEFT JOIN company_affiliation comp ON c.cust_no = comp.cust_no
                LEFT JOIN existing_bank eb ON c.cust_no = eb.cust_no
                LEFT JOIN cust_po_relationship cpr ON c.cust_no = cpr.cust_no
                LEFT JOIN public_official_details po ON cpr.gov_int_id = po.gov_int_id
                WHERE c.cust_no = %s;
            """, (str(cust_no),))
            
            customer_data = cursor.fetchone()

            if not customer_data:
                flash('Customer not found.', 'danger')
                return redirect(url_for('admin_dashboard_page'))

            # Convert row to dictionary for easier access in template
            columns = [desc[0] for desc in cursor.description]
            customer = dict(zip(columns, customer_data))

            # Split custname into first and last for form
            full_name = customer.get('custname', '').strip()
            name_parts = full_name.rsplit(' ', 1)
            customer['firstName'] = name_parts[0] if len(name_parts) > 1 else full_name
            customer['lastName'] = name_parts[1] if len(name_parts) > 1 else ''

            # Split spouse name
            spouse_full_name = customer.get('sp_name', '').strip()
            spouse_name_parts = spouse_full_name.rsplit(' ', 1)
            customer['spouseFirstName'] = spouse_name_parts[0] if len(spouse_name_parts) > 1 else spouse_full_name
            customer['spouseLastName'] = spouse_name_parts[1] if len(spouse_name_parts) > 1 else ''

            # Format dates for HTML input
            if customer.get('datebirth'):
                customer['datebirth'] = customer['datebirth'].isoformat()
            if customer.get('emp_date'):
                customer['emp_date'] = customer['emp_date'].isoformat()
            if customer.get('sp_datebirth'):
                customer['sp_datebirth'] = customer['sp_datebirth'].isoformat()
            
            # Convert source_wealth string back to list for checkboxes if needed, or handle in template
            if customer.get('source_wealth'):
                customer['sourceOfWealthList'] = [s.strip() for s in customer['source_wealth'].split(',')]
            else:
                customer['sourceOfWealthList'] = []

            return render_template('admin_edit_customer.html', customer=customer, cust_no=str(cust_no))

    except psycopg2.Error as err:
        conn.rollback()
        print(f"Database error during customer edit: {err}")
        if debug_mode:
            raise
        flash(f'An error occurred: {err}', 'danger')
        return redirect(url_for('admin_dashboard_page'))
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error during customer edit: {e}")
        if debug_mode:
            raise
        flash('An unexpected error occurred during customer edit.', 'danger')
        return redirect(url_for('admin_dashboard_page'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- Customer Dashboard ---
@app.route('/customer_dashboard')
@login_required
@roles_required('Customer') # Only accessible by regular customers
def customer_dashboard_page():
    # Placeholder for customer-specific data display or actions
    return render_template('customer_dashboard.html', username=session.get('username'))

@app.route('/delete_customer/<uuid:cust_no>', methods=['POST'])
@login_required
@roles_required('Admin')
def delete_customer(cust_no):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page'))

        cursor = conn.cursor()
        conn.autocommit = False # Start a transaction for deletion

        # Get related IDs before deleting the customer
        cursor.execute("SELECT occ_id, fin_code FROM customer WHERE cust_no = %s;", (str(cust_no),))
        customer_fks = cursor.fetchone()

        occ_id = None
        fin_code = None
        if customer_fks:
            occ_id = customer_fks[0]
            fin_code = customer_fks[1]

        # Delete from tables that have foreign keys referencing customer (ON DELETE CASCADE will handle many)
        # For tables with ON DELETE SET NULL, no explicit deletion is needed here,
        # but if we want to clean up orphaned records in occ and fin, we do it after customer deletion.

        # Delete related employer details if this customer is the only one linked to its occupation
        if occ_id:
            cursor.execute("SELECT emp_id FROM employer_details WHERE occ_id = %s;", (occ_id,))
            employer_ids = cursor.fetchall() # Get all employer_ids linked to this occ_id
            
            for emp_id_tuple in employer_ids:
                emp_id = emp_id_tuple[0]
                cursor.execute("SELECT COUNT(*) FROM employment_details WHERE emp_id = %s;", (emp_id,))
                if cursor.fetchone()[0] == 1: # If this is the only customer linked to this employer_id
                    cursor.execute("DELETE FROM employer_details WHERE emp_id = %s;", (emp_id,))
            
        # Delete the customer record (this should cascade delete credentials, spouse, company_affiliation, existing_bank, cust_po_relationship, employment_details)
        cursor.execute("DELETE FROM customer WHERE cust_no = %s;", (str(cust_no),))

        # After customer deletion, check if occ_id and fin_code are still referenced by any other customer
        if fin_code:
            cursor.execute("SELECT COUNT(*) FROM customer WHERE fin_code = %s", (fin_code,))
            if cursor.fetchone()[0] == 0: 
                cursor.execute("DELETE FROM financial_record WHERE fin_code = %s", (fin_code,))
        
        if occ_id:
            cursor.execute("SELECT COUNT(*) FROM customer WHERE occ_id = %s", (occ_id,))
            if cursor.fetchone()[0] == 0: 
                cursor.execute("DELETE FROM occupation WHERE occ_id = %s", (occ_id,))

        conn.commit() 
        flash(f'Customer {cust_no} and all related records deleted successfully!', 'success')
        return redirect(url_for('admin_dashboard_page')) 

    except psycopg2.Error as err:
        conn.rollback() 
        print(f"Database error during customer deletion: {err}")
        if debug_mode:
            raise
        flash(f'An error occurred during deletion: {err}', 'danger')
        return redirect(url_for('admin_dashboard_page')) 
    except Exception as e:
        if conn: 
            conn.rollback()
        print(f"Error during customer deletion: {e}")
        if debug_mode:
            raise
        flash('An unexpected error occurred during customer deletion.', 'danger')
        return redirect(url_for('admin_dashboard_page')) 
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# --- Main execution block ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)) 
    _ensure_database_schema() # Ensure schema on startup
    app.run(debug=debug_mode, host='0.0.0.0', port=port) # Use 0.0.0.0 for Render deployment
