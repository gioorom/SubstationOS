import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DATABASE_PATH = Path("substationos.db")


def get_column_names(
    connection: sqlite3.Connection,
) -> set[str]:
    rows = connection.execute(
        "PRAGMA table_info(documents)"
    ).fetchall()

    return {row[1] for row in rows}


def create_backup() -> Path:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = Path(
        f"substationos_backup_{timestamp}.db"
    )

    shutil.copy2(
        DATABASE_PATH,
        backup_path,
    )

    return backup_path


def detect_file_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()

    format_by_extension = {
        ".pdf": "PDF",
        ".dwg": "DWG",
        ".xlsx": "XLSX",
        ".xls": "XLSX",
        ".docx": "DOCX",
        ".doc": "DOCX",
        ".step": "MODEL_3D",
        ".stp": "MODEL_3D",
        ".iges": "MODEL_3D",
        ".igs": "MODEL_3D",
        ".stl": "MODEL_3D",
        ".obj": "MODEL_3D",
        ".fbx": "MODEL_3D",
        ".f3d": "MODEL_3D",
        ".ipt": "MODEL_3D",
        ".iam": "MODEL_3D",
    }

    return format_by_extension.get(
        suffix,
        "OTHER",
    )


def run_migration() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database non trovato: {DATABASE_PATH}"
        )

    backup_path = create_backup()

    print(
        f"Backup creato: {backup_path}"
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        columns = get_column_names(
            connection
        )

        if (
            "project" in columns
            and "project_name" not in columns
        ):
            connection.execute(
                """
                ALTER TABLE documents
                RENAME COLUMN project TO project_name
                """
            )

            print(
                "Colonna project rinominata in project_name."
            )

        columns = get_column_names(
            connection
        )

        if "project_id" not in columns:
            connection.execute(
                """
                ALTER TABLE documents
                ADD COLUMN project_id INTEGER
                REFERENCES projects(id)
                """
            )

            print(
                "Colonna project_id aggiunta."
            )

        columns = get_column_names(
            connection
        )

        if "file_format" not in columns:
            connection.execute(
                """
                ALTER TABLE documents
                ADD COLUMN file_format VARCHAR
                NOT NULL DEFAULT 'OTHER'
                """
            )

            print(
                "Colonna file_format aggiunta."
            )

        documents = connection.execute(
            """
            SELECT id, filename
            FROM documents
            """
        ).fetchall()

        for document_id, filename in documents:
            file_format = detect_file_format(
                filename
            )

            connection.execute(
                """
                UPDATE documents
                SET file_format = ?
                WHERE id = ?
                """,
                (
                    file_format,
                    document_id,
                ),
            )

        valid_categories = {
            "FUNCTIONAL_SCHEMATIC",
            "WIRING_TERMINAL",
            "GENERAL_TECHNICAL",
            "CABLE_LIST",
            "RELAY_SETTINGS",
            "COMMISSIONING_REPORT",
            "OTHER",
        }

        category_rows = connection.execute(
            """
            SELECT id, category
            FROM documents
            """
        ).fetchall()

        for document_id, category in category_rows:
            if category not in valid_categories:
                connection.execute(
                    """
                    UPDATE documents
                    SET category = 'GENERAL_TECHNICAL'
                    WHERE id = ?
                    """,
                    (document_id,),
                )

        connection.execute(
            """
            UPDATE documents
            SET revision = '00'
            WHERE revision IS NULL
               OR TRIM(revision) = ''
            """
        )

        connection.execute(
            """
            UPDATE documents
            SET project_name = 'Unknown'
            WHERE project_name IS NULL
               OR TRIM(project_name) = ''
            """
        )

        connection.commit()

        print(
            "Migrazione completata correttamente."
        )

    except Exception:
        connection.rollback()

        print(
            "Migrazione annullata. "
            "Il database originale non è stato modificato completamente."
        )

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()