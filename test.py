import sqlite3

con = sqlite3.connect("scouting.db")
for row in con.execute("SELECT id, name FROM player ORDER BY name"):
    print(row)