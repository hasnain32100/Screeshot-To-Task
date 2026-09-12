import sqlite3
from sqlalchemy import inspect
from database import engine, Base
from models.task import Task


NEW_COLUMNS = {
    "person": "VARCHAR(200)",
    "amount": "VARCHAR(50)",
    "currency": "VARCHAR(20)",
    "phone": "VARCHAR(50)",
    "email": "VARCHAR(200)",
    "url": "VARCHAR(500)",
    "organization": "VARCHAR(200)",
    "summary": "TEXT",
    "raw_extraction": "JSON",
}


def run_migration():

    inspector = inspect(engine)

    if "tasks" not in inspector.get_table_names():
        print("No existing 'tasks' table found — creating fresh tables instead.")
        Base.metadata.create_all(bind=engine)
        print("Done.")
        return

    existing_columns = {
        col["name"] for col in inspector.get_columns("tasks")
    }

    with engine.connect() as connection:

        for column_name, column_type in NEW_COLUMNS.items():

            if column_name in existing_columns:
                print(f"Skipping '{column_name}' — already exists.")
                continue

            print(f"Adding column '{column_name}' ({column_type})...")

            connection.exec_driver_sql(
                f"ALTER TABLE tasks ADD COLUMN {column_name} {column_type}"
            )

        connection.commit()

    print("Migration complete. Existing data was preserved.")


if __name__ == "__main__":
    run_migration()