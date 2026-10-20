"""Tiny in-process metrics store with Prometheus text exposition (no client lib needed)."""

import threading
from dataclasses import dataclass, field


@dataclass
class Metrics:
    requests_total: int = 0
    errors_total: int = 0
    gate_total: dict = field(default_factory=dict)  # verdict -> count
    tokens_total: int = 0
    last_tokens_per_s: float = 0.0
    last_latency_s: float = 0.0
    cold_start_s: float | None = None  # process start -> first answered question
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_answer(self, tokens: int, gen_seconds: float, total_seconds: float, since_start: float):
        with self._lock:
            self.requests_total += 1
            self.tokens_total += tokens
            if gen_seconds > 0 and tokens > 0:
                self.last_tokens_per_s = tokens / gen_seconds
            self.last_latency_s = total_seconds
            if self.cold_start_s is None:
                self.cold_start_s = since_start

    def record_gate(self, verdict: str):
        with self._lock:
            self.gate_total[verdict] = self.gate_total.get(verdict, 0) + 1

    def record_error(self):
        with self._lock:
            self.errors_total += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "requests_total": self.requests_total,
                "errors_total": self.errors_total,
                "tokens_total": self.tokens_total,
                "tokens_per_s": round(self.last_tokens_per_s, 2),
                "last_latency_s": round(self.last_latency_s, 3),
                "cold_start_s": None if self.cold_start_s is None else round(self.cold_start_s, 2),
            }

    def prometheus(self) -> str:
        s = self.snapshot()
        lines = [
            ("airgap_requests_total", "counter", s["requests_total"]),
            ("airgap_errors_total", "counter", s["errors_total"]),
            ("airgap_generated_tokens_total", "counter", s["tokens_total"]),
            ("airgap_tokens_per_second", "gauge", s["tokens_per_s"]),
            ("airgap_last_request_latency_seconds", "gauge", s["last_latency_s"]),
        ]
        if s["cold_start_s"] is not None:
            lines.append(("airgap_cold_start_seconds", "gauge", s["cold_start_s"]))
        out = []
        for name, kind, val in lines:
            out += [f"# TYPE {name} {kind}", f"{name} {val}"]
        out.append("# TYPE airgap_gate_verdicts_total counter")
        for verdict, n in sorted(self.gate_total.items()):
            out.append(f'airgap_gate_verdicts_total{{verdict="{verdict}"}} {n}')
        return "\n".join(out) + "\n"


METRICS = Metrics()
