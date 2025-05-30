-- landbank.sql
-- PostgreSQL compatible schema with IF NOT EXISTS

-- Reference Tables (ID Generators)
CREATE TABLE IF NOT EXISTS SpouseCode (
    spouse_code SERIAL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS Occupation (
    occ_id SERIAL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS FinancialRecord (
    fin_code SERIAL PRIMARY KEY
);

-- Main Customer Table
CREATE TABLE IF NOT EXISTS Customer (
    cust_no VARCHAR(10) PRIMARY KEY,
    custname VARCHAR(50) NOT NULL,
    datebirth DATE NOT NULL,
    nationality VARCHAR(20) NOT NULL,
    citizenship VARCHAR(20) NOT NULL,
    custsex VARCHAR(1) CHECK (custsex IN ('M', 'F')) NOT NULL,
    placebirth VARCHAR(100) NOT NULL,
    civilstatus VARCHAR(20) CHECK (civilstatus IN ('Single', 'Married', 'Widowed', 'Divorced', 'Separated')) NOT NULL,
    num_children INT NOT NULL,
    mmaiden_name VARCHAR(50) NOT NULL,
    cust_address VARCHAR(100) NOT NULL,
    email_address VARCHAR(50) NOT NULL UNIQUE,
    contact_no VARCHAR(20) NOT NULL,
    spouse_code INT,
    occ_id INT,
    fin_code INT,
    password VARCHAR(255) NOT NULL, -- Added password field for login
    FOREIGN KEY (spouse_code) REFERENCES SpouseCode(spouse_code) ON DELETE SET NULL,
    FOREIGN KEY (occ_id) REFERENCES Occupation(occ_id) ON DELETE SET NULL,
    FOREIGN KEY (fin_code) REFERENCES FinancialRecord(fin_code) ON DELETE SET NULL
);

-- Optional Spouse Details
CREATE TABLE IF NOT EXISTS Spouse (
    spouse_id SERIAL PRIMARY KEY,
    spouse_code INT UNIQUE,
    name VARCHAR(50),
    birthdate DATE,
    profession VARCHAR(50),
    FOREIGN KEY (spouse_code) REFERENCES SpouseCode(spouse_code) ON DELETE CASCADE
);

-- Dummy data for testing (optional, remove for production)
-- INSERT INTO Customer (cust_no, custname, datebirth, nationality, citizenship, custsex, placebirth, civilstatus, num_children, mmaiden_name, cust_address, email_address, contact_no, password)
-- VALUES ('admin', 'Admin User', '1980-01-01', 'Filipino', 'Filipino', 'M', 'Manila', 'Married', 0, 'N/A', 'Admin Office', 'landbankADMIN@gmail.com', '09171234567', 'LandBank2025')
-- ON CONFLICT (cust_no) DO NOTHING;
