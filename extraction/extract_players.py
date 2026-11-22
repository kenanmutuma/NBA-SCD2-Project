import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("BALLDONTLIE_API_KEY")
API_URL = "https://api.balldontlie.io/v1/players"


def request_page(headers, params, max_retries=5):
    """Request one API page, retrying transient 429 throttling responses."""
    for attempt in range(max_retries):
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)

        if response.status_code != 429:
            response.raise_for_status()
            return response

        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                wait_seconds = int(retry_after)
            except ValueError:
                wait_seconds = 2 ** attempt
        else:
            wait_seconds = 2 ** attempt

        print(
            f"API rate limit reached. Waiting {wait_seconds} seconds "
            f"(retry {attempt + 1}/{max_retries})..."
        )
        time.sleep(wait_seconds)

    response = requests.get(API_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response


def extract_players(per_page=100, max_players=None):
    """Extract players from every API page using the API cursor."""
    if not API_KEY:
        raise ValueError("BALLDONTLIE_API_KEY is missing from .env")

    headers = {"Authorization": API_KEY}
    players = []
    cursor = None

    while True:
        params = {"per_page": per_page}
        if cursor is not None:
            params["cursor"] = cursor

        response = request_page(headers, params)
        result = response.json()

        page_players = result.get("data", [])
        players.extend(page_players)

        if max_players is not None and len(players) >= max_players:
            players = players[:max_players]
            break

        next_cursor = (result.get("meta") or {}).get("next_cursor")
        if next_cursor is None:
            break

        cursor = next_cursor
        time.sleep(1)

    print(f"Successfully extracted {len(players)} NBA players.")
    return players


if __name__ == "__main__":
    extracted_players = extract_players(per_page=100)

    for player in extracted_players[:10]:
        team = player.get("team") or {}
        print({
            "player_id": player.get("id"),
            "first_name": player.get("first_name"),
            "last_name": player.get("last_name"),
            "position": player.get("position"),
            "team_name": team.get("full_name"),
            "college": player.get("college"),
            "country": player.get("country"),
        })


from extraction.extract_players import extract_players
from config.snowflake_config import get_snowflake_connection


def load_players():

    # Extract players from BALLDONTLIE
    players = extract_players()

    if not players:
        print("No player records found.")
        return

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
                player.get("draft_number")
            )

            records.append(record)

        cursor.executemany(insert_query, records)
        connection.commit()

        print(f"SUCCESS: {len(records)} players loaded into Snowflake RAW.")

        cursor.close()

    finally:
        connection.close()


if __name__ == "__main__":
    load_players()