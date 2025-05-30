CREATE TABLE IF NOT EXISTS Customer (
    cust_no VARCHAR(10) PRIMARY KEY,
    custname VARCHAR(100) NOT NULL,
    email_address VARCHAR(100) UNIQUE NOT NULL,
    phone_no VARCHAR(20),
    address VARCHAR(255),
    password VARCHAR(255) NOT NULL,
    account_balance DECIMAL(15, 2) DEFAULT 0.00
);

CREATE TABLE IF NOT EXISTS SpouseCode (
    spouse_code VARCHAR(10) PRIMARY KEY,
    description VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Occupation (
    occupation_code VARCHAR(10) PRIMARY KEY,
    description VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS FinancialRecord (
    record_id SERIAL PRIMARY KEY,
    cust_no VARCHAR(10) REFERENCES Customer(cust_no),
    record_type VARCHAR(50), -- e.g., 'deposit', 'withdrawal', 'transfer'
    amount DECIMAL(15, 2) NOT NULL,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add any other tables you have with IF NOT EXISTS
-- CREATE TABLE IF NOT EXISTS AnotherTable ( ... );

-- You might also want to add initial data if needed, but ensure it's idempotent
-- E.g., INSERT INTO SpouseCode (spouse_code, description) VALUES ('S001', 'Married') ON CONFLICT (spouse_code) DO NOTHING;
