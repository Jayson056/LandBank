# 🏦 LandBank Customer Information Management System (CIMS)

> **Academic Course Project** | **Information Management Course (IM)**  
> **Type**: Group Project Requirements &bull; Fullstack Web Application  
> **Live Web Application**: [https://landbank-k6bl.onrender.com/](https://landbank-k6bl.onrender.com/)  

---

## 📌 Project Overview

The **LandBank Customer Information Management System (CIMS)** is a fullstack web-based banking portal and data management system developed as a core requirement for the **Information Management Course**. Modeled after the operational requirements of the **Land Bank of the Philippines**, the project demonstrates best practices in **relational database architecture, data normalization, secure customer onboarding (KYC), and administrative record governance**.

Traditional bank customer onboarding relies heavily on manual paper-based forms that are prone to data redundancy, lost paperwork, and compliance audit delays. This project digitizes and streamlines the entire customer registration pipeline through an interactive multi-step workflow connected to a relational database.

---

## 🎯 Course Project Objectives

1. **Relational Database Design & Implementation**: Design a normalized database schema enforcing referential integrity, foreign key constraints, and audit trails.
2. **Digital KYC (Know Your Customer) Workflow**: Implement a structured multi-phase data collection pipeline capturing personal, occupational, and financial data according to banking standards.
3. **Data Retrieval & Lifecycle Management**: Build full CRUD (Create, Read, Update, Delete) administrative capabilities for managing banking customer profiles.
4. **Document Generation**: Provide automated generation of printable official account opening registration documents.
5. **System Security & Audit Logging**: Implement administrative session controls and audit logging for sensitive customer updates.

---

## 🚀 Key Features

### 1. Multi-Step Digital KYC Onboarding Pipeline
- **Step 1: Personal Profile (`/registration1`)**: Captures legal names, contact information, date of birth, civil status, and residential address.
- **Step 2: Occupation & Employment (`/registration2`)**: Records employment status, industry category, employer/business name, and occupational classifications.
- **Step 3: Financial & Source of Wealth (`/registration3`)**: Classifies income sources, estimated gross monthly earnings, and regulatory compliance flags.

### 2. Printable Official Bank Documents (`/registrationPrint`)
- Generates a print-ready, officially styled LandBank customer enrollment form populated dynamically with the customer's recorded data.
- Standardized layout suitable for physical archiving or customer signature verification.

### 3. Administrative CIMS Dashboard (`/admin_dashboard`)
- **Centralized Customer Registry**: Search, filter, and view all registered bank customers.
- **Record Inspector (`/admin_view_customer`)**: Detailed multi-tab inspection of personal, employment, and financial data.
- **Customer Record Editor (`/admin_edit_customer`)**: Full administrative edit privileges with data validation.
- **Audit Trails (`admin_logs.txt`)**: Logs administrative updates, record changes, and access timestamps for compliance tracking.

---

## 🛠️ Tech Stack & Architecture

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3 &bull; Flask | Routing, request validation, business logic, and template rendering |
| **Database Engine** | PostgreSQL (`psycopg2`) / MySQL | Normalized relational schema for customer records and financial data |
| **Frontend** | HTML5, CSS3, Bootstrap 5, JavaScript | Responsive banking portal UI with glassmorphism styling |
| **Document Generation** | CSS Paged Media / HTML Print API | High-fidelity printable customer account opening forms |
| **Cloud Deployment** | Render Cloud Platform | Containerized web service connected to managed PostgreSQL |

---

## 🗄️ Database Architecture

The system utilizes a normalized relational database schema defined in [`landbank.sql`](landbank.sql):

- `customer_personal`: Stores primary customer identification, contact info, and demographics.
- `occupation`: Normalizes occupation types, business nature, and employment classifications.
- `financial_record`: Tracks verified wealth sources, gross income brackets, and financial background.
- `admin_logs`: Records timestamped administrative activities and record modifications.

---

## 💻 Local Setup & Installation

### Prerequisites
- Python 3.10+
- PostgreSQL or MySQL Server
- Git

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Jayson056/LandBank.git
   cd LandBank
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install project dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Database Connection:**
   Create a `.env` or set environment variables:
   ```env
   DATABASE_URL=postgresql://username:password@localhost:5432/landbank
   SECRET_KEY=your_secret_key_here
   FLASK_DEBUG=True
   ```
   *(Alternatively, configure local credentials in `db_config.py`).*

5. **Initialize Database Schema:**
   Import the SQL tables into your PostgreSQL/MySQL instance:
   ```bash
   psql -U username -d landbank -f landbank.sql
   ```

6. **Run the Application:**
   ```bash
   python app.py
   ```
   Open your browser and navigate to `http://localhost:5000/`.

---

## 👥 Academic Credits

- **Course**: Information Management (IM) Course Project
- **Project Structure**: Academic Group Requirement
- **Lead Developer & System Architect**: [Jayson Apable Combate (Jayson056)](https://github.com/Jayson056)
- **Institution**: Polytechnic University of the Philippines (PUP)

---

## 📄 License
This project was developed for educational and academic assessment purposes as part of the Information Management curriculum. All trademarks and brand assets (Land Bank of the Philippines) belong to their respective owners.
