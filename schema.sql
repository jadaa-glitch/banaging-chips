-- Banaging Chips Database Schema
-- Compatible with MySQL 8.0+ / MariaDB

CREATE DATABASE IF NOT EXISTS banaging_chips;
USE banaging_chips;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'Cashier / Sales Clerk',
    is_verified TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Products / Flavors Table
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    flavor_name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(255) NULL,
    unit_price DECIMAL(8,2) NOT NULL DEFAULT 50.00,
    badge_color VARCHAR(20) DEFAULT '#F5A623',
    is_active TINYINT(1) NOT NULL DEFAULT 1
);

-- 4. Import Batches Table (Tracks CSV/Excel uploads)
CREATE TABLE IF NOT EXISTS import_batches (
    batch_id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    total_rows INT DEFAULT 0,
    imported_rows INT DEFAULT 0,
    failed_rows INT DEFAULT 0,
    imported_by INT NOT NULL,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    FOREIGN KEY (imported_by) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 5. Import Errors Table (Row-level validation issues)
CREATE TABLE IF NOT EXISTS import_errors (
    error_id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    row_number INT NOT NULL,
    raw_data TEXT,
    error_message VARCHAR(255) NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES import_batches(batch_id) ON DELETE CASCADE
);

-- 6. Sales Table
CREATE TABLE IF NOT EXISTS sales (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_date DATE NOT NULL,
    customer_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(8,2) NOT NULL DEFAULT 50.00,
    amount_paid DECIMAL(10,2) NOT NULL,
    payment_method ENUM('Cash on Hand', 'GCash Transfer') NOT NULL DEFAULT 'Cash on Hand',
    notes TEXT,
    batch_reference VARCHAR(50) DEFAULT 'BATCH-2025-05B',
    recorded_by INT NOT NULL,
    import_batch_id INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (recorded_by) REFERENCES users(user_id),
    FOREIGN KEY (import_batch_id) REFERENCES import_batches(batch_id) ON DELETE SET NULL
);

-- 7. Deleted Sales Archive Table
CREATE TABLE IF NOT EXISTS deleted_sales (
    archive_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    sale_date DATE NOT NULL,
    customer_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    amount_paid DECIMAL(10,2) NOT NULL,
    recorded_by INT NOT NULL,
    deleted_by INT NOT NULL,
    delete_reason VARCHAR(100) DEFAULT 'Cashier Punch Errors',
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (recorded_by) REFERENCES users(user_id),
    FOREIGN KEY (deleted_by) REFERENCES users(user_id)
);

-- Seed Products matching Figma Flavors
INSERT INTO products (product_id, flavor_name, display_name, description, unit_price, badge_color) VALUES
(1, 'Original', 'Original Sweet', 'Classic Brown Sugar Glaze', 50.00, '#E5A93C'),
(2, 'Cheese', 'Cheese Delight', 'Golden Cheddar Dust', 50.00, '#F39200'),
(3, 'Sour Cream', 'Sour Cream & Chives', 'Tangy Herb Infusion', 50.00, '#2E7D32'),
(4, 'BBQ', 'Smoked BBQ', 'Savory Woodsmoke Spice', 50.00, '#6D2B1B')
ON DUPLICATE KEY UPDATE 
    display_name = VALUES(display_name),
    description = VALUES(description),
    unit_price = VALUES(unit_price),
    badge_color = VALUES(badge_color);
