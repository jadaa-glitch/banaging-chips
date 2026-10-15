from app import create_app, database

app = create_app()

with app.app_context():
    db = database.get_db()
    with db.cursor() as cur:
        # 1. Clean deleted_sales (4 old sample deleted records from May 2025)
        cur.execute("DELETE FROM deleted_sales")
        print("Cleared dummy deleted_sales records.")
        
        # 2. Clean import_batches and errors
        cur.execute("DELETE FROM import_errors")
        cur.execute("DELETE FROM import_batches")
        print("Cleared dummy import_batches records.")

        # 3. Clean orphan/dummy customers (13 sample customers with 0 sales)
        cur.execute("DELETE FROM customers WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM sales)")
        print(f"Removed {cur.rowcount} dummy customers with 0 sales.")

        # 4. Remove dummy user juanitolim
        cur.execute("DELETE FROM users WHERE username = 'juanitolim'")
        print("Removed dummy test user 'juanitolim'.")

        # 5. Update batch_reference in sales to clean value
        cur.execute("UPDATE sales SET batch_reference = 'IT305-CLEANED'")
        print("Updated batch_reference to 'IT305-CLEANED'.")

        # 6. Re-order and re-sequence sales sale_id from 1 to 1276
        cur.execute("CREATE TEMPORARY TABLE temp_sales AS SELECT * FROM sales ORDER BY sale_date ASC, sale_id ASC")
        cur.execute("DELETE FROM sales")
        cur.execute("ALTER TABLE sales AUTO_INCREMENT = 1")
        cur.execute("""
            INSERT INTO sales (sale_date, customer_id, product_id, quantity, unit_price, amount_paid, payment_method, notes, batch_reference, recorded_by, import_batch_id, created_at)
            SELECT sale_date, customer_id, product_id, quantity, unit_price, amount_paid, payment_method, notes, batch_reference, recorded_by, import_batch_id, created_at
            FROM temp_sales
        """)
        cur.execute("DROP TEMPORARY TABLE temp_sales")
        print("Successfully re-sequenced sales table from sale_id = 1 to 1276.")

    db.commit()

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) as c, MIN(sale_id) as min_id, MAX(sale_id) as max_id, SUM(quantity) as qty, SUM(amount_paid) as rev FROM sales")
        s_info = cur.fetchone()
        print("\n=== FINAL CLEAN DATABASE AUDIT ===")
        print(f"  Sales Total Rows: {s_info['c']}")
        print(f"  Sales ID Range:   REC-{s_info['min_id']:04d} to REC-{s_info['max_id']:04d}")
        print(f"  Sales Volume:     {s_info['qty']} packs")
        print(f"  Sales Revenue:    PHP {float(s_info['rev']):,.2f}")
        
        cur.execute("SELECT COUNT(*) as c FROM customers")
        print(f"  Real Customers:   {cur.fetchone()['c']}")
        
        cur.execute("SELECT COUNT(*) as c FROM deleted_sales")
        print(f"  Trash / Deleted:  {cur.fetchone()['c']}")
        
        cur.execute("SELECT user_id, username, full_name, role FROM users")
        print(f"  Active Users:     {cur.fetchall()}")
        print("==================================")
