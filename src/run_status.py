"""Machine-readable run status and optional webhook notification."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

import requests


@dataclass
class RunStatus:
    project: str
    date: str
    engine: str = ""
    input_file: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    source_counts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    status: str = "running"
    output_file: str = ""
    duration_seconds: float = 0.0
    _started_monotonic: float = field(default_factory=time.monotonic, repr=False)

    def record_source(self, name, count):
        self.source_counts[name] = int(count)
        if count == 0:
            self.warn(name, "source returned no items")

    def warn(self, source, message):
        self.warnings.append({"source": source, "message": str(message)})

    def error(self, source, message):
        self.errors.append({"source": source, "message": str(message)})

    def finish(self, success, output_file=""):
        if not success:
            self.status = "failed"
        elif self.warnings or self.errors:
            self.status = "success_with_warnings"
        else:
            self.status = "success"
        self.output_file = output_file or self.output_file
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.duration_seconds = round(time.monotonic() - self._started_monotonic, 3)

    def payload(self):
        data = asdict(self)
        data.pop("_started_monotonic", None)
        return data

    def write(self, output_dir):
        path = Path(output_dir) / f"run-status-{self.date}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.payload(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def notify_webhook(self):
        url = os.environ.get("RUN_STATUS_WEBHOOK_URL", "").strip()
        if not url:
            return
        try:
            response = requests.post(url, json=self.payload(), timeout=10)
            response.raise_for_status()
        except Exception as exc:
            print(f"[监控] webhook 回传失败: {exc}", file=sys.stderr)
