from rag_stack.api.limits import ClientLimiter, client_key

DAY = 24 * 60 * 60


class Clock:
    def __init__(self) -> None:
        self.now = 1_000 * DAY  # midnight UTC

    def __call__(self) -> float:
        return self.now


def test_allows_requests_up_to_the_rate_then_refuses():
    limiter = ClientLimiter(
        requests_per_minute=2,
        daily_token_budget=1000,
        total_daily_token_budget=10_000,
        clock=Clock(),
    )

    assert limiter.check("a") is None
    assert limiter.check("a") is None
    assert limiter.check("a") == "Too many requests. Please wait a minute and try again."


def test_rate_window_slides():
    clock = Clock()
    limiter = ClientLimiter(
        requests_per_minute=1, daily_token_budget=1000, total_daily_token_budget=10_000, clock=clock
    )

    assert limiter.check("a") is None
    clock.now += 59
    assert limiter.check("a") is not None
    clock.now += 1
    assert limiter.check("a") is None


def test_clients_are_limited_separately():
    limiter = ClientLimiter(
        requests_per_minute=1,
        daily_token_budget=1000,
        total_daily_token_budget=10_000,
        clock=Clock(),
    )

    assert limiter.check("a") is None
    assert limiter.check("b") is None


def test_token_budget_refuses_once_spent_and_resets_next_day():
    clock = Clock()
    limiter = ClientLimiter(
        requests_per_minute=100,
        daily_token_budget=100,
        total_daily_token_budget=10_000,
        clock=clock,
    )

    limiter.charge("a", 60)
    assert limiter.check("a") is None
    limiter.charge("a", 40)
    assert limiter.check("a") == "Daily usage limit reached. Please try again tomorrow."
    assert limiter.check("b") is None

    clock.now += DAY
    assert limiter.check("a") is None


def test_total_budget_refuses_every_client_once_spent():
    limiter = ClientLimiter(
        requests_per_minute=100, daily_token_budget=100, total_daily_token_budget=150, clock=Clock()
    )

    limiter.charge("a", 90)
    limiter.charge("b", 60)
    assert (
        limiter.check("c")
        == "The assistant has reached its daily limit. Please try again tomorrow."
    )


def test_ipv6_clients_are_limited_by_their_64():
    assert client_key("2001:db8:1:2:aaaa::1") == client_key("2001:db8:1:2:bbbb::2")
    assert client_key("2001:db8:1:2::1") != client_key("2001:db8:1:3::1")
    assert client_key("::ffff:192.0.2.7") == "192.0.2.7"
    assert client_key("192.0.2.7") == "192.0.2.7"
    assert client_key("testclient") == "testclient"
