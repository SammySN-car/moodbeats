"""
Database Migration Script
Adds missing columns to the songs table for the Kaggle knowledge base integration.
Run once before importing songs.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / 'moodbeats.db'


def migrate():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute('PRAGMA table_info(songs)')
    existing_cols = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns: {existing_cols}")

    # New columns needed for Kaggle dataset
    new_columns = [
        ("genre", "VARCHAR(100) DEFAULT 'unknown'"),
        ("acousticness", "FLOAT DEFAULT 0.0"),
        ("instrumentalness", "FLOAT DEFAULT 0.0"),
        ("speechiness", "FLOAT DEFAULT 0.0"),
        ("liveness", "FLOAT DEFAULT 0.0"),
    ]

    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
            added += 1
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()

    if added > 0:
        print(f"\nMigration complete: {added} columns added")
    else:
        print("\nNo migration needed: all columns already exist")


if __name__ == '__main__':
    migrate()
