import time
from collections import defaultdict
from threading import RLock
from typing import Dict, Tuple


class AppMetrics:
    """Small in-process metrics registry for local demos and portfolio use."""

    def __init__(self) -> None:
        self.started_at = time.time()
        self._request_counts: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self._request_latency_sum: Dict[Tuple[str, str, int], float] = defaultdict(float)
        self._lock = RLock()

    def record_request(self, method: str, path: str, status_code: int, elapsed_seconds: float) -> None:
        key = (method.upper(), path, int(status_code))
        with self._lock:
            self._request_counts[key] += 1
            self._request_latency_sum[key] += max(0.0, elapsed_seconds)

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP techspec_app_uptime_seconds Time since the API process started.",
                "# TYPE techspec_app_uptime_seconds gauge",
                f"techspec_app_uptime_seconds {time.time() - self.started_at:.6f}",
                "# HELP techspec_http_requests_total Total HTTP requests by method, path, and status.",
                "# TYPE techspec_http_requests_total counter",
            ]

            for (method, path, status_code), count in sorted(self._request_counts.items()):
                labels = f'method="{method}",path="{path}",status="{status_code}"'
                lines.append(f"techspec_http_requests_total{{{labels}}} {count}")

            lines.extend(
                [
                    "# HELP techspec_http_request_latency_seconds_sum Total request latency by method, path, and status.",
                    "# TYPE techspec_http_request_latency_seconds_sum counter",
                ]
            )

            for (method, path, status_code), latency_sum in sorted(self._request_latency_sum.items()):
                labels = f'method="{method}",path="{path}",status="{status_code}"'
                lines.append(f"techspec_http_request_latency_seconds_sum{{{labels}}} {latency_sum:.6f}")

        return "\n".join(lines) + "\n"


metrics = AppMetrics()
