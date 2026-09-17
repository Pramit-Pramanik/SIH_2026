import sqlite3

def check():
    conn = sqlite3.connect('mandiq.db')
    cursor = conn.cursor()
    row = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='procurement_logs'").fetchone()
    print("TABLE SQL:")
    print(row[0] if row else "Table not found")

if __name__ == '__main__':
    check()
