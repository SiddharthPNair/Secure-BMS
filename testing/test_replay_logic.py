
class ReplayDetected(Exception):
    pass


def check_counter(counter, last_counter):
    if counter <= last_counter:
        raise ReplayDetected(
            f"Counter {counter} rejected; last accepted counter "
            f"was {last_counter}."
        )
    return counter


def test_fresh_counter():
    assert check_counter(1355, 1354) == 1355


def test_duplicate_counter():
    try:
        check_counter(1354, 1354)
    except ReplayDetected:
        return
    raise AssertionError("Duplicate counter was not rejected")


def test_stale_counter():
    try:
        check_counter(1353, 1354)
    except ReplayDetected:
        return
    raise AssertionError("Stale counter was not rejected")


if __name__ == "__main__":
    test_fresh_counter()
    test_duplicate_counter()
    test_stale_counter()
    print("PASS: Fresh counter accepted.")
    print("PASS: Duplicate counter rejected.")
    print("PASS: Stale counter rejected.")
