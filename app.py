import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid # For generating unique IDs like cust_no and other VARCHAR IDs

app = Flask(__name__)
# IMPORTANT: Change this to a strong, unique secret key for production environments
app.secret_key = 'your_super_secret_key_here'

# Database configuration
db_config = {
    'host': '127.0.0.1',  # Use 127.0.0.1 for local MySQL, or your database host
    'port': '3306',
    'user': 'root',
    'password': 'LandBank@2025',  # Your MySQL root password
    'database': 'database_landbank'
}

def get_db_connection():
    """Establishes and returns a database connection using mysql.connector."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- Function to Ensure Database Schema (for development/initial setup) ---
def _ensure_database_schema():
    """
    Ensures that necessary database columns have appropriate lengths and types (VARCHAR for IDs).
    This function should typically be run only once, or managed by a proper migration tool.
    For development, it runs on app startup.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to get database connection for schema update.")
            return

        cursor = conn.cursor()
        print("Attempting to ensure database schema (column lengths and types)...\n")

        # Define schema for relevant tables and columns, explicitly setting VARCHAR lengths
        schema_updates = {
            'customer': {
                'cust_no': 'VARCHAR(10) NOT NULL PRIMARY KEY',
                'custname': 'VARCHAR(255)',
                'email_address': 'VARCHAR(255)',
                'contact_no': 'VARCHAR(20)',
                'occ_id': 'VARCHAR(10)',
                'fin_code': 'VARCHAR(10)'
            },
            'occupation': {
                'occ_id': 'VARCHAR(10) NOT NULL PRIMARY KEY',
                'occ_type': 'VARCHAR(255)',
                'bus_nature': 'VARCHAR(255)'
            },
            'financial_record': {
                'fin_code': 'VARCHAR(10) NOT NULL PRIMARY KEY',
                'source_wealth': 'VARCHAR(255)',
                'mon_income': 'VARCHAR(255)', # Ensure this is VARCHAR
                'ann_income': 'VARCHAR(255)'  # Ensure this is VARCHAR
            },
            'credentials': {
                'cust_no': 'VARCHAR(10) NOT NULL',
                'username': 'VARCHAR(255)',
                'password': 'VARCHAR(255)'
            },
            'employer_details': {
                'emp_id': 'VARCHAR(10) NOT NULL PRIMARY KEY',
                'occ_id': 'VARCHAR(10)',
                'tin_id': 'VARCHAR(50)',
                'empname': 'VARCHAR(255)',
                'emp_address': 'VARCHAR(255)',
                'phonefax_no': 'VARCHAR(50)',
                'job_title': 'VARCHAR(255)',
                'emp_date': 'DATE'
            },
            'public_official_details': {
                'gov_int_id': 'VARCHAR(10) NOT NULL PRIMARY KEY',
                'gov_int_name': 'VARCHAR(255)',
                'official_position': 'VARCHAR(255)',
                'branch_orgname': 'VARCHAR(255)'
            },
            'cust_po_relationship': {
                'relation_desc': 'VARCHAR(255)' # Ensure this is VARCHAR
            },
            'spouse': {
                'cust_no': 'VARCHAR(10)',
                'sp_name': 'VARCHAR(255)',
                'sp_datebirth': 'DATE',
                'sp_profession': 'VARCHAR(255)'
            },
            'company_affiliation': {
                'cust_no': 'VARCHAR(10)',
                'depositor_role': 'VARCHAR(255)',
                'dep_compname': 'VARCHAR(255)'
            },
            'bank_details': {
                'bank_code': 'VARCHAR(10) NOT NULL PRIMARY KEY',
                'bank_name': 'VARCHAR(255)',
                'branch': 'VARCHAR(255)'
            },
            'existing_bank': {
                'cust_no': 'VARCHAR(10)',
                'bank_code': 'VARCHAR(10)',
                'acc_type': 'VARCHAR(255)'
            },
            'employment_details': {
                'cust_no': 'VARCHAR(10)',
                'emp_id': 'VARCHAR(10)'
            }
        }

        for table, columns in schema_updates.items():
            try:
                # Check if table exists
                cursor.execute(f"SHOW TABLES LIKE '{table}'")
                table_exists = cursor.fetchone()

                if not table_exists:
                    print(f"  - WARNING: Table '{table}' does not exist. Skipping schema update for this table.")
                    continue

                cursor.execute(f"DESCRIBE {table}")
                existing_columns_info = cursor.fetchall()
                existing_columns_map = {col[0]: {'type': col[1].decode('utf-8').upper(), 'null': col[2].decode('utf-8').upper(), 'key': col[3].decode('utf-8').upper()} for col in existing_columns_info}

                for col_name, desired_col_def in columns.items():
                    if col_name in existing_columns_map:
                        existing_type_info = existing_columns_map[col_name]
                        # Simplified check for VARCHAR type and length, and NOT NULL/PRIMARY KEY
                        # This comparison is robust for exact type match (e.g., VARCHAR(10) vs VARCHAR(20))
                        if existing_type_info['type'] != desired_col_def.upper().split(' ')[0] and 'VARCHAR' in desired_col_def.upper():
                             # Special handling for VARCHAR where length might differ but type is still VARCHAR
                             current_type_base = existing_type_info['type'].split('(')[0]
                             desired_type_base = desired_col_def.split('(')[0].upper()
                             if current_type_base == desired_type_base:
                                 # If base type is VARCHAR, check full definition (e.g., VARCHAR(10) vs VARCHAR(255))
                                 if existing_type_info['type'] != desired_col_def.upper():
                                     try:
                                         cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} {desired_col_def};")
                                         print(f"  - Altered {table}.{col_name} to {desired_col_def} (type/length mismatch corrected)")
                                     except mysql.connector.Error as alter_err:
                                         print(f"  - WARNING: Could not alter {table}.{col_name} for type/length: {alter_err}")
                                 else:
                                     print(f"  - {table}.{col_name} already matches '{desired_col_def}'")
                             else: # Different base type (e.g., INT to VARCHAR)
                                 try:
                                     cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} {desired_col_def};")
                                     print(f"  - Altered {table}.{col_name} to {desired_col_def} (base type changed)")
                                 except mysql.connector.Error as alter_err:
                                     print(f"  - WARNING: Could not alter {table}.{col_name} for base type: {alter_err}")
                        elif existing_type_info['type'] != desired_col_def.upper(): # For non-VARCHAR or exact type check
                            try:
                                cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN {col_name} {desired_col_def};")
                                print(f"  - Altered {table}.{col_name} to {desired_col_def}")
                            except mysql.connector.Error as alter_err:
                                print(f"  - WARNING: Could not alter {table}.{col_name}: {alter_err}")
                        else:
                            print(f"  - {table}.{col_name} already matches '{desired_col_def}'")
                    else:
                        print(f"  - WARNING: Column '{col_name}' not found in table '{table}'. Skipping alter for this column.")

            except mysql.connector.Error as desc_err:
                print(f"  - WARNING: Error describing table {table}: {desc_err}")
            except Exception as e:
                print(f"  - AN UNEXPECTED ERROR occurred while processing table {table}: {e}")

        conn.commit()
        print("\nDatabase schema check/update completed.")
    except mysql.connector.Error as err:
        print(f"Error during database schema update: {err}")
    except Exception as e:
        print(f"An unexpected error occurred during schema update: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# --- Page Routes (existing routes, unchanged) ---
@app.route('/')
def landing():
    """Renders the landing page."""
    return render_template('landingPage.html')

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
    Generates UUIDs for VARCHAR primary keys.
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
        conn.start_transaction()

        # --- 1. Insert into occupation table ---
        # Generate a unique VARCHAR ID for occ_id
        occ_id = str(uuid.uuid4())[:10].upper() # Using uuid for VARCHAR ID
        occ_type = r2.get('occupation')
        bus_nature = r2.get('natureOfBusiness')
        sql_occ = "INSERT INTO occupation (occ_id, occ_type, bus_nature) VALUES (%s, %s, %s)"
        cursor.execute(sql_occ, (occ_id, occ_type, bus_nature))

        # --- 2. Insert into financial_record table ---
        # Generate a unique VARCHAR ID for fin_code
        fin_code = str(uuid.uuid4())[:10].upper() # Using uuid for VARCHAR ID
        source_wealth_list = r2.get('sourceOfWealth', [])
        source_wealth = ', '.join(source_wealth_list) if isinstance(source_wealth_list, list) else source_wealth_list
        mon_income = r2.get('monthlyIncome')
        ann_income = r2.get('annualIncome')
        sql_fin = "INSERT INTO financial_record (fin_code, source_wealth, mon_income, ann_income) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql_fin, (fin_code, source_wealth, mon_income, ann_income))

        # --- 3. Insert into customer table ---
        # Generate a unique VARCHAR ID for cust_no
        cust_no = str(uuid.uuid4())[:10].upper() # Using uuid for VARCHAR ID
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

        sql_cust = """INSERT INTO customer (cust_no, custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, occ_id, fin_code)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        customer_data = (
            cust_no, custname, datebirth, nationality, citizenship,
            custsex, placebirth, civilstatus,
            num_children,
            mmaiden_name, cust_address,
            email_address, contact_no, occ_id, fin_code
        )

        print("--- DEBUG: Preparing to execute customer insert query ---")
        # print("SQL Query:", cursor.mogrify(sql_cust, customer_data)) # Removed this line

        cursor.execute(sql_cust, customer_data)

        print(f"--- DEBUG: Successfully inserted customer. New cust_no: {cust_no} (Type: {type(cust_no)}) ---")

        # --- 4. Insert into employer_details and employment_details if applicable ---
        if r2.get('occupation') == 'Employed':
            # Generate a unique VARCHAR ID for emp_id
            emp_id = str(uuid.uuid4())[:10].upper() # Using uuid for VARCHAR ID
            tin_id = r2.get('tinId', '')
            empname = r2.get('companyName', '')
            emp_address = r2.get('employerAddress', '')
            phonefax_no = r2.get('employerPhone', '')
            job_title = r2.get('jobTitle', '')
            emp_date = r2.get('employmentDate') or '2000-01-01'

            sql_emp_details = "INSERT INTO employer_details (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql_emp_details, (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))

            sql_emp_link = "INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s)"
            cursor.execute(sql_emp_link, (cust_no, emp_id))


        # --- 5. Insert into spouse table if married ---
        if r1.get('civilStatus') == 'Married':
            sp_name = f"{r1.get('spouseFirstName', '')} {r1.get('spouseLastName', '')}"
            sp_datebirth = r1.get('spouseDob')
            sp_profession = r1.get('spouseProfession')
            if sp_name.strip() and sp_datebirth and sp_profession:
                sql_spouse = "INSERT INTO spouse (cust_no, sp_name, sp_datebirth, sp_profession) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql_spouse, (cust_no, sp_name, sp_datebirth, sp_profession))

        # --- 6. Insert into company_affiliation ---
        roles = r3.get('depositorRole', [])
        companies = r3.get('companyName', [])
        if not isinstance(roles, list): roles = [roles] if roles else []
        if not isinstance(companies, list): companies = [companies] if companies else []

        for role, company in zip(roles, companies):
            if role and company:
                sql_comp_aff = "INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname) VALUES (%s, %s, %s)"
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
                sql_insert_bank = "INSERT IGNORE INTO bank_details (bank_code, bank_name, branch) VALUES (%s, %s, %s)"
                cursor.execute(sql_insert_bank, (bank_name, bank_name, branch))

                sql_existing_bank = "INSERT INTO existing_bank (cust_no, bank_code, acc_type) VALUES (%s, %s, %s)"
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
                # Generate a unique VARCHAR ID for gov_int_id
                gov_int_id = str(uuid.uuid4())[:10].upper() # Using uuid for VARCHAR ID
                gov_name = f"{gov_first_names[i]} {gov_last_names[i]}"
                sql_po_details = "INSERT INTO public_official_details (gov_int_id, gov_int_name, official_position, branch_orgname) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql_po_details, (gov_int_id, gov_name, positions[i], org_names[i]))

                sql_po_rel = "INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc) VALUES (%s, %s, %s)"
                cursor.execute(sql_po_rel, (cust_no, gov_int_id, relationships[i]))

        # --- 9. Call insert_credentials here to save username and password ---
        insert_credentials(cursor, cust_no, r1)

        conn.commit()
        return '', 200

    except mysql.connector.Error as err:
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
    """
    cursor.execute(sql, (cust_no, username, password))


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

        cursor = conn.cursor(dictionary=True) # Use dictionary=True to fetch rows as dictionaries

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

        # Fetch Occupation and Financial data directly from customer join (already done above)
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
        # Check if the customer is 'Employed' before fetching employer details
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

        return render_template('userHome.html', user_data=user_data)

    except mysql.connector.Error as err:
        print(f"Database error in userHome: {err}")
        flash(f'An error occurred while fetching your data: {err}', 'danger')
        return redirect(url_for('login'))
    except Exception as e:
        print(f"Error in userHome: {e}")
        flash('An unexpected error occurred while loading your profile.', 'danger')
        return redirect(url_for('login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/logout', methods=['POST']) # Add methods=['POST'] here
def logout():
    session.pop('user', None)
    session.pop('user_email', None)
    session.pop('cust_no', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('username')
        password_input = request.form.get('password')

        if email == 'admin@gmail.com' and password_input == 'LandBank@2025':
            session['admin'] = True
            session['user_email'] = email
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if not conn:
                flash('Database connection failed.', 'danger')
                return render_template('login.html', error='Database connection failed.')

            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT credentials.cust_no, username, password, customer.custname
                FROM credentials
                JOIN customer ON credentials.cust_no = customer.cust_no
                WHERE username = %s
            """, (email,))
            user = cursor.fetchone()

            if user and user['password'] == password_input:
                session['user'] = user['custname']
                session['user_email'] = user['username']
                session['cust_no'] = user['cust_no']

                flash('Logged in successfully!', 'success')
                return redirect(url_for('userHome'))
            else:
                flash('Invalid username or password.', 'danger') # Corrected error message
                return render_template('login.html', error='Invalid username or password.')

        except mysql.connector.Error as err: # Catch specific database errors
            print(f"Database error during login: {err}")
            flash(f'An error occurred during login: {err}', 'danger')
            return render_template('login.html', error=f"Database error during login: {err}")
        except Exception as e:
            print(f"Login error: {e}")
            flash('An unexpected error occurred during login.', 'danger')
            return render_template('login.html', error='An unexpected error occurred during login.')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('login.html')

@app.route('/registrationSuccess')
def registration_success():
    """Renders the registration success page."""
    return render_template('registrationSuccess.html')


# ... (your existing code above admin_dashboard) ...

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        flash('Please login to access the admin dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.cust_no, c.custname, c.email_address, c.contact_no
            FROM customer c
            ORDER BY c.cust_no DESC
        """)
        customers = cursor.fetchall()

        return render_template('admin_dashboard.html', customers=customers)

    except Exception as e:
        print(f"Error in admin_dashboard: {e}")
        return "An error occurred while loading the dashboard.", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- ROUTE: Admin View Customer Details ---
@app.route('/admin/customer/<string:cust_no>')
def admin_view_customer(cust_no):
    if 'admin' not in session:
        flash('Please login to access the admin dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    user_data = {} # This dictionary will hold all fetched data

    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard'))

        cursor = conn.cursor(dictionary=True) # Use dictionary=True for easy access by column name

        # Fetch Customer Information (main customer table joined with occupation and financial_record)
        cursor.execute("""
            SELECT c.*, o.occ_type, o.bus_nature, f.source_wealth, f.mon_income, f.ann_income
            FROM customer c
            LEFT JOIN occupation o ON c.occ_id = o.occ_id
            LEFT JOIN financial_record f ON c.fin_code = f.fin_code
            WHERE c.cust_no = %s
        """, (cust_no,))
        user_data['customer'] = cursor.fetchone()

        if not user_data['customer']:
            flash(f'Customer with ID {cust_no} not found.', 'danger')
            return redirect(url_for('admin_dashboard'))

        # Separate the fetched data for clarity in the template
        # The .get() method is used to safely access keys, returning None if not found,
        # which helps prevent errors if a joined field is NULL.
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

        # Fetch Employer Details (conditional on occupation type)
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

        # Fetch Company Affiliations (multiple records possible)
        cursor.execute("SELECT * FROM company_affiliation WHERE cust_no = %s", (cust_no,))
        user_data['company_affiliations'] = cursor.fetchall()

        # Fetch Existing Bank Accounts (multiple records possible)
        cursor.execute("""
            SELECT eb.acc_type, bd.bank_name, bd.branch
            FROM existing_bank eb
            JOIN bank_details bd ON eb.bank_code = bd.bank_code
            WHERE eb.cust_no = %s
        """, (cust_no,))
        user_data['existing_banks'] = cursor.fetchall()

        # Fetch Public Official Relationships (multiple records possible)
        cursor.execute("""
            SELECT cpr.relation_desc, pod.gov_int_name, pod.official_position, pod.branch_orgname
            FROM cust_po_relationship cpr
            JOIN public_official_details pod ON cpr.gov_int_id = pod.gov_int_id
            WHERE cpr.cust_no = %s
        """, (cust_no,))
        user_data['public_official_relationships'] = cursor.fetchall()

        # Render the template, passing all collected data in 'user_data'
        return render_template('admin_view_customer.html', user_data=user_data)

    except mysql.connector.Error as err:
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
# ... (your existing code, including admin_view_customer route) ...

# --- NEW ROUTE: Admin Edit Customer Details ---
@app.route('/admin/edit_customer/<string:cust_no>', methods=['GET', 'POST'])
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

        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # --- Handle form submission for UPDATE ---
            # This is where you will add the logic to process the form data
            # and update the database. For now, we'll just redirect after a message.
            flash('Customer update logic is not yet implemented for POST. Displaying current data.', 'info')
            # You will need to implement:
            # 1. Get form data: request.form.get('fieldname')
            # 2. Prepare SQL UPDATE statements for customer, spouse, employment, financial, etc.
            # 3. Execute updates in a transaction.
            # 4. Handle success/failure with flashes.
            # Example (conceptual, do not use directly without full implementation):
            # new_name = request.form.get('custname')
            # cursor.execute("UPDATE customer SET custname = %s WHERE cust_no = %s", (new_name, cust_no))
            # conn.commit()
            # flash('Customer details updated successfully!', 'success')
            # return redirect(url_for('admin_view_customer', cust_no=cust_no))
            pass # Keep execution flowing to GET part for now
        
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
        # Make sure these keys exist, even if None
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

    except mysql.connector.Error as err:
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


# ... (your existing code, including admin_edit_customer route) ...

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

        # Start a transaction to ensure data integrity
        conn.start_transaction()

        # Delete from tables that have foreign keys referencing customer (or other tables that reference others)
        # Order of deletion is crucial due to foreign key constraints:
        # Delete child records first, then parent records.

        # 1. Delete from cust_po_relationship
        cursor.execute("DELETE FROM cust_po_relationship WHERE cust_no = %s", (cust_no,))

        # 2. Delete from existing_bank
        cursor.execute("DELETE FROM existing_bank WHERE cust_no = %s", (cust_no,))

        # 3. Delete from company_affiliation
        cursor.execute("DELETE FROM company_affiliation WHERE cust_no = %s", (cust_no,))

        # 4. Handle employment_details and employer_details
        # First, find emp_id from employment_details if customer is employed
        cursor.execute("SELECT emp_id FROM employment_details WHERE cust_no = %s", (cust_no,))
        emp_id_result = cursor.fetchone()
        emp_id = emp_id_result[0] if emp_id_result else None

        # Delete from employment_details
        cursor.execute("DELETE FROM employment_details WHERE cust_no = %s", (cust_no,))

        # If emp_id exists, delete from employer_details (assuming emp_id is unique to employment_details)
        if emp_id:
            cursor.execute("DELETE FROM employer_details WHERE emp_id = %s", (emp_id,))
            
        # 5. Delete from spouse
        cursor.execute("DELETE FROM spouse WHERE cust_no = %s", (cust_no,))

        # 6. Get fin_code and occ_id before deleting from customer
        cursor.execute("SELECT fin_code, occ_id FROM customer WHERE cust_no = %s", (cust_no,))
        customer_info = cursor.fetchone()
        fin_code = customer_info[0] if customer_info else None
        occ_id = customer_info[1] if customer_info else None

        # 7. Finally, delete from customer
        cursor.execute("DELETE FROM customer WHERE cust_no = %s", (cust_no,))

        # 8. Delete from financial_record if fin_code exists and is no longer referenced by other customers
        if fin_code:
            cursor.execute("SELECT COUNT(*) FROM customer WHERE fin_code = %s", (fin_code,))
            if cursor.fetchone()[0] == 0: # If no other customers use this fin_code
                cursor.execute("DELETE FROM financial_record WHERE fin_code = %s", (fin_code,))
        
        # 9. Delete from occupation if occ_id exists and is no longer referenced by other customers
        if occ_id:
            cursor.execute("SELECT COUNT(*) FROM customer WHERE occ_id = %s", (occ_id,))
            if cursor.fetchone()[0] == 0: # If no other customers use this occ_id
                cursor.execute("DELETE FROM occupation WHERE occ_id = %s", (occ_id,))


        conn.commit() # Commit the transaction if all deletions are successful
        flash(f'Customer {cust_no} and all related records deleted successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    except mysql.connector.Error as err:
        conn.rollback() # Rollback on error
        print(f"Database error during customer deletion: {err}")
        flash(f'An error occurred during deletion: {err}', 'danger')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        if conn: # Check if conn exists before trying to rollback
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
    _ensure_database_schema() # Run schema check/update on app startup (for development)
    app.run(host='0.0.0.0', port=0000, debug=True) # Corrected port to 5000
