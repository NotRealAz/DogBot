import sqlite3
import json

# Use UTF-8 encoding to avoid UnicodeDecodeError
with open('config/achievements.json', encoding='utf-8') as f:
    jn = json.load(f)

db = sqlite3.connect('databases/ach.db')

cursor = db.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS achievements
                  (GID INTEGER, UID INTEGER, ID TEXT, 
                  PRIMARY KEY(GID, UID, ID))''')

db.commit()

class Achievement:
    @classmethod
    def Claim(cls, GID: int, UID: int, ID: str):
        if GID == 0:
            raise ValueError("Guild ID cannot be zero")
        if UID == 0:
            raise ValueError("User ID cannot be zero")
        if ID == 0:
            raise ValueError("ID cannot be zero")
        
        cursor.execute("SELECT * FROM achievements WHERE GID = ? AND UID = ? AND ID = ?", (GID, UID, ID))
        if cursor.fetchone():
            raise ValueError("Achievement already claimed")

        cursor.execute("INSERT INTO achievements VALUES (?, ?, ?)", (GID, UID, ID))
        db.commit()
        
    @classmethod
    def Retrieve(cls, GID: int, UID: int):
        if GID == 0:
            raise ValueError("Guild ID cannot be zero")
        if UID == 0:
            raise ValueError("User ID cannot be zero")

        cursor.execute("SELECT * FROM achievements WHERE GID = ? AND UID = ?", (GID, UID))
        achievements = cursor.fetchall()

        result = []
        for achievement in achievements:
            achievement_id = achievement[2]
            # Search for the achievement in the list 'jn'
            found = next((item for item in jn if item.get("ID") == achievement_id), None)
            if found is None:
                raise LookupError(f"Achievement ID {achievement_id} does not exist")
            result.append(found)

        return result



