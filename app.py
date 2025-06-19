import psycopg2 
from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid # Still used for session/internal if needed, but not for DB IDs
import os 
import psycopg2.extras 

# Import both connection URL functions
from db_config import get_db_url, get_postgres_admin_url

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

def _generate_next_id(cursor, table_name, id_column, prefix, padding_length):
    """
    Generates the next sequential ID with a given prefix and padding.
    E.g., C001, EMP001, SP01.
    """
    # Find the last ID for the given prefix
    # Use LIKE operator for VARCHAR columns
    cursor.execute(f"SELECT {id_column} FROM {table_name} WHERE {id_column} LIKE %s ORDER BY {id_column} DESC LIMIT 1;", (f"{prefix}%",))
    last_id_result = cursor.fetchone()

    next_num = 1
    if last_id_result:
        last_id = last_id_result[0]
        # Extract the numeric part after the prefix
        try:
            last_id_num_str = last_id[len(prefix):]
            next_num = int(last_id_num_str) + 1
        except (ValueError, IndexError):
            # Fallback if the existing ID format is unexpected, start from 1
            print(f"Warning: Malformed ID '{last_id}' found for {table_name}. Generating next ID from 1.")
            next_num = 1
    
    return f"{prefix}{str(next_num).zfill(padding_length)}"

def _reset_database():
    """
    Connects as a superuser to drop and recreate the database.
    WARNING: This will DELETE ALL DATA. Use ONLY for development/testing.
    Requires POSTGRES_ADMIN_URL in environment or db_config.py.
    """
    admin_conn = None
    admin_cursor = None
    try:
        admin_conn_url = get_postgres_admin_url()
        # Connect to 'postgres' database as it's the default superuser database
        admin_conn = psycopg2.connect(admin_conn_url)
        admin_conn.autocommit = True # Autocommit for DDL like DROP/CREATE DATABASE
        admin_cursor = admin_conn.cursor()

        db_name = get_db_url().split('/')[-1] # Extract database name from app's URL

        print(f"\n--- Attempting to reset database '{db_name}' (DEVELOPMENT ONLY) ---")
        
        # Terminate all active connections to the database before dropping
        admin_cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{db_name}'
              AND pid <> pg_backend_pid();
        """)
        print(f"  - Terminated active connections to '{db_name}'.")
        
        # Drop and create the database
        admin_cursor.execute(f"DROP DATABASE IF EXISTS {db_name};")
        print(f"  - Dropped database '{db_name}'.")
        admin_cursor.execute(f"CREATE DATABASE {db_name};")
        print(f"  - Created database '{db_name}'.")
        print(f"--- Database '{db_name}' reset successfully. ---")

    except psycopg2.Error as err:
        print(f"ERROR: Database reset failed: {err}")
        print("Please ensure POSTGRES_ADMIN_URL is correctly configured with superuser credentials.")
        if debug_mode:
            raise
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during database reset: {e}")
        if debug_mode:
            raise
    finally:
        if admin_cursor:
            admin_cursor.close()
        if admin_conn:
            admin_conn.close()

# --- Function to Ensure Database Schema (for development/initial setup) ---
def _ensure_database_schema():
    """
    Ensures that necessary tables exist and have appropriate types for PostgreSQL.
    This function should typically be run only once, or managed by a proper migration tool.
    For development, it runs on app startup.
    
    Includes a conditional database reset if a major schema incompatibility (like UUID vs VARCHAR PK)
    is detected in debug mode.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to get database connection for schema update.")
            # If initial connection fails, try resetting db if in debug mode
            if debug_mode:
                _reset_database()
                conn = get_db_connection() # Try connecting again after reset
                if not conn:
                    print("Failed to get database connection even after reset. Exiting schema check.")
                    return
            else:
                return

        cursor = conn.cursor()
        conn.autocommit = True # Set to True for schema operations outside of explicit transactions
        print("Attempting to ensure PostgreSQL database schema with custom IDs...\n")

        # --- Check for major schema incompatibility (UUID vs VARCHAR for cust_no) ---
        # If in debug mode and cust_no is still UUID, force a full database reset.
        if debug_mode:
            try:
                cursor.execute("""
                    SELECT data_type FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = 'customer' AND column_name = 'cust_no';
                """)
                cust_no_type = cursor.fetchone()
                if cust_no_type and cust_no_type[0] == 'uuid':
                    print("\n!!! Detected 'customer.cust_no' is still UUID. Forcing database reset for development. !!!\n")
                    conn.close() # Close current connection before resetting
                    _reset_database()
                    conn = get_db_connection() # Reconnect after reset
                    if not conn:
                        print("Failed to reconnect after database reset. Cannot proceed with schema creation.")
                        return
                    cursor = conn.cursor()
                    conn.autocommit = True # Re-enable autocommit for the new cursor
            except psycopg2.ProgrammingError as e:
                # This error means the table might not exist yet, which is fine, proceed to create
                print(f"Schema check warning: {e}. Assuming fresh schema or table creation will follow.")
                conn.rollback() # Rollback any partial transaction from schema check
            except Exception as e:
                print(f"Unexpected error during initial schema type check: {e}")
                conn.rollback()


        # Define table creation SQL for PostgreSQL with VARCHAR primary keys
        # Tables are ordered to respect foreign key dependencies.
        schema_sql = {
            'occupation': """
                CREATE TABLE IF NOT EXISTS occupation (
                    occ_id VARCHAR(10) PRIMARY KEY, -- Changed from UUID
                    occ_type VARCHAR(255),
                    bus_nature VARCHAR(255)
                );
            """,
            'financial_record': """
                CREATE TABLE IF NOT EXISTS financial_record (
                    fin_code VARCHAR(10) PRIMARY KEY, -- Changed from UUID
                    source_wealth TEXT,
                    mon_income TEXT, 
                    ann_income TEXT 
                );
            """,
            'bank_details': """
                CREATE TABLE IF NOT EXISTS bank_details (
                    bank_code VARCHAR(10) PRIMARY KEY, -- Changed from VARCHAR(10) to VARCHAR(10) explicit
                    bank_name VARCHAR(255),
                    branch VARCHAR(255)
                );
            """,
            'public_official_details': """
                CREATE TABLE IF NOT EXISTS public_official_details (
                    gov_int_id VARCHAR(10) PRIMARY KEY, -- Changed from UUID
                    gov_int_name VARCHAR(255),
                    official_position VARCHAR(255),
                    branch_orgname VARCHAR(255)
                );
            """,
            'customer': """
                CREATE TABLE IF NOT EXISTS customer (
                    cust_no VARCHAR(10) PRIMARY KEY, -- Changed from UUID
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
                    occ_id VARCHAR(10), -- Changed from UUID
                    fin_code VARCHAR(10), -- Changed from UUID
                    registration_status VARCHAR(50) DEFAULT 'Pending', 
                    FOREIGN KEY (occ_id) REFERENCES occupation (occ_id) ON DELETE SET NULL,
                    FOREIGN KEY (fin_code) REFERENCES financial_record (fin_code) ON DELETE SET NULL
                );
            """,
            'employer_details': """
                CREATE TABLE IF NOT EXISTS employer_details (
                    emp_id VARCHAR(10) PRIMARY KEY, -- Changed from UUID
                    occ_id VARCHAR(10) REFERENCES occupation (occ_id) ON DELETE SET NULL, -- Changed from UUID
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
                    cust_no VARCHAR(10) REFERENCES customer (cust_no) ON DELETE CASCADE, -- Changed from UUID
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    PRIMARY KEY (cust_no, username) 
                );
            """,
            'spouse': """
                CREATE TABLE IF NOT EXISTS spouse (
                    spouse_id VARCHAR(10) PRIMARY KEY, -- NEW: Added spouse_id as PK
                    cust_no VARCHAR(10) UNIQUE REFERENCES customer (cust_no) ON DELETE CASCADE, -- Changed from UUID, now UNIQUE
                    sp_name VARCHAR(255),
                    sp_datebirth DATE,
                    sp_profession VARCHAR(255)
                );
            """,
            'company_affiliation': """
                CREATE TABLE IF NOT EXISTS company_affiliation (
                    cust_no VARCHAR(10) REFERENCES customer (cust_no) ON DELETE CASCADE, -- Changed from UUID
                    depositor_role VARCHAR(255),
                    dep_compname VARCHAR(255),
                    PRIMARY KEY (cust_no, depositor_role, dep_compname) 
                );
            """,
            'existing_bank': """
                CREATE TABLE IF NOT EXISTS existing_bank (
                    cust_no VARCHAR(10) REFERENCES customer (cust_no) ON DELETE CASCADE, -- Changed from UUID
                    bank_code VARCHAR(10) REFERENCES bank_details (bank_code) ON DELETE CASCADE, -- Changed from VARCHAR(10)
                    acc_type VARCHAR(255),
                    PRIMARY KEY (cust_no, bank_code, acc_type) 
                );
            """,
            'cust_po_relationship': """
                CREATE TABLE IF NOT EXISTS cust_po_relationship (
                    cust_no VARCHAR(10) REFERENCES customer (cust_no) ON DELETE CASCADE, -- Changed from UUID
                    gov_int_id VARCHAR(10) REFERENCES public_official_details (gov_int_id) ON DELETE CASCADE, -- Changed from UUID
                    relation_desc VARCHAR(255),
                    PRIMARY KEY (cust_no, gov_int_id) 
                );
            """,
            'employment_details': """
                CREATE TABLE IF NOT EXISTS employment_details (
                    cust_no VARCHAR(10) REFERENCES customer (cust_no) ON DELETE CASCADE, -- Changed from UUID
                    emp_id VARCHAR(10) REFERENCES employer_details (emp_id) ON DELETE CASCADE, -- Changed from UUID
                    PRIMARY KEY (cust_no, emp_id) 
                );
            """
        }

        for table_name, create_sql in schema_sql.items():
            try:
                print(f"  - Ensuring table: {table_name}")
                cursor.execute(create_sql)
                conn.commit() 
                print(f"  - Table '{table_name}' checked/created successfully.")
            except psycopg2.Error as err:
                print(f"  - ERROR creating/checking table {table_name}: {err}")
                conn.rollback() 
        
        # --- ALTER TABLE LOGIC (for financial_record income types and customer status, and spouse PK) ---
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
            
            # Check and add spouse_id to spouse table if it doesn't exist, and update PK
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'spouse' AND column_name = 'spouse_id';
            """)
            spouse_id_column_exists = cursor.fetchone()
            if not spouse_id_column_exists:
                print("  - Adding 'spouse_id' column to 'spouse' table...")
                cursor.execute("ALTER TABLE spouse ADD COLUMN spouse_id VARCHAR(10);")
                conn.commit()
                
                print("  - Updating spouse table primary key to spouse_id...")
                # First, drop the old primary key if it existed on cust_no
                cursor.execute("""
                    DO $$
                    DECLARE
                        constraint_name text;
                    BEGIN
                        SELECT conname INTO constraint_name
                        FROM pg_constraint
                        WHERE conrelid = 'spouse'::regclass AND contype = 'p';
                        
                        IF constraint_name IS NOT NULL THEN
                            EXECUTE 'ALTER TABLE spouse DROP CONSTRAINT ' || constraint_name;
                        END IF;
                    END
                    $$;
                """)
                conn.commit()
                # Make cust_no unique in spouse if it's not already
                # Note: The 'uuid ~~ unknown' error came from here when cust_no was UUID.
                # Now that schema is being managed more strictly, this should be fine
                # if the tables are fresh or already VARCHAR.
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'spouse'::regclass AND contype = 'u' AND conkey = array[2]) THEN
                            ALTER TABLE spouse ADD CONSTRAINT unique_cust_no_in_spouse UNIQUE (cust_no);
                        END IF;
                    END
                    $$;
                """)
                conn.commit()
                # Set spouse_id as PRIMARY KEY
                cursor.execute("ALTER TABLE spouse ALTER COLUMN spouse_id SET NOT NULL;")
                conn.commit()
                cursor.execute("ALTER TABLE spouse ADD PRIMARY KEY (spouse_id);")
                conn.commit()
                print("  - Successfully added 'spouse_id' to 'spouse' table and updated PK.")

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
    Generates custom sequential IDs for primary keys.
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

        # --- Generate unique IDs for this transaction ---
        cust_no = _generate_next_id(cursor, 'customer', 'cust_no', 'C', 3)
        occ_id = _generate_next_id(cursor, 'occupation', 'occ_id', 'OC', 2)
        fin_code = _generate_next_id(cursor, 'financial_record', 'fin_code', 'F', 1)
        # emp_id, spouse_id, gov_int_id, bank_code will be generated conditionally as needed

        print(f"Generated IDs: cust_no={cust_no}, occ_id={occ_id}, fin_code={fin_code}")

        # --- 1. Insert into occupation table ---
        occ_type = r2.get('occupation')
        bus_nature = r2.get('natureOfBusiness')
        sql_occ = "INSERT INTO occupation (occ_id, occ_type, bus_nature) VALUES (%s, %s, %s);"
        cursor.execute(sql_occ, (occ_id, occ_type, bus_nature))

        # --- 2. Insert into financial_record table ---
        source_wealth_list = r2.get('sourceOfWealth', [])
        source_wealth = ', '.join(source_wealth_list) if isinstance(source_wealth_list, list) else source_wealth_list
        mon_income = r2.get('monthlyIncome')
        ann_income = r2.get('annualIncome')
        sql_fin = "INSERT INTO financial_record (fin_code, source_wealth, mon_income, ann_income) VALUES (%s, %s, %s, %s);"
        cursor.execute(sql_fin, (fin_code, source_wealth, mon_income, ann_income))

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
        registration_status = 'Pending' 

        sql_cust = """INSERT INTO customer (cust_no, custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, occ_id, fin_code, registration_status)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
        customer_data = (
            cust_no, custname, datebirth, nationality, citizenship,
            custsex, placebirth, civilstatus,
            num_children,
            mmaiden_name, cust_address,
            email_address, contact_no, occ_id, fin_code, registration_status
        )

        cursor.execute(sql_cust, customer_data)
        print(f"--- DEBUG: Successfully inserted customer. New cust_no: {cust_no} ---")

        # --- 4. Insert into employer_details and employment_details if applicable ---
        if r2.get('occupation') == 'Employed':
            emp_id = _generate_next_id(cursor, 'employer_details', 'emp_id', 'EMP', 3)
            tin_id = r2.get('tinId', '')
            empname = r2.get('companyName', '')
            emp_address = r2.get('employerAddress', '')
            phonefax_no = r2.get('employerPhone', '')
            emp_date_str = r2.get('employmentDate') 
            emp_date = emp_date_str if emp_date_str else None # Handle empty date string
            job_title = r2.get('jobTitle', '')


            sql_emp_details = "INSERT INTO employer_details (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);"
            cursor.execute(sql_emp_details, (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))

            sql_emp_link = "INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s);"
            cursor.execute(sql_emp_link, (cust_no, emp_id))

        # --- 5. Insert into spouse table if married ---
        if r1.get('civilStatus') == 'Married':
            spouse_id = _generate_next_id(cursor, 'spouse', 'spouse_id', 'SP', 1)
            sp_name = f"{r1.get('spouseFirstName', '')} {r1.get('spouseLastName', '')}"
            sp_datebirth_str = r1.get('spouseDob')
            sp_datebirth = sp_datebirth_str if sp_datebirth_str else None # Handle empty date string
            sp_profession = r1.get('spouseProfession')
            if sp_name.strip() and sp_profession and sp_datebirth: # Only insert if all spouse fields are non-empty
                sql_spouse = "INSERT INTO spouse (spouse_id, cust_no, sp_name, sp_datebirth, sp_profession) VALUES (%s, %s, %s, %s, %s);"
                cursor.execute(sql_spouse, (spouse_id, cust_no, sp_name, sp_datebirth, sp_profession))

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
        banks_data = r3.get('bank', [])
        branches_data = r3.get('branch', [])
        acc_types_data = r3.get('accountType', [])

        # Ensure lists are of equal length, or handle accordingly
        min_bank_len = min(len(banks_data), len(branches_data), len(acc_types_data))
        
        for i in range(min_bank_len):
            bank_name = banks_data[i]
            branch = branches_data[i]
            acc_type = acc_types_data[i]

            if bank_name and branch and acc_type:
                # Check if bank_details already exists to avoid duplicate bank_code generation for same bank
                cursor.execute("SELECT bank_code FROM bank_details WHERE bank_name = %s AND branch = %s;", (bank_name, branch))
                existing_bank_code = cursor.fetchone()

                if existing_bank_code:
                    current_bank_code = existing_bank_code[0]
                else:
                    current_bank_code = _generate_next_id(cursor, 'bank_details', 'bank_code', 'B', 1)
                    sql_insert_bank = "INSERT INTO bank_details (bank_code, bank_name, branch) VALUES (%s, %s, %s);"
                    cursor.execute(sql_insert_bank, (current_bank_code, bank_name, branch))

                sql_existing_bank = "INSERT INTO existing_bank (cust_no, bank_code, acc_type) VALUES (%s, %s, %s) ON CONFLICT (cust_no, bank_code, acc_type) DO NOTHING;"
                cursor.execute(sql_existing_bank, (cust_no, current_bank_code, acc_type))

        # --- 8. Insert into public_official_details and cust_po_relationship ---
        gov_last_names = r3.get('govLastName', [])
        gov_first_names = r3.get('govFirstName', [])
        relationships = r3.get('relationship', [])
        positions = r3.get('position', [])
        org_names = r3.get('govBranchOrgName', [])

        min_len_po = min(len(gov_last_names), len(gov_first_names), len(relationships), len(positions), len(org_names))
        for i in range(min_len_po):
            # Only process if essential fields are not empty
            if gov_last_names[i] and gov_first_names[i] and relationships[i] and positions[i] and org_names[i]:
                gov_name = f"{gov_first_names[i]} {gov_last_names[i]}"
                
                # Check if PO already exists to avoid duplicates
                cursor.execute("SELECT gov_int_id FROM public_official_details WHERE gov_int_name = %s AND official_position = %s AND branch_orgname = %s;",
                               (gov_name, positions[i], org_names[i]))
                po_exists = cursor.fetchone()

                if po_exists:
                    gov_int_id = po_exists[0]
                else:
                    gov_int_id = _generate_next_id(cursor, 'public_official_details', 'gov_int_id', 'OFF', 3)
                    sql_po_details = "INSERT INTO public_official_details (gov_int_id, gov_int_name, official_position, branch_orgname) VALUES (%s, %s, %s, %s);"
                    cursor.execute(sql_po_details, (gov_int_id, gov_name, positions[i], org_names[i]))

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

# --- Helper Function Definitions (Called from submit_registration and admin_add_customer) ---
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

        return render_template('userHome.html', user_data=user_data)

    except psycopg2.Error as err:
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

@app.route('/logout', methods=['POST'])
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
            return redirect(url_for('admin_dashboard_page')) 

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if not conn:
                flash('Database connection failed.', 'danger')
                return render_template('login.html', error='Database connection failed.')

            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            cursor.execute("""
                SELECT credentials.cust_no, username, password, customer.custname
                FROM credentials
                JOIN customer ON credentials.cust_no = customer.cust_no
                WHERE username = %s
            """, (email,))
            user = cursor.fetchone()

            if user and user['password'] == password_input: # IMPORTANT: Replace with hashed password comparison in production
                session['user'] = user['custname']
                session['user_email'] = user['username']
                session['cust_no'] = user['cust_no'] # cust_no is now VARCHAR
                flash('Logged in successfully!', 'success')
                return redirect(url_for('userHome'))
            else:
                flash('Invalid username or password.', 'danger')
                return render_template('login.html', error='Invalid username or password.')

        except psycopg2.Error as err:
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

# Explicitly named endpoint for clarity and to resolve potential routing issues
@app.route('/admin_dashboard', endpoint='admin_dashboard_page')
def admin_dashboard():
    if 'admin' not in session:
        flash('Please login to access the admin dashboard.', 'warning')
        return redirect(url_for('login')) 

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            if debug_mode:
                raise Exception("Database connection failed for admin_dashboard.")
            flash('Database connection failed.', 'danger')
            return redirect(url_for('login'))

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get query parameters for filtering and searching
        search_query = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        reg_date_filter = request.args.get('reg_date', '').strip()

        sql_query = """
            SELECT c.cust_no, c.custname, c.email_address, c.contact_no, 
                   c.registration_status, 
                   c.datebirth AS registration_date -- Using datebirth as registration date
            FROM customer c
            WHERE 1=1
        """
        params = []

        if search_query:
            sql_query += " AND (c.custname ILIKE %s OR c.email_address ILIKE %s OR c.contact_no ILIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        
        if status_filter and status_filter != 'All Statuses':
            sql_query += " AND c.registration_status = %s"
            params.append(status_filter)

        if reg_date_filter:
            sql_query += " AND c.datebirth = %s" 
            params.append(reg_date_filter)

        sql_query += " ORDER BY c.custname ASC" 

        cursor.execute(sql_query, params)
        customers = cursor.fetchall()

        processed_customers = []
        for customer in customers:
            customer_dict = dict(customer) # Convert row to dictionary for modification
            customer_dict['status'] = customer_dict.get('registration_status', 'Pending') 
            if customer_dict.get('registration_date'):
                customer_dict['registration_date'] = customer_dict['registration_date'].strftime('%Y-%m-%d')
            processed_customers.append(customer_dict)

        return render_template('admin_dashboard.html', customers=processed_customers)

    except psycopg2.Error as err:
        print(f"Database error in admin_dashboard: {err}")
        if debug_mode:
            raise
        flash(f'An error occurred while loading the dashboard: {err}', 'danger')
        return redirect(url_for('login')) 
    except Exception as e:
        print(f"Error in admin_dashboard: {e}")
        if debug_mode:
            raise
        flash('An unexpected error occurred while loading the dashboard.', 'danger')
        return redirect(url_for('login')) 
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- NEW ROUTE: Admin Add Customer ---
@app.route('/admin/add_customer', methods=['POST'])
def admin_add_customer():
    if 'admin' not in session:
        flash('Please login to access this function.', 'warning')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page'))

        cursor = conn.cursor()
        conn.autocommit = False # Start a transaction

        # --- Generate unique IDs for this transaction ---
        cust_no = _generate_next_id(cursor, 'customer', 'cust_no', 'C', 3)
        occ_id = _generate_next_id(cursor, 'occupation', 'occ_id', 'OC', 2)
        fin_code = _generate_next_id(cursor, 'financial_record', 'fin_code', 'F', 1)
        # emp_id, spouse_id, gov_int_id, bank_code will be generated conditionally as needed

        # --- Extract form data for Customer table ---
        custname = request.form.get('custname')
        datebirth = request.form.get('datebirth') or None # Handle empty date
        nationality = request.form.get('nationality')
        citizenship = request.form.get('citizenship')
        custsex = request.form.get('custsex')
        placebirth = request.form.get('placebirth')
        civilstatus = request.form.get('civilstatus')
        num_children = int(request.form.get('num_children') or 0)
        mmaiden_name = request.form.get('mmaiden_name')
        cust_address = request.form.get('cust_address')
        email_address = request.form.get('email_address')
        contact_no = request.form.get('contact_no')
        registration_status = request.form.get('registration_status') or 'Active'

        # --- Insert into Financial Record table ---
        source_wealth = request.form.get('source_wealth') or 'Unspecified'
        mon_income = request.form.get('mon_income') or '0'
        ann_income = request.form.get('ann_income') or '0'
        sql_fin = "INSERT INTO financial_record (fin_code, source_wealth, mon_income, ann_income) VALUES (%s, %s, %s, %s);"
        cursor.execute(sql_fin, (fin_code, source_wealth, mon_income, ann_income))

        # --- Insert into Occupation table ---
        occ_type = request.form.get('occ_type') or 'Unspecified'
        bus_nature = request.form.get('bus_nature') or 'General'
        sql_occ = "INSERT INTO occupation (occ_id, occ_type, bus_nature) VALUES (%s, %s, %s);"
        cursor.execute(sql_occ, (occ_id, occ_type, bus_nature))

        # --- Insert into Customer table ---
        sql_cust = """INSERT INTO customer (cust_no, custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, occ_id, fin_code, registration_status)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
        customer_data = (
            cust_no, custname, datebirth, nationality, citizenship,
            custsex, placebirth, civilstatus,
            num_children,
            mmaiden_name, cust_address,
            email_address, contact_no, occ_id, fin_code, registration_status
        )
        cursor.execute(sql_cust, customer_data)

        # --- Insert into Credentials table (using email as username, generate a simple password) ---
        insert_credentials(cursor, cust_no, {'email': email_address}) 

        # --- Insert into Spouse table (if married and data provided) ---
        sp_name = request.form.get('sp_name')
        sp_datebirth = request.form.get('sp_datebirth') or None # Handle empty date
        sp_profession = request.form.get('sp_profession')
        if civilstatus == 'Married' and sp_name and sp_profession and sp_datebirth:
            spouse_id = _generate_next_id(cursor, 'spouse', 'spouse_id', 'SP', 1)
            sql_spouse = "INSERT INTO spouse (spouse_id, cust_no, sp_name, sp_datebirth, sp_profession) VALUES (%s, %s, %s, %s, %s);"
            cursor.execute(sql_spouse, (spouse_id, cust_no, sp_name, sp_datebirth, sp_profession))

        # --- Insert into Employer Details and Employment Details if applicable ---
        if occ_type == 'Employed': 
            tin_id = request.form.get('tin_id')
            empname = request.form.get('empname')
            emp_address = request.form.get('emp_address')
            phonefax_no = request.form.get('phonefax_no')
            job_title = request.form.get('job_title')
            emp_date = request.form.get('emp_date') or None # Handle empty date

            if empname: 
                emp_id = _generate_next_id(cursor, 'employer_details', 'emp_id', 'EMP', 3)
                sql_emp_details = "INSERT INTO employer_details (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);"
                cursor.execute(sql_emp_details, (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))
                sql_emp_link = "INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s);"
                cursor.execute(sql_emp_link, (cust_no, emp_id))

        # --- Insert into Company Affiliations ---
        depositor_roles = request.form.getlist('depositor_role[]')
        dep_compnames = request.form.getlist('dep_compname[]')
        for role, comp_name in zip(depositor_roles, dep_compnames):
            if role and comp_name:
                cursor.execute("INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname) VALUES (%s, %s, %s);", (cust_no, role, comp_name))

        # --- Insert into Existing Bank Accounts ---
        bank_names = request.form.getlist('bank_name[]')
        branches = request.form.getlist('branch[]')
        acc_types = request.form.getlist('acc_type[]')
        for b_name, branch, a_type in zip(bank_names, branches, acc_types):
            if b_name and branch and a_type:
                cursor.execute("SELECT bank_code FROM bank_details WHERE bank_name = %s AND branch = %s;", (b_name, branch))
                existing_bank_code = cursor.fetchone()

                if existing_bank_code:
                    current_bank_code = existing_bank_code[0]
                else:
                    current_bank_code = _generate_next_id(cursor, 'bank_details', 'bank_code', 'B', 1)
                    cursor.execute("INSERT INTO bank_details (bank_code, bank_name, branch) VALUES (%s, %s, %s);", (current_bank_code, b_name, branch))
                
                cursor.execute("INSERT INTO existing_bank (cust_no, bank_code, acc_type) VALUES (%s, %s, %s);", (cust_no, current_bank_code, a_type))

        # --- Insert into Public Official Relationships ---
        gov_int_names = request.form.getlist('gov_int_name[]')
        official_positions = request.form.getlist('official_position[]')
        branch_orgnames = request.form.getlist('branch_orgname[]')
        relation_descs = request.form.getlist('relation_desc[]')

        min_len_po = min(len(gov_int_names), len(official_positions), len(branch_orgnames), len(relation_descs))
        for i in range(min_len_po):
            gov_name = gov_int_names[i]
            pos = official_positions[i]
            org = branch_orgnames[i]
            rel_desc = relation_descs[i]

            if gov_name and pos and org and rel_desc:
                cursor.execute("SELECT gov_int_id FROM public_official_details WHERE gov_int_name = %s AND official_position = %s AND branch_orgname = %s;", (gov_name, pos, org))
                po_id_result = cursor.fetchone()
                if po_id_result:
                    gov_int_id = po_id_result[0]
                else:
                    gov_int_id = _generate_next_id(cursor, 'public_official_details', 'gov_int_id', 'OFF', 3)
                    cursor.execute("INSERT INTO public_official_details (gov_int_id, gov_int_name, official_position, branch_orgname) VALUES (%s, %s, %s, %s);", (gov_int_id, gov_name, pos, org))
                
                cursor.execute("INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc) VALUES (%s, %s, %s);", (cust_no, gov_int_id, rel_desc))
            
        conn.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('admin_dashboard_page'))

    except psycopg2.Error as err:
        if conn:
            conn.rollback()
        print(f"Database error during add customer: {err}")
        flash(f'An error occurred during adding customer: {err}', 'danger')
        return redirect(url_for('admin_dashboard_page'))
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Unexpected error during add customer: {e}")
        flash('An unexpected error occurred during adding customer.', 'danger')
        return redirect(url_for('admin_dashboard_page'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# --- ROUTE: Admin View Customer Details ---
@app.route('/admin/customer/<cust_no>') # cust_no is now VARCHAR
def admin_view_customer(cust_no):
    if 'admin' not in session:
        flash('Please login to access the admin dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    user_data = {} 

    try:
        conn = get_db_connection()
        if not conn:
            if debug_mode:
                raise Exception("Database connection failed for admin_view_customer.")
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page')) 

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
            flash(f'Customer with ID {cust_no} not found.', 'danger')
            return redirect(url_for('admin_dashboard_page')) 

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
        if debug_mode:
            raise
        flash(f'An error occurred while fetching customer data: {err}', 'danger')
        return redirect(url_for('admin_dashboard_page')) 
    except Exception as e:
        print(f"Error in admin_view_customer: {e}")
        if debug_mode:
            raise
        flash('An unexpected error occurred while loading customer details.', 'danger')
        return redirect(url_for('admin_dashboard_page')) 
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- NEW ROUTE: Admin Edit Customer Details ---
@app.route('/admin/edit_customer/<cust_no>', methods=['GET', 'POST']) # cust_no is now VARCHAR
def admin_edit_customer(cust_no):
    if 'admin' not in session:
        flash('Please login to access the admin dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    customer_data = {} 

    try:
        conn = get_db_connection()
        if not conn:
            if debug_mode:
                raise Exception("Database connection failed for admin_edit_customer.")
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page')) 

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if request.method == 'POST':
            # --- Handle form submission for UPDATE ---
            custname = request.form.get('custname')
            datebirth = request.form.get('datebirth') or None # Handle empty date string
            nationality = request.form.get('nationality')
            citizenship = request.form.get('citizenship')
            custsex = request.form.get('custsex')
            placebirth = request.form.get('placebirth')
            civilstatus = request.form.get('civilstatus')
            num_children = request.form.get('num_children') or '0'
            mmaiden_name = request.form.get('mmaiden_name')
            cust_address = request.form.get('cust_address')
            email_address = request.form.get('email_address')
            contact_no = request.form.get('contact_no')
            registration_status = request.form.get('registration_status') # Added this field from form

            sp_name = request.form.get('sp_name')
            sp_datebirth = request.form.get('sp_datebirth') or None # Handle empty date string
            sp_profession = request.form.get('sp_profession')

            occ_type = request.form.get('occ_type')
            bus_nature = request.form.get('bus_nature')
            tin_id = request.form.get('tin_id')
            empname = request.form.get('empname')
            emp_address = request.form.get('emp_address')
            phonefax_no = request.form.get('phonefax_no')
            job_title = request.form.get('job_title')
            emp_date = request.form.get('emp_date') or None # Handle empty date string

            source_wealth = request.form.get('source_wealth')
            mon_income = request.form.get('mon_income')
            ann_income = request.form.get('ann_income')

            conn.autocommit = False 

            # Fetch current occ_id and fin_code associated with the customer
            cursor.execute("SELECT occ_id, fin_code FROM customer WHERE cust_no = %s;", (cust_no,))
            customer_ids_info = cursor.fetchone()

            if not customer_ids_info:
                flash(f'Customer with ID {cust_no} not found for update.', 'danger')
                conn.rollback()
                return redirect(url_for('admin_dashboard_page')) 

            current_occ_id = customer_ids_info['occ_id']
            current_fin_code = customer_ids_info['fin_code']

            # --- Update Customer Table ---
            cursor.execute("""
                UPDATE customer
                SET custname = %s, datebirth = %s, nationality = %s, citizenship = %s, custsex = %s,
                    placebirth = %s, civilstatus = %s, num_children = %s, mmaiden_name = %s,
                    cust_address = %s, email_address = %s, contact_no = %s, registration_status = %s
                WHERE cust_no = %s;
            """, (custname, datebirth, nationality, citizenship, custsex,
                  placebirth, civilstatus, int(num_children), mmaiden_name,
                  cust_address, email_address, contact_no, registration_status,
                  cust_no)) 
            
            # --- Update Occupation Table (or insert if new and not found) ---
            if current_occ_id:
                cursor.execute("""
                    UPDATE occupation SET occ_type = %s, bus_nature = %s
                    WHERE occ_id = %s;
                """, (occ_type, bus_nature, current_occ_id))
            else: # If customer had no occupation, create one
                if occ_type or bus_nature:
                    new_occ_id = _generate_next_id(cursor, 'occupation', 'occ_id', 'OC', 2)
                    cursor.execute("INSERT INTO occupation (occ_id, occ_type, bus_nature) VALUES (%s, %s, %s);", (new_occ_id, occ_type, bus_nature))
                    cursor.execute("UPDATE customer SET occ_id = %s WHERE cust_no = %s;", (new_occ_id, cust_no))

            # --- Update Financial Record Table ---
            if current_fin_code:
                cursor.execute("""
                    UPDATE financial_record
                    SET source_wealth = %s, mon_income = %s, ann_income = %s
                    WHERE fin_code = %s;
                """, (source_wealth, mon_income, ann_income, current_fin_code))
            else: # If customer had no financial record, create one
                if source_wealth or mon_income or ann_income:
                    new_fin_code = _generate_next_id(cursor, 'financial_record', 'fin_code', 'F', 1)
                    cursor.execute("INSERT INTO financial_record (fin_code, source_wealth, mon_income, ann_income) VALUES (%s, %s, %s, %s);", (new_fin_code, source_wealth, mon_income, ann_income))
                    cursor.execute("UPDATE customer SET fin_code = %s WHERE cust_no = %s;", (new_fin_code, cust_no))


            # --- Update Spouse Table (Conditional insert/update/delete) ---
            if civilstatus == 'Married' and sp_name and sp_datebirth and sp_profession:
                cursor.execute("SELECT spouse_id FROM spouse WHERE cust_no = %s;", (cust_no,))
                existing_spouse_id_result = cursor.fetchone()

                if existing_spouse_id_result:
                    existing_spouse_id = existing_spouse_id_result['spouse_id']
                    cursor.execute("""
                        UPDATE spouse
                        SET sp_name = %s, sp_datebirth = %s, sp_profession = %s
                        WHERE spouse_id = %s;
                    """, (sp_name, sp_datebirth, sp_profession, existing_spouse_id))
                else: # Insert new spouse details
                    new_spouse_id = _generate_next_id(cursor, 'spouse', 'spouse_id', 'SP', 1)
                    cursor.execute("INSERT INTO spouse (spouse_id, cust_no, sp_name, sp_datebirth, sp_profession) VALUES (%s, %s, %s, %s, %s);",
                                   (new_spouse_id, cust_no, sp_name, sp_datebirth, sp_profession))
            else:
                cursor.execute("DELETE FROM spouse WHERE cust_no = %s;", (cust_no,)) 

            # --- Update Employer Details and Employment Details (Complex - simplified) ---
            if occ_type == 'Employed' and empname: 
                cursor.execute("SELECT emp_id FROM employment_details WHERE cust_no = %s;", (cust_no,))
                existing_emp_id_result = cursor.fetchone()
                existing_emp_id = existing_emp_id_result['emp_id'] if existing_emp_id_result else None

                if existing_emp_id:
                    cursor.execute("""
                        UPDATE employer_details
                        SET occ_id = %s, tin_id = %s, empname = %s, emp_address = %s, phonefax_no = %s, job_title = %s, emp_date = %s
                        WHERE emp_id = %s;
                    """, (current_occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date, existing_emp_id))
                else: 
                    new_emp_id = _generate_next_id(cursor, 'employer_details', 'emp_id', 'EMP', 3)
                    sql_emp_details = "INSERT INTO employer_details (emp_id, occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);"
                    cursor.execute(sql_emp_details, (new_emp_id, current_occ_id, tin_id, empname, emp_address, phonefax_no, job_title, emp_date))
                    cursor.execute("INSERT INTO employment_details (cust_no, emp_id) VALUES (%s, %s);", (cust_no, new_emp_id))
            else: # If not employed or employer name is removed, delete employer details
                # Delete from employment_details first (FK constraint)
                cursor.execute("DELETE FROM employment_details WHERE cust_no = %s;", (cust_no,))
                # Now check and delete from employer_details if no other employment_details reference it
                # This logic is simplified: it might not fully clean up if the employer_details
                # was linked to other customers (which is not expected in this schema where occ_id links)
                # A more robust solution would be to check if emp_id is referenced anywhere else before deleting from employer_details
                # For now, if no employment_details link exists for this emp_id, delete it
                if current_occ_id: 
                    cursor.execute("SELECT emp_id FROM employer_details WHERE occ_id = %s AND emp_id NOT IN (SELECT emp_id FROM employment_details);", (current_occ_id,))
                    orphaned_emp_ids = cursor.fetchall()
                    for emp_id_to_delete in orphaned_emp_ids:
                        cursor.execute("DELETE FROM employer_details WHERE emp_id = %s;", (emp_id_to_delete[0],))


            # --- Update Dynamic Lists: Company Affiliations, Existing Banks, Public Official Relationships ---
            # Company Affiliations
            cursor.execute("DELETE FROM company_affiliation WHERE cust_no = %s;", (cust_no,)) 
            depositor_roles = request.form.getlist('depositor_role[]')
            dep_compnames = request.form.getlist('dep_compname[]')
            for role, comp_name in zip(depositor_roles, dep_compnames):
                if role and comp_name: 
                    cursor.execute("INSERT INTO company_affiliation (cust_no, depositor_role, dep_compname) VALUES (%s, %s, %s);", (cust_no, role, comp_name)) 

            # Existing Bank Accounts
            cursor.execute("DELETE FROM existing_bank WHERE cust_no = %s;", (cust_no,)) 
            bank_names = request.form.getlist('bank_name[]')
            branches = request.form.getlist('branch[]')
            acc_types = request.form.getlist('acc_type[]')
            for b_name, branch, a_type in zip(bank_names, branches, acc_types):
                if b_name and branch and a_type: 
                    # Check if bank_details already exists (by name and branch)
                    cursor.execute("SELECT bank_code FROM bank_details WHERE bank_name = %s AND branch = %s;", (b_name, branch))
                    existing_bank_code = cursor.fetchone()

                    if existing_bank_code:
                        current_bank_code = existing_bank_code['bank_code']
                    else:
                        current_bank_code = _generate_next_id(cursor, 'bank_details', 'bank_code', 'B', 1)
                        cursor.execute("INSERT INTO bank_details (bank_code, bank_name, branch) VALUES (%s, %s, %s);", (current_bank_code, b_name, branch))
                    
                    cursor.execute("INSERT INTO existing_bank (cust_no, bank_code, acc_type) VALUES (%s, %s, %s);", (cust_no, current_bank_code, a_type)) 

            # Public Official Relationships
            cursor.execute("DELETE FROM cust_po_relationship WHERE cust_no = %s;", (cust_no,)) 
            gov_int_names = request.form.getlist('gov_int_name[]')
            official_positions = request.form.getlist('official_position[]')
            branch_orgnames = request.form.getlist('branch_orgname[]')
            relation_descs = request.form.getlist('relation_desc[]')

            min_len_po = min(len(gov_int_names), len(official_positions), len(branch_orgnames), len(relation_descs))
            for i in range(min_len_po):
                gov_name = gov_int_names[i]
                pos = official_positions[i]
                org = branch_orgnames[i]
                rel_desc = relation_descs[i]

                if gov_name and pos and org and rel_desc: 
                    cursor.execute("SELECT gov_int_id FROM public_official_details WHERE gov_int_name = %s AND official_position = %s AND branch_orgname = %s;", (gov_name, pos, org))
                    po_id_result = cursor.fetchone()
                    if po_id_result:
                        gov_int_id = po_id_result['gov_int_id']
                    else:
                        gov_int_id = _generate_next_id(cursor, 'public_official_details', 'gov_int_id', 'OFF', 3)
                        cursor.execute("INSERT INTO public_official_details (gov_int_id, gov_int_name, official_position, branch_orgname) VALUES (%s, %s, %s, %s);", (gov_int_id, gov_name, pos, org))
                    
                    cursor.execute("INSERT INTO cust_po_relationship (cust_no, gov_int_id, relation_desc) VALUES (%s, %s, %s);", (cust_no, gov_int_id, rel_desc)) 
            
            conn.commit()
            flash('Customer details updated successfully!', 'success')
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
            return redirect(url_for('admin_dashboard_page')) 

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
        if debug_mode:
            raise
        flash(f'An error occurred while fetching customer data: {err}', 'danger')
        return redirect(url_for('admin_dashboard_page')) 
    except Exception as e:
        print(f"Error in admin_edit_customer: {e}")
        if debug_mode:
            raise
        flash('An unexpected error occurred while loading customer details for editing.', 'danger')
        return redirect(url_for('admin_dashboard_page')) 
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
        return redirect(url_for('admin_dashboard_page')) 

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            if debug_mode:
                raise Exception("Database connection failed for delete_customer.")
            flash('Database connection failed.', 'danger')
            return redirect(url_for('admin_dashboard_page')) 

        cursor = conn.cursor()
        conn.autocommit = False 

        # 1. Get occ_id and fin_code before deleting the customer
        cursor.execute("SELECT fin_code, occ_id FROM customer WHERE cust_no = %s", (cust_no,)) 
        customer_info = cursor.fetchone()
        
        if not customer_info: # If customer not found, nothing to delete
            flash(f'Customer {cust_no} not found for deletion.', 'warning')
            conn.rollback() 
            return redirect(url_for('admin_dashboard_page'))

        fin_code, occ_id = customer_info 

        cursor.execute("DELETE FROM customer WHERE cust_no = %s", (cust_no,)) 
        
        # 3. Handle deletion of financial_record and occupation if they are no longer referenced
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
    _ensure_database_schema() 
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
