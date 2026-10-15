import openpyxl
from datetime import datetime
from app import create_app
from app.database import get_db

app = create_app()

print("Opening IT_305_cleaned.xlsx...")
wb = openpyxl.load_workbook('IT_305_cleaned.xlsx', data_only=True)
ws = wb['Cleaned Data']
rows = list(ws.iter_rows(values_only=True))[1:]
print(f"Total rows found in Cleaned Data sheet: {len(rows)}")

with app.app_context():
    db = get_db()
    
    # 1. Update product catalog pricing and ensure Unspecified exists
    with db.cursor() as cur:
        cur.execute("UPDATE products SET unit_price = 45.00 WHERE unit_price IS NOT NULL")
        cur.execute("SELECT product_id FROM products WHERE flavor_name = 'Unspecified'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO products (flavor_name, display_name, description, unit_price, badge_color, is_active)
                VALUES ('Unspecified', 'Assorted / Unspecified', 'Multi-flavor or Unspecified Pack', 45.00, '#8E24AA', 0)
            """)
    db.commit()

    # 2. Cache product IDs
    with db.cursor() as cur:
        cur.execute("SELECT product_id, flavor_name FROM products")
        product_map = {p['flavor_name'].strip().lower(): p['product_id'] for p in cur.fetchall()}
    print("Product ID mapping:", product_map)

    # 3. Get Store Manager user id for recorded_by
    with db.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE username = 'daniellajaralve'")
        user_row = cur.fetchone()
        recorded_by = user_row['user_id'] if user_row else 1
    print(f"Using recorded_by user_id: {recorded_by}")

    # 4. Insert all unique customer names and commit
    customer_names = set()
    for r in rows:
        name = str(r[1]).strip() if r[1] else 'Unknown'
        customer_names.add(name)

    print(f"Ensuring {len(customer_names)} unique customers in customers table...")
    with db.cursor() as cur:
        for name in customer_names:
            cur.execute("INSERT IGNORE INTO customers (customer_name) VALUES (%s)", (name,))
    db.commit()
    print("Committed all customers to database.")

    # 5. Build robust customer map
    with db.cursor() as cur:
        cur.execute("SELECT customer_id, customer_name FROM customers")
        customer_map = {c['customer_name']: c['customer_id'] for c in cur.fetchall()}
    print(f"Cached {len(customer_map)} customer mappings.")

    # Helper function to get customer_id with MySQL fallback
    def get_customer_id(cur, name):
        if name in customer_map:
            return customer_map[name]
        cur.execute("SELECT customer_id FROM customers WHERE customer_name = %s", (name,))
        row = cur.fetchone()
        if row:
            customer_map[name] = row['customer_id']
            return row['customer_id']
        return None

    # 6. Clear placeholder sales
    with db.cursor() as cur:
        cur.execute("DELETE FROM sales")
    db.commit()
    print("Cleared previous placeholder sales.")

    # 7. Prepare and insert sales records
    sales_to_insert = []
    missing_cust = []
    with db.cursor() as cur:
        for idx, r in enumerate(rows, 1):
            d_val, name_val, flavor_val, qty_val, price_val = r

            if isinstance(d_val, datetime):
                s_date = d_val.strftime('%Y-%m-%d')
            else:
                s_date = str(d_val)[:10]

            c_name = str(name_val).strip() if name_val else 'Unknown'
            cust_id = get_customer_id(cur, c_name)
            if not cust_id:
                missing_cust.append((idx, c_name))

            f_key = str(flavor_val).strip().lower() if flavor_val else 'unspecified'
            prod_id = product_map.get(f_key, product_map.get('unspecified'))

            qty = int(qty_val or 1)
            amount = float(price_val or (qty * 45.00))
            unit_price = 45.00

            sales_to_insert.append((s_date, cust_id, prod_id, qty, unit_price, amount, recorded_by))

    if missing_cust:
        print(f"ERROR: {len(missing_cust)} rows have missing customer IDs:", missing_cust[:5])
        exit(1)

    print(f"Inserting {len(sales_to_insert)} sales transactions...")
    with db.cursor() as cur:
        cur.executemany("""
            INSERT INTO sales (sale_date, customer_id, product_id, quantity, unit_price, amount_paid, recorded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, sales_to_insert)
    db.commit()
    print("Successfully committed all sales to MySQL!")

    # 8. Run Verification Query
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total_rows, SUM(quantity) as total_qty, SUM(amount_paid) as total_rev FROM sales")
        res = cur.fetchone()
        total_rows = res['total_rows']
        total_qty = res['total_qty']
        total_rev = float(res['total_rev'])

    print("\n" + "="*50)
    print("DATABASE INGESTION AUDIT REPORT:")
    print(f"  Total Transactions: {total_rows}")
    print(f"  Total Packs Sold:   {total_qty} units")
    print(f"  Total Sales Sum:    PHP {total_rev:,.2f}")
    print("="*50)

    assert total_rows == 1276, f"Expected 1276, got {total_rows}"
    assert total_qty == 1648, f"Expected 1648, got {total_qty}"
    assert abs(total_rev - 74160.00) < 0.01, f"Expected 74160.00, got {total_rev}"
    print("\nALL DATA INTEGRITY CHECKS PASSED WITH 100% ACCURACY!")
