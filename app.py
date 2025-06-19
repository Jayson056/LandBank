import psycopg2 # Changed from mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid # For generating unique IDs
import os # To access environment variables
import psycopg2.extras # Import DictCursor for dictionary results

# Import the get_db_url function from db_config
from db_config import get_db_url

app = Flask(__name__)
# IMPORTANT: Change this to a strong, unique secret key for production environments
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_here') # Use environment variable for secret key

# Determine debug mode from environment variable. This allows more verbose errors in development.
debug_mode = os.environ.get('FLASK_DEBUG', 'True') == 'True'

def get_db_connection():
    """Establishes and returns a database connection using psycopg2 for PostgreSQL."""
    try:
        conn_url = get_db_url()
        # psycopg2 can connect using a full connection string (URL)
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
                    mon_income TEXT, -- Intended type
                    ann_income TEXT -- Intended type
                );
            """,
            'bank_details': """
                CREATE TABLE IF NOT EXISTS bank_details (
                    bank_code VARCHAR(10) PRIMARY KEY, -- Keeping VARCHAR(10) as it's likely an external code
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
                    email_address VARCHAR(255) UNIQUE, -- Email should likely be unique
                    contact_no VARCHAR(20),
                    occ_id UUID,
                    fin_code UUID,
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
                    PRIMARY KEY (cust_no, username) -- Composite primary key
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
                    PRIMARY KEY (cust_no, depositor_role, dep_compname) -- Composite key for uniqueness
                );
            """,
            'existing_bank': """
                CREATE TABLE IF NOT EXISTS existing_bank (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    bank_code VARCHAR(10) REFERENCES bank_details (bank_code) ON DELETE CASCADE,
                    acc_type VARCHAR(255),
                    PRIMARY KEY (cust_no, bank_code, acc_type) -- Composite key for uniqueness
                );
            """,
            'cust_po_relationship': """
                CREATE TABLE IF NOT EXISTS cust_po_relationship (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    gov_int_id UUID REFERENCES public_official_details (gov_int_id) ON DELETE CASCADE,
                    relation_desc VARCHAR(255),
                    PRIMARY KEY (cust_no, gov_int_id) -- Composite primary key
                );
            """,
            'employment_details': """
                CREATE TABLE IF NOT EXISTS employment_details (
                    cust_no UUID REFERENCES customer (cust_no) ON DELETE CASCADE,
                    emp_id UUID REFERENCES employer_details (emp_id) ON DELETE CASCADE,
                    PRIMARY KEY (cust_no, emp_id) -- Composite primary key
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
            conn.rollback() # Rollback if extension creation failed

        for table_name, create_sql in schema_sql.items():
            try:
                print(f"  - Ensuring table: {table_name}")
                cursor.execute(create_sql)
                conn.commit() # Commit each table creation to ensure it's saved
                print(f"  - Table '{table_name}' checked/created successfully.")
            except psycopg2.Error as err:
                print(f"  - ERROR creating/checking table {table_name}: {err}")
                conn.rollback() # Rollback on error for this table
        
        # --- NEW ALTER TABLE LOGIC ---
        # This section will attempt to alter the financial_record columns if they are not TEXT.
        # This is a simplified approach for schema evolution. For production, consider Alembic.
        try:
            # Check current type of mon_income
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

            # Check current type of ann_income
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

        except psycopg2.Error as alter_err:
            print(f"  - ERROR during ALTER TABLE for financial_record: {alter_err}")
            conn.rollback()
        except Exception as e:
            print(f"  - Unexpected error during ALTER TABLE check: {e}")
            conn.rollback()
        # --- END NEW ALTER TABLE LOGIC ---


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


# --- Page Routes (existing routes, unchanged, but now uses PostgreSQL connection) ---
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

        # Use cursor factory for dictionary results if needed, otherwise default
        cursor = conn.cursor()
        conn.autocommit = False # Start a transaction

        # --- 1. Insert into occupation table ---
        # PostgreSQL will generate UUID automatically if DEFAULT gen_random_uuid() is used
        # We can optionally pass it or let DB handle. Here, we'll let DB handle for UUID columns.
        occ_type = r2.get('occupation')
        bus_nature = r2.get('natureOfBusiness')
        sql_occ = "INSERT INTO occupation (occ_type, bus_nature) VALUES (%s, %s) RETURNING occ_id;"
        cursor.execute(sql_occ, (occ_type, bus_nature))
        occ_id = cursor.fetchone()[0] # Fetch the generated UUID

        # --- 2. Insert into financial_record table ---
        source_wealth_list = r2.get('sourceOfWealth', [])
        source_wealth = ', '.join(source_wealth_list) if isinstance(source_wealth_list, list) else source_wealth_list
        # Ensure mon_income and ann_income are handled as TEXT
        mon_income = r2.get('monthlyIncome')
        ann_income = r2.get('annualIncome')
        sql_fin = "INSERT INTO financial_record (source_wealth, mon_income, ann_income) VALUES (%s, %s, %s) RETURNING fin_code;"
        cursor.execute(sql_fin, (source_wealth, mon_income, ann_income))
        fin_code = cursor.fetchone()[0] # Fetch the generated UUID

        # --- 3. Insert into customer table ---
        # cust_no will be generated by the database via DEFAULT gen_random_uuid()
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

        sql_cust = """INSERT INTO customer (custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, occ_id, fin_code)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING cust_no;"""
        customer_data = (
            custname, datebirth, nationality, citizenship,
            custsex, placebirth, civilstatus,
            num_children,
            mmaiden_name, cust_address,
            email_address, contact_no, occ_id, fin_code
        )

        cursor.execute(sql_cust, customer_data)
        cust_no = cursor.fetchone()[0] # Fetch the generated UUID for cust_no

        print(f"--- DEBUG: Successfully inserted customer. New cust_no: {cust_no} (Type: {type(cust_no)}) ---")

        # --- 4. Insert into employer_details and employment_details if applicable ---
        if r2.get('occupation') == 'Employed':
            # emp_id will be generated by the database
            tin_id = r2.get('tinId', '')
            empname = r2.get('companyName', '')
            emp_address = r2.get('employerAddress', '')
            phonefax_no = r2.get('employerPhone', '')
            job_title = r2.get('jobTitle', '')
            emp_date = r2.get('employmentDate') or '2000-01-01'

            sql_emp_details = "INSERT INTO employer_details (occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING emp_id;"
            cursor.execute(sql_emp_details, (occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))
            emp_id = cursor.fetchone()[0] # Fetch the generated UUID

            sql_emp_link = "INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s)"
            cursor.execute(sql_emp_link, (cust_no, emp_id))

        # --- 5. Insert into spouse table if married ---
        if r1.get('civilStatus') == 'Married':
            sp_name = f"{r1.get('spouseFirstName', '')} {r1.get('spouseLastName', '')}"
            sp_datebirth = r1.get('spouseDob')
            sp_profession = r1.get('spouseProfession')
            if sp_name.strip() and sp_datebirth and sp_profession:
                sql_spouse = "INSERT INTO spouse (cust_no, sp_name, sp_datebirth, sp_profession) VALUES (%s, %s, %s, %s) ON CONFLICT (cust_no) DO UPDATE SET sp_name = EXCLUDED.sp_name, sp_datebirth = EXCLUDED.sp_datebirth, sp_profession = EXCLUDED.sp_profession;"
                cursor.execute(sql_spouse, (cust_no, sp_name, sp_datebirth, sp_profession))

        # --- 6. Insert into company_affiliation ---
        roles = r3.get('depositorRole', [])
        companies = r3.get('companyName', [])
        if not isinstance(roles, list): roles = [roles] if roles else []
        if not isinstance(companies, list): companies = [companies] if companies else []

        for role, company in zip(roles, companies):
            if role and company:
                sql_comp_aff = "INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname) VALUES (%s, %s, %s) ON CONFLICT (cust_no, depositor_role, dep_compname) DO NOTHING;"
                cursor.execute(sql_comp_aff, (cust_no, role, company))

        # --- 7. Insert into bank_details and existing_bank ---
        banks = r3.get('bank', [])
        branches = r3.get('branch', [])
        acc_types = r3.get('accountType', [])
        if not isinstance(banks, list): banks = [banks] if banks else []
        if not isinstance(branches, list): branches = [branches] if branches else []
        if not isinstance(acc_types, list): acc_types = [acc_types] if acc_types else []

        for bank_name, branch, acc_type in zip(banks, branches, acc_types):
            if bank_name and branch and acc_type:
                # Use ON CONFLICT DO NOTHING for bank_details instead of INSERT IGNORE
                sql_insert_bank = "INSERT INTO bank_details (bank_code, bank_name, branch) VALUES (%s, %s, %s) ON CONFLICT (bank_code) DO NOTHING;"
                cursor.execute(sql_insert_bank, (bank_name, bank_name, branch))

                sql_existing_bank = "INSERT INTO existing_bank (cust_no, bank_code, acc_type) VALUES (%s, %s, %s) ON CONFLICT (cust_no, bank_code, acc_type) DO NOTHING;"
                cursor.execute(sql_existing_bank, (cust_no, bank_name, acc_type))

        # --- 8. Insert into public_official_details and cust_po_relationship ---
        gov_last_names = r3.get('govLastName', [])
        gov_first_names = r3.get('govFirstName', [])
        relationships = r3.get('relationship', [])
        positions = r3.get('position', [])
        org_names = r3.get('govBranchOrgName', [])

        if not isinstance(gov_last_names, list): gov_last_names = [gov_last_names] if gov_last_names else []
        if not isinstance(gov_first_names, list): gov_first_names = [gov_first_names] if gov_first_names else []
        if not isinstance(relationships, list): relationships = [relationships] if relationships else []
        if not isinstance(positions, list): positions = [positions] if positions else []
        if not isinstance(org_names, list): org_names = [org_names] if org_names else []

        min_len = min(len(gov_last_names), len(gov_first_names), len(relationships), len(positions), len(org_names))
        for i in range(min_len):
            if gov_last_names[i] and gov_first_names[i] and relationships[i] and positions[i] and org_names[i]:
                # gov_int_id will be generated by the database
                gov_name = f"{gov_first_names[i]} {gov_last_names[i]}"
                sql_po_details = "INSERT INTO public_official_details (gov_int_name, official_position, branch_orgname) VALUES (%s, %s, %s) RETURNING gov_int_id;"
                cursor.execute(sql_po_details, (gov_name, positions[i], org_names[i]))
                gov_int_id = cursor.fetchone()[0] # Fetch the generated UUID

                sql_po_rel = "INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc) VALUES (%s, %s, %s) ON CONFLICT (cust_no, gov_int_id) DO NOTHING;"
                cursor.execute(sql_po_rel, (cust_no, gov_int_id, relationships[i]))

        # --- 9. Call insert_credentials here to save username and password ---
        insert_credentials(cursor, cust_no, r1)

        conn.commit() # Commit the entire transaction
        return '', 200

    except psycopg2.Error as err:
        if conn:
            conn.rollback()
        print(f"Error during registration submission: {err}")
        return f"Database error during submission: {err}", 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Unexpected error during registration submission: {e}")
        return f"An unexpected error occurred: {e}", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- Helper Function Definitions (Called from submit_registration) ---
def insert_credentials(cursor, cust_no, data):
    """
    Inserts user credentials into the credentials table.
    """
    username = data.get('email')
    # IMPORTANT: In a real application, you MUST hash passwords.
    # For now, using a default password based on cust_no for demonstration.
    password = f"defaultPass{cust_no}"

    sql = """
        INSERT INTO credentials (cust_no, username, password)
        VALUES (%s, %s, %s)
        ON CONFLICT (cust_no, username) DO UPDATE SET password = EXCLUDED.password;
    """
    cursor.execute(sql, (str(cust_no), username, password)) # Cast UUID to string for psycopg2

# --- Placeholder for other Flask routes and functions ---
@app.route('/userHome')
def userHome():
    if 'cust_no' not in session:
        flash('Please log in to access this page.', 'info')
        return redirect(url_for('login'))

    cust_no = session['cust_no']
    conn = None
    cursor = None
    user_data = {}

    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return render_template('login.html', error='Database connection failed.')

        # Use cursor_factory to get dictionary results for easier access
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Fetch Customer Information
        cursor.execute("""
            SELECT c.*, o.occ_type, o.bus_nature, f.source_wealth, f.mon_income, f.ann_income
            FROM customer c
            LEFT JOIN occupation o ON c.occ_id = o.occ_id
            LEFT JOIN financial_record f ON c.fin_code = f.fin_code
            WHERE c.cust_no = %s
        """, (cust_no,))
        user_data['customer'] = cursor.fetchone()

        if not user_data['customer']:
            flash('Customer data not found.', 'danger')
            return redirect(url_for('login'))

        # Separate the fetched data for clarity in the template, though already joined
        user_data['occupation'] = {
            'occ_type': user_data['customer'].get('occ_type'),
            'bus_nature': user_data['customer'].get('bus_nature')
        }
        user_data['financial_record'] = {
            'source_wealth': user_data['customer'].get('source_wealth'),
            'mon_income': user_data['customer'].get('mon_income'),
            'ann_income': user_data['customer'].get('ann_income')
        }

        # Fetch Spouse Information (if exists)
        cursor.execute("SELECT * FROM spouse WHERE cust_no = %s", (cust_no,))
        user_data['spouse'] = cursor.fetchone()

        # Fetch Employer Details (if exists, linked via employment_details and occupation)
        if user_data['occupation']['occ_type'] == 'Employed':
            cursor.execute("""
                SELECT ed.*
                FROM employer_details ed
                JOIN employment_details empd ON ed.emp_id = empd.emp_id
                WHERE empd.cust_no = %s
            """, (cust_no,))
            user_data['employer_details'] = cursor.fetchone()
        else:
            user_data['employer_details'] = None

        # Fetch Company Affiliations
        cursor.execute("SELECT * FROM company_affiliation WHERE cust_no = %s", (cust_no,))
        user_data['company_affiliations'] = cursor.fetchall()

        # Fetch Existing Bank Accounts
        cursor.execute("""
            SELECT eb.acc_type, bd.bank_name, bd.branch
            FROM existing_bank eb
            JOIN bank_details bd ON eb.bank_code = bd.bank_code
            WHERE eb.cust_no = %s
        """, (cust_no,))
        user_data['existing_banks'] = cursor.fetchall()

        # Fetch Public Official Relationships
        cursor.execute("""
            SELECT cpr.relation_desc, pod.gov_int_name, pod.official_position, pod.branch_orgname
            FROM cust_po_relationship cpr
            JOIN public_official_details pod ON cpr.gov_int_id = pod.gov_int_id
            WHERE cpr.cust_no = %s
        """, (cust_no,))
        user_data['public_official_relationships'] = cursor.fetchall()

        return render_template('admin_view_customer.html', user_data=user_data)

    except psycopg2.Error as err:
        print(f"Database error in admin_view_customer: {err}")
        flash(f'An error occurred while fetching customer data: {err}', 'danger')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print(f"Error in admin_view_customer: {e}")
        flash('An unexpected error occurred while loading customer details.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- NEW ROUTE: Admin Edit Customer Details ---
@app.route('/admin/edit_customer/<uuid:cust_no>', methods=['GET', 'POST']) # Use <uuid:cust_no>
def admin_edit_customer(cust_no):
    if 'admin' not in session:
        flash('Please login to access the admin dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    customer_data = {} # Will hold all fetched data for the customer

    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard'))

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if request.method == 'POST':
            # --- Handle form submission for UPDATE ---
            # IMPORTANT: Implement your update logic here.
            # This is a placeholder. You'll need to get form data and update
            # all relevant tables (customer, spouse, financial_record, etc.)
            # Example:
            # new_custname = request.form.get('custname')
            # cursor.execute("UPDATE customer SET custname = %s WHERE cust_no = %s", (new_custname, cust_no))
            # conn.commit()
            flash('Customer update logic is not yet fully implemented for POST. Displaying current data.', 'info')
            return redirect(url_for('admin_view_customer', cust_no=cust_no))
        
        # --- Handle GET request (and fall-through from POST) for displaying current data ---
        # Fetch Customer Information
        cursor.execute("""
            SELECT c.*, o.occ_type, o.bus_nature, f.source_wealth, f.mon_income, f.ann_income
            FROM customer c
            LEFT JOIN occupation o ON c.occ_id = o.occ_id
            LEFT JOIN financial_record f ON c.fin_code = f.fin_code
            WHERE c.cust_no = %s
        """, (cust_no,))
        customer_data['customer'] = cursor.fetchone()

        if not customer_data['customer']:
            flash(f'Customer with ID {cust_no} not found.', 'danger')
            return redirect(url_for('admin_dashboard'))

        # Separate the fetched data for clarity in the template
        customer_data['occupation'] = {
            'occ_type': customer_data['customer'].get('occ_type'),
            'bus_nature': customer_data['customer'].get('bus_nature')
        }
        customer_data['financial_record'] = {
            'source_wealth': customer_data['customer'].get('source_wealth'),
            'mon_income': customer_data['customer'].get('mon_income'),
            'ann_income': customer_data['customer'].get('ann_income')
        }

        # Fetch Spouse Information (if exists)
        cursor.execute("SELECT * FROM spouse WHERE cust_no = %s", (cust_no,))
        customer_data['spouse'] = cursor.fetchone()

        # Fetch Employer Details (if exists and occupation is 'Employed')
        if customer_data['occupation']['occ_type'] == 'Employed':
            cursor.execute("""
                SELECT ed.*
                FROM employer_details ed
                JOIN employment_details empd ON ed.emp_id = empd.emp_id
                WHERE empd.cust_no = %s
            """, (cust_no,))
            customer_data['employer_details'] = cursor.fetchone()
        else:
            customer_data['employer_details'] = None

        # Fetch Company Affiliations
        cursor.execute("SELECT * FROM company_affiliation WHERE cust_no = %s", (cust_no,))
        customer_data['company_affiliations'] = cursor.fetchall()

        # Fetch Existing Bank Accounts
        cursor.execute("""
            SELECT eb.acc_type, bd.bank_name, bd.branch
            FROM existing_bank eb
            JOIN bank_details bd ON eb.bank_code = bd.bank_code
            WHERE eb.cust_no = %s
        """, (cust_no,))
        customer_data['existing_banks'] = cursor.fetchall()

        # Fetch Public Official Relationships
        cursor.execute("""
            SELECT cpr.relation_desc, pod.gov_int_name, pod.official_position, pod.branch_orgname
            FROM cust_po_relationship cpr
            JOIN public_official_details pod ON cpr.gov_int_id = pod.gov_int_id
            WHERE cpr.cust_no = %s
        """, (cust_no,))
        customer_data['public_official_relationships'] = cursor.fetchall()

        return render_template('admin_edit_customer.html', customer_data=customer_data)

    except psycopg2.Error as err:
        print(f"Database error in admin_edit_customer: {err}")
        flash(f'An error occurred while fetching customer data: {err}', 'danger')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print(f"Error in admin_edit_customer: {e}")
        flash('An unexpected error occurred while loading customer details for editing.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- NEW ROUTE: Delete Customer ---
@app.route('/delete_customer', methods=['POST'])
def delete_customer():
    if 'admin' not in session:
        flash('Please login to access this function.', 'warning')
        return redirect(url_for('login'))

    cust_no = request.form.get('cust_no')
    if not cust_no:
        flash('Customer ID is missing for deletion.', 'danger')
        return redirect(url_for('admin_dashboard'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard'))

        cursor = conn.cursor()
        conn.autocommit = False # Start a transaction

        # PostgreSQL handles CASCADE deletes via foreign key constraints,
        # so explicit deletions from child tables are often not strictly needed
        # if the foreign keys are set up with ON DELETE CASCADE.
        # However, to explicitly handle related record deletion and orphaned records:

        # 1. Get occ_id and fin_code before deleting the customer
        cursor.execute("SELECT fin_code, occ_id FROM customer WHERE cust_no = %s", (cust_no,))
        customer_info = cursor.fetchone()
        fin_code = customer_info[0] if customer_info else None
        occ_id = customer_info[1] if customer_info else None

        # 2. Delete the customer record. This will trigger CASCADE deletes for:
        #    - credentials
        #    - cust_po_relationship
        #    - existing_bank
        #    - company_affiliation
        #    - employment_details
        #    - spouse
        # if foreign keys are set up with ON DELETE CASCADE.
        # You might still need to explicitly delete from employer_details,
        # financial_record, and occupation if they are not exclusively linked
        # or if their foreign keys are ON DELETE SET NULL.
        cursor.execute("DELETE FROM customer WHERE cust_no = %s", (cust_no,))
        
        # 3. Handle employer_details (if it's not cascaded from employment_details, or if emp_id can become orphaned)
        # Check if the emp_id is referenced by any other employment_details records *before* deleting customer.
        # If not, and it was associated with this customer, delete it.
        # This part assumes employer_details might not cascade from customer directly.
        # Original code had logic for this, adapt for PostgreSQL:
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
        return redirect(url_for('admin_dashboard'))

    except psycopg2.Error as err:
        conn.rollback()
        print(f"Database error during customer deletion: {err}")
        flash(f'An error occurred during deletion: {err}', 'danger')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error during customer deletion: {e}")
        flash('An unexpected error occurred during customer deletion.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# --- Main execution block ---
if __name__ == '__main__':
    # For Render, the PORT will be provided by an environment variable
    port = int(os.environ.get('PORT', 0000))
    # In a production environment, debug should be False
    debug_mode = os.environ.get('FLASK_DEBUG', 'True') == 'True'

    _ensure_database_schema() # Run schema check/update on app startup
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

