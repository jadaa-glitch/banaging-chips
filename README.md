# Banaging Chips — Sales Recording & BI Dashboard System

Internal Sales Recording and Business Intelligence (BI) Analytics System built for **Crispy Delight — E & E Banaging Chips**.

---

## 🍌 Features Implemented

1. **Terminal Authentication**
   * Pre-configured login matching `Login.png`.
   * Staff registration matching `Sign Up.png` with role assignment.
2. **Interactive BI Dashboard**
   * Top KPI cards: Total Sales, Total Quantity Sold, Transactions, and Top-Selling Flavor.
   * Monthly Revenue progression trend (spline/gradient line chart).
   * Revenue breakdown by flavor with 4 mini metric cards.
   * Flavor share (%) donut chart with exact flavor color tokens.
   * Daily sales bar chart for the last 14 days with velocity metrics.
   * Live-synced recent transactions table.
3. **Sales Ledger Management**
   * Customer search, flavor dropdown filter, date range filters.
   * Shift summary (Today's revenue and units sold).
   * Add Record form with interactive flavor selection cards, quantity stepper, and auto-computed total locked display.
   * Edit Record form with audit log callout and immutable entry timestamps.
   * Soft-delete confirmation modal with audit reason tracking.
   * Shift report printing and CSV export.
4. **Deleted Records Archive**
   * 365-day mandatory retention ledger view.
   * Voided value, reclaimed pack tracking, and staff auditor indicators.
   * Deletion breakdown by cause analytics widget.
   * One-click record restoration back to the active ledger.
5. **Excel / CSV Batch Data Ingestion (Option A)**
   * File dropzone for `.csv` and `.xlsx` files.
   * Validation engine verifying dates, customer names, flavor catalog matching, and positive quantities.
   * Validation staging table showing valid rows and flagging specific row errors.
   * Sample CSV template download.

---

## 🚀 How to Run

### 1. Start the Flask Application
Open PowerShell in the project directory and run:

```powershell
.\venv\Scripts\python.exe run.py
```

The application will start on: **`http://localhost:5000`**

### 2. Default Login Credentials
* **Username**: `daniellajaralve`
* **Password**: `password123`
* **Role**: `Store Manager`

*(Additional Cashier account seeded: `juanitolim` / `password123`)*

---

## 🗄️ Database Configuration
* **Engine**: MySQL 8.0+ / MariaDB
* **Host**: `localhost:3306`
* **Database**: `banaging_chips`
* **User**: `root`
* **Password**: *(default empty)*
* **Schema file**: [`schema.sql`](schema.sql)
