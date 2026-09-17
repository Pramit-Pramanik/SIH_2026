import sqlite3

def update_farmer():
    conn = sqlite3.connect('mandiq.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE farmers SET mobile_number='9814255201', name='Balwinder Singh' WHERE farmer_id=2")
    conn.commit()
    row = cursor.execute("SELECT farmer_id, name, mobile_number FROM farmers WHERE farmer_id=2").fetchone()
    print("Updated farmer:", row)
    conn.close()

if __name__ == '__main__':
    update_farmer()
