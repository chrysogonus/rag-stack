import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, date, datetime


class ClientLimiter:
    """Per-client request rate (sliding minute) and daily token budget.

    ponytail: in-process memory, so limits are per replica and reset on restart; move to a
    shared store (Redis or Postgres) before running more than one replica.
    """

    def __init__(
        self,
        requests_per_minute: int,
        daily_token_budget: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._requests_per_minute = requests_per_minute
        self._daily_token_budget = daily_token_budget
        self._clock = clock
        self._day: date | None = None
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)
        self._tokens: defaultdict[str, int] = defaultdict(int)

    def _roll_day(self) -> None:
        # Starting each UTC day empty resets budgets and bounds memory to one day's clients.
        today = datetime.fromtimestamp(self._clock(), UTC).date()
        if today != self._day:
            self._day = today
            self._requests.clear()
            self._tokens.clear()

    def check(self, client: str) -> str | None:
        """Record a request. Returns why it's refused, or None if it may proceed."""
        self._roll_day()
        if self._tokens[client] >= self._daily_token_budget:
            return "Daily usage limit reached. Please try again tomorrow."
        now = self._clock()
        requests = self._requests[client]
        while requests and requests[0] <= now - 60:
            requests.popleft()
        if len(requests) >= self._requests_per_minute:
            return "Too many requests. Please wait a minute and try again."
        requests.append(now)
        return None

    def charge(self, client: str, tokens: int) -> None:
        self._roll_day()
        self._tokens[client] += tokens
