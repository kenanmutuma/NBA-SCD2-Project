from pathlib import Path

from config.snowflake_config import get_snowflake_connection
from extraction.extract_players import extract_players
from loading.load_players_to_snowflake import load_players


PROJECT_ROOT = Path(__file__).resolve().parent
SQL_FILES = {
    "staging": PROJECT_ROOT / "sql" / "refresh_staging.sql",
    "scd2": PROJECT_ROOT / "sql" / "scd2_transform_players.sql",
}


def execute_sql_file(connection, name):
    sql_text = SQL_FILES[name].read_text(encoding="utf-8")

    for statement in sql_text.split(";"):
        statement = statement.strip()
        if not statement:
            continue

        cursor = connection.cursor()
        try:
            cursor.execute(statement)
            try:
                rows = cursor.fetchall()
                if rows:
                    print(f"{name.upper()}:", rows)
            except Exception:
                pass
        finally:
            cursor.close()


def run_pipeline(max_players=None):
    print("1/4 Extracting players from the API...")
    players = extract_players(per_page=100, max_players=max_players)

    print("2/4 Loading players into RAW...")
    loaded_count = load_players(players)

    connection = get_snowflake_connection()

    try:
        connection.cursor().execute("BEGIN")

        print("3/4 Refreshing STAGING...")
        execute_sql_file(connection, "staging")

        print("4/4 Running the SCD2 transformation...")
        execute_sql_file(connection, "scd2")

        connection.commit()

        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) AS TOTAL_VERSION_ROWS,
                SUM(IFF(IS_CURRENT, 1, 0)) AS CURRENT_ROWS,
                COUNT(DISTINCT PLAYER_ID) AS DISTINCT_PLAYERS
            FROM NBA_DATA_WAREHOUSE.DW.DIM_NBA_PLAYERS
        """)
        validation = cursor.fetchone()
        cursor.close()

        print("PIPELINE SUCCESS")
        print("RAW records loaded:", loaded_count)
        print("Dimension total/current/distinct:", validation)

    except Exception:
        connection.rollback()
        print("PIPELINE FAILED: transaction rolled back.")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    run_pipeline()
