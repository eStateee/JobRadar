#!/usr/bin/env python3
import sqlite3
import datetime
import os
import shutil

def backup_db():
    source_db = "database.db"
    if not os.path.exists(source_db):
        print(f"Source DB {source_db} not found.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_{timestamp}.db"
    
    try:
        # Use sqlite3 backup api for safe copy even if in use
        con = sqlite3.connect(source_db)
        bck = sqlite3.connect(backup_file)
        with bck:
            con.backup(bck)
        bck.close()
        con.close()
        
        # Also copy it to a static name "backup.db" as requested in spec
        shutil.copy2(backup_file, "backup.db")
        print(f"Successfully backed up {source_db} to {backup_file} and backup.db")
    except Exception as e:
        print(f"Error during backup: {e}")

if __name__ == "__main__":
    backup_db()
