import sqlite3
c = sqlite3.connect('file:backend/mellowtech.db?mode=ro', uri=True)
for (t,) in c.execute("select name from sqlite_master where type='table'").fetchall():
    n = c.execute(f'select count(*) from "{t}"').fetchone()[0]
    cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
    print(t, n, cols)
