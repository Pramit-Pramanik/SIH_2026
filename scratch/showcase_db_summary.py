import sqlite3

def summarize_db():
    conn = sqlite3.connect('mandiq.db')
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
    print("Database Tables & Counts:")
    for (tbl,) in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
        print(f"  - {tbl}: {count} records")

    print("\nShowcase Transactions in procurement_logs:")
    demo_txns = cursor.execute("SELECT transaction_id, farmer_id, current_state, crop_moisture_pct, net_weight_qt, total_payout_inr FROM procurement_logs WHERE transaction_id LIKE 'TXN-DEMO-%' ORDER BY transaction_id;").fetchall()
    for row in demo_txns:
        print(f"  {row[0]} | Farmer: {row[1]} | State: {row[2]} | Moisture: {row[3]}% | Net: {row[4]} qt | Payout: Rs {row[5]}")

    conn.close()

if __name__ == '__main__':
    summarize_db()
