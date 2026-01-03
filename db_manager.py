import sqlite3

DB_NAME = 'portfolio.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,           -- วันที่ YYYY-MM-DD
                type TEXT NOT NULL,           -- BUY, SELL, DEPOSIT, WITHDRAW, DIVIDEND
                platform TEXT NOT NULL,       -- Dime, Binance
                ticker TEXT NOT NULL,         -- AAPL, BTC-USD, THB
                quantity REAL NOT NULL,       -- จำนวนหุ้น/เหรียญ
                price REAL NOT NULL,          -- ราคาซื้อขายต่อหน่วย (Original Currency)
                fee REAL DEFAULT 0,           -- ค่าธรรมเนียม
                currency TEXT NOT NULL,       -- USD, THB
                fx_rate REAL DEFAULT 1.0,     -- อัตราแลกเปลี่ยน (บาท/USD)
                wht REAL DEFAULT 0,           -- ภาษีหัก ณ ที่จ่าย
                notes TEXT                    -- โน้ตเพิ่มเติม
            )
        ''')
        
        conn.commit()
        print(f"Database '{DB_NAME}' initial successed.")

def check_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions)")
        columns = cursor.fetchall()
        print("\n Table Columns found:")
        for col in columns:
            print(f"- {col[1]} ({col[2]})")

if __name__ == '__main__':
    init_db()
    check_db()