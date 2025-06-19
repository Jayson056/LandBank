-- PostgreSQL Schema for LandBank2025

-- Drop tables if they exist to allow for clean re-creation.
-- Order of dropping tables is important due to foreign key dependencies.
DROP TABLE IF EXISTS credentials CASCADE;
DROP TABLE IF EXISTS employment_details CASCADE;
DROP TABLE IF EXISTS spouse CASCADE;
DROP TABLE IF EXISTS company_affiliation CASCADE;
DROP TABLE IF EXISTS existing_bank CASCADE;
DROP TABLE IF EXISTS cust_po_relationship CASCADE;
DROP TABLE IF EXISTS customer CASCADE;
DROP TABLE IF EXISTS employer_details CASCADE; -- Must be dropped before occupation if it references occupation
DROP TABLE IF EXISTS public_official_details CASCADE;
DROP TABLE IF EXISTS financial_record CASCADE;
DROP TABLE IF EXISTS occupation CASCADE;
DROP TABLE IF EXISTS bank_details CASCADE;


-- Re-create tables with VARCHAR primary keys and adjusted structures
-- based on your provided MySQL DDL, adapted for PostgreSQL.

-- Table: occupation
CREATE TABLE IF NOT EXISTS occupation (
    occ_id VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR to match your data format (e.g., 'OC01')
    occ_type VARCHAR(255) NOT NULL,
    bus_nature VARCHAR(255)
);

-- Table: financial_record
-- IMPORTANT ASSUMPTION:
-- Your original financial_record INSERT data sometimes included 'cust_no',
-- but the table definition here has 'fin_code' as PRIMARY KEY and 'customer' links to it via 'fin_code'.
-- We are keeping 'fin_code' as the primary key of financial_record.
-- 'mon_income' and 'ann_income' are kept as VARCHAR(255) as per your DDL,
-- assuming they might store formatted strings (e.g., with currency symbols) rather than pure numbers.
CREATE TABLE IF NOT EXISTS financial_record (
    fin_code VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR to match your data format (e.g., 'F1')
    source_wealth VARCHAR(255),
    mon_income VARCHAR(255),
    ann_income VARCHAR(255)
);

-- Table: customer
CREATE TABLE IF NOT EXISTS customer (
    cust_no VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR to match your data format (e.g., 'C001')
    custname VARCHAR(255) NOT NULL,
    datebirth DATE,
    nationality VARCHAR(100),
    citizenship VARCHAR(100),
    custsex VARCHAR(10),
    placebirth VARCHAR(255),
    civilstatus VARCHAR(50),
    num_children INTEGER, -- PostgreSQL uses INTEGER for INT
    mmaiden_name VARCHAR(255),
    cust_address VARCHAR(255),
    email_address VARCHAR(255) UNIQUE NOT NULL,
    contact_no VARCHAR(20),
    occ_id VARCHAR(10) NOT NULL, -- Must be NOT NULL as per your DDL
    fin_code VARCHAR(10) NOT NULL, -- Must be NOT NULL as per your DDL
    FOREIGN KEY (occ_id) REFERENCES occupation(occ_id) ON DELETE RESTRICT, -- Prevent deletion of occupation if referenced
    FOREIGN KEY (fin_code) REFERENCES financial_record(fin_code) ON DELETE RESTRICT -- Prevent deletion of financial_record if referenced
);

-- Table: credentials
-- Assuming a 1-to-1 relationship between customer and credentials based on cust_no being PRIMARY KEY here.
CREATE TABLE IF NOT EXISTS credentials (
    cust_no VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    FOREIGN KEY (cust_no) REFERENCES customer(cust_no) ON DELETE CASCADE -- Delete credentials if customer is deleted
);

-- Table: employer_details
CREATE TABLE IF NOT EXISTS employer_details (
    emp_id VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR to match your data format (e.g., 'EMP01')
    occ_id VARCHAR(10), -- Added as per your insert data, assuming it's a foreign key
    tin_id VARCHAR(50),
    empname VARCHAR(255) NOT NULL,
    emp_address VARCHAR(255),
    phonefax_no VARCHAR(20),
    job_title VARCHAR(100),
    emp_date DATE,
    FOREIGN KEY (occ_id) REFERENCES occupation(occ_id) ON DELETE SET NULL -- Set occ_id to NULL if occupation is deleted
);

-- Table: employment_details
CREATE TABLE IF NOT EXISTS employment_details (
    cust_no VARCHAR(10), -- Maintained as VARCHAR
    emp_id VARCHAR(10), -- Maintained as VARCHAR
    PRIMARY KEY (cust_no, emp_id),
    FOREIGN KEY (cust_no) REFERENCES customer(cust_no) ON DELETE CASCADE, -- Delete employment details if customer is deleted
    FOREIGN KEY (emp_id) REFERENCES employer_details(emp_id) ON DELETE CASCADE -- Delete employment details if employer is deleted
);

-- Table: spouse
-- Assuming a 1-to-1 relationship between customer and spouse based on cust_no being PRIMARY KEY here.
CREATE TABLE IF NOT EXISTS spouse (
    cust_no VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR
    sp_code VARCHAR(10), -- Included as per your DDL
    sp_name VARCHAR(255),
    sp_datebirth DATE,
    sp_profession VARCHAR(255),
    FOREIGN KEY (cust_no) REFERENCES customer(cust_no) ON DELETE CASCADE -- Delete spouse record if customer is deleted
);

-- Table: company_affiliation
CREATE TABLE IF NOT EXISTS company_affiliation (
    comp_aff_id SERIAL PRIMARY KEY, -- PostgreSQL equivalent of AUTO_INCREMENT
    cust_no VARCHAR(10) NOT NULL, -- Maintained as VARCHAR
    depositor_role VARCHAR(255),
    dep_compname VARCHAR(255),
    FOREIGN KEY (cust_no) REFERENCES customer(cust_no) ON DELETE CASCADE -- Delete affiliations if customer is deleted
);

-- Table: bank_details
CREATE TABLE IF NOT EXISTS bank_details (
    bank_code VARCHAR(50) PRIMARY KEY,
    bank_name VARCHAR(255) NOT NULL,
    branch VARCHAR(255)
);

-- Table: existing_bank
CREATE TABLE IF NOT EXISTS existing_bank (
    existing_bank_id SERIAL PRIMARY KEY, -- PostgreSQL equivalent of AUTO_INCREMENT
    cust_no VARCHAR(10) NOT NULL, -- Maintained as VARCHAR
    bank_code VARCHAR(50) NOT NULL,
    acc_type VARCHAR(100),
    FOREIGN KEY (cust_no) REFERENCES customer(cust_no) ON DELETE CASCADE, -- Delete existing bank records if customer is deleted
    FOREIGN KEY (bank_code) REFERENCES bank_details(bank_code) ON DELETE CASCADE -- Delete existing bank records if bank details are deleted
);

-- Table: public_official_details
CREATE TABLE IF NOT EXISTS public_official_details (
    gov_int_id VARCHAR(10) PRIMARY KEY, -- Maintained as VARCHAR to match your data format (e.g., 'OFF001')
    gov_int_name VARCHAR(255) NOT NULL,
    official_position VARCHAR(255),
    branch_orgname VARCHAR(255)
);

-- Table: cust_po_relationship
CREATE TABLE IF NOT EXISTS cust_po_relationship (
    cust_no VARCHAR(10) NOT NULL, -- Maintained as VARCHAR
    gov_int_id VARCHAR(10) NOT NULL, -- Maintained as VARCHAR
    relation_desc VARCHAR(255) NOT NULL,
    PRIMARY KEY (cust_no, gov_int_id, relation_desc), -- Composite primary key as in your DDL
    FOREIGN KEY (cust_no) REFERENCES customer(cust_no) ON DELETE CASCADE, -- Delete relationship if customer is deleted
    FOREIGN KEY (gov_int_id) REFERENCES public_official_details(gov_int_id) ON DELETE CASCADE -- Delete relationship if public official details are deleted
);
