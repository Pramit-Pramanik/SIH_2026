import sqlite3

def migrate_procurement_logs():
    conn = sqlite3.connect('mandiq.db')
    cursor = conn.cursor()

    # Check existing indices
    indexes = cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='procurement_logs'").fetchall()
    print("Existing indexes:", indexes)

    # 1. Disable FK checks for schema migration
    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("BEGIN TRANSACTION;")

    # 2. Create new table with CANCELLED included in the CHECK constraint
    cursor.execute("""
    CREATE TABLE procurement_logs_new (
        transaction_id VARCHAR(36) NOT NULL, 
        farmer_id INTEGER NOT NULL, 
        mandi_id INTEGER NOT NULL, 
        slot_id INTEGER, 
        scheduled_date DATE NOT NULL, 
        crop_moisture_pct NUMERIC(4, 2), 
        gross_weight_qt NUMERIC(10, 2), 
        tare_weight_qt NUMERIC(10, 2), 
        net_weight_qt NUMERIC(10, 2), 
        total_payout_inr NUMERIC(12, 2), 
        current_state VARCHAR(30) NOT NULL, 
        token_signature VARCHAR(64) NOT NULL, 
        payout_block_hash VARCHAR(64), 
        client_mutation_id VARCHAR(36), 
        server_receive_sequence BIGINT, 
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
        PRIMARY KEY (transaction_id), 
        CONSTRAINT chk_crop_moisture_range CHECK (crop_moisture_pct >= 0 AND crop_moisture_pct <= 100), 
        CONSTRAINT chk_gross_weight_non_negative CHECK (gross_weight_qt >= 0), 
        CONSTRAINT chk_tare_weight_non_negative CHECK (tare_weight_qt >= 0), 
        CONSTRAINT chk_net_weight_non_negative CHECK (net_weight_qt >= 0), 
        CONSTRAINT chk_total_payout_non_negative CHECK (total_payout_inr >= 0), 
        CONSTRAINT chk_procurement_state_valid CHECK (current_state IN ('SLOT_BOOKED', 'GATE_ENTRY_VERIFIED', 'IN_QA_QUEUE', 'QUALITY_APPROVED', 'QUALITY_REJECTED', 'ROUTED_TO_WEIGHBRIDGE', 'WEIGHED_GROSS', 'WEIGHED_TARE', 'BILL_GENERATED', 'DBT_PAYMENT_INITIATED', 'PAYMENT_SETTLED', 'PAYMENT_FAILED', 'CANCELLED')), 
        FOREIGN KEY(farmer_id) REFERENCES farmers (farmer_id) ON DELETE RESTRICT, 
        FOREIGN KEY(mandi_id) REFERENCES mandis (mandi_id) ON DELETE RESTRICT, 
        FOREIGN KEY(slot_id) REFERENCES procurement_slots (slot_id) ON DELETE RESTRICT
    );
    """)

    # 3. Copy existing data
    cursor.execute("""
    INSERT INTO procurement_logs_new SELECT * FROM procurement_logs;
    """)

    # 4. Drop old table
    cursor.execute("DROP TABLE procurement_logs;")

    # 5. Rename new table
    cursor.execute("ALTER TABLE procurement_logs_new RENAME TO procurement_logs;")

    # 6. Recreate indices
    cursor.execute("CREATE INDEX idx_procurement_mandi_state ON procurement_logs (mandi_id, current_state);")
    cursor.execute("CREATE INDEX idx_procurement_farmer ON procurement_logs (farmer_id);")

    conn.commit()

    # 7. Check FK validity
    cursor.execute("PRAGMA foreign_keys = ON;")
    fk_errors = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    print("FK Errors:", fk_errors)

    # 8. Verify row count
    count = cursor.execute("SELECT COUNT(*) FROM procurement_logs;").fetchone()[0]
    print(f"Total rows in procurement_logs: {count}")
    conn.close()

if __name__ == '__main__':
    migrate_procurement_logs()
