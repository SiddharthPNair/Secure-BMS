
import psycopg
from psycopg.rows import dict_row


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "secure_bms_test",
    "user": "postgres",
    # Set PGPASSWORD in your terminal before running this test.
    "password": None,
    "row_factory": dict_row,
    "connect_timeout": 5,
}


class ReplayDetected(Exception):
    pass


def check_and_update_replay_state(connection, nonce):
    if not isinstance(nonce, bytes) or len(nonce) != 12:
        raise ValueError("Invalid nonce")

    session_id = nonce[:8]
    counter = int.from_bytes(nonce[8:], "big")

    state = connection.execute(
        """
        SELECT active_session_id, last_counter
        FROM secure_bms_replay_state
        WHERE singleton_id = 1
        FOR UPDATE
        """
    ).fetchone()

    if state is None:
        raise RuntimeError("Replay state row is missing")

    active_session = state["active_session_id"]
    if active_session is not None:
        active_session = bytes(active_session)

    if active_session == session_id:
        if counter <= state["last_counter"]:
            raise ReplayDetected("Duplicate or stale counter")

        connection.execute(
            """
            UPDATE secure_bms_replay_state
            SET last_counter = %s
            WHERE singleton_id = 1
            """,
            (counter,),
        )
    else:
        previous = connection.execute(
            """
            SELECT 1
            FROM secure_bms_replay_sessions
            WHERE session_id = %s
            """,
            (session_id,),
        ).fetchone()

        if previous:
            raise ReplayDetected("Previously seen inactive session")

        connection.execute(
            """
            INSERT INTO secure_bms_replay_sessions (session_id)
            VALUES (%s)
            """,
            (session_id,),
        )

        connection.execute(
            """
            UPDATE secure_bms_replay_state
            SET active_session_id = %s, last_counter = %s
            WHERE singleton_id = 1
            """,
            (session_id, counter),
        )


def make_nonce(session_id, counter):
    return session_id + counter.to_bytes(4, "big")


def expect_replay(connection, nonce):
    try:
        check_and_update_replay_state(connection, nonce)
    except ReplayDetected:
        return
    raise AssertionError("Replay was not rejected")


def main():
    with psycopg.connect(**DB_CONFIG) as connection:
        # Start from a clean state in the isolated test database only.
        connection.execute("DELETE FROM secure_bms_replay_state")
        connection.execute("DELETE FROM secure_bms_replay_sessions")
        connection.execute(
            """
            INSERT INTO secure_bms_replay_state
                (singleton_id, active_session_id, last_counter)
            VALUES (1, NULL, -1)
            """
        )

        session_a = b"SESSIONA"
        session_b = b"SESSIONB"

        check_and_update_replay_state(
            connection, make_nonce(session_a, 10)
        )
        print("PASS: First message from a new session accepted.")

        check_and_update_replay_state(
            connection, make_nonce(session_a, 11)
        )
        print("PASS: Higher counter accepted.")

        expect_replay(connection, make_nonce(session_a, 11))
        print("PASS: Duplicate counter rejected.")

        expect_replay(connection, make_nonce(session_a, 9))
        print("PASS: Stale counter rejected.")

        check_and_update_replay_state(
            connection, make_nonce(session_b, 1)
        )
        print("PASS: New session accepted.")

        expect_replay(connection, make_nonce(session_a, 12))
        print("PASS: Previously seen inactive session rejected.")

        # Roll back every test change.
        connection.rollback()

    print("PASS: Test transaction rolled back.")


if __name__ == "__main__":
    main()
