from extraction.extract_players import extract_players
from config.snowflake_config import get_snowflake_connection


def load_players(players=None):

    # Extract players only if the caller did not already provide them.
    if players is None:
        players = extract_players()

    if not players:
        print("No player records found.")
        return 0

    connection = get_snowflake_connection()

    try:
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO NBA_DATA_WAREHOUSE.RAW.NBA_PLAYERS_API (
                PLAYER_ID,
                FIRST_NAME,
                LAST_NAME,
                POSITION,
                TEAM_ID,
                TEAM_NAME,
                JERSEY_NUMBER,
                HEIGHT,
                WEIGHT,
                COLLEGE,
                COUNTRY,
                DRAFT_YEAR,
                DRAFT_ROUND,
                DRAFT_NUMBER
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """

        records = []

        for player in players:
            team = player.get("team") or {}

            record = (
                player.get("id"),
                player.get("first_name"),
                player.get("last_name"),
                player.get("position"),
                team.get("id"),
                team.get("full_name"),
                player.get("jersey_number"),
                player.get("height"),
                player.get("weight"),
                player.get("college"),
                player.get("country"),
                player.get("draft_year"),
                player.get("draft_round"),
                player.get("draft_number"),
            )

            records.append(record)

        cursor.executemany(insert_query, records)
        connection.commit()

        print(f"SUCCESS: {len(records)} players loaded into Snowflake RAW.")
        cursor.close()
        return len(records)

    finally:
        connection.close()


if __name__ == "__main__":
    load_players()