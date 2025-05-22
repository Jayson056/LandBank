from flask import Flask, render_template, request, redirect
import mysql.connector
from config import db_config

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/customers')
def customer_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer")
    customers = cursor.fetchall()
    conn.close()
    return render_template('customer_list.html', customers=customers)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Customer (cust_no, custname, datebirth, nationality, citizenship, custsex, placebirth,
        civilstatus, mmaiden_name, num_children, cust_address, email_address, contact_no)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['cust_no'], data['custname'], data['datebirth'], data['nationality'], data['citizenship'],
        data['custsex'], data['placebirth'], data['civilstatus'], data['mmaiden_name'], data['num_children'],
        data['cust_address'], data['email_address'], data['contact_no']
    ))
    conn.commit()
    conn.close()
    return redirect('/customers')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=0000, debug=True)  # Set a valid port number (e.g., 5000)
