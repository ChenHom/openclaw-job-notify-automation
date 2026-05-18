"""Infrastructure adapter for sending payloads to Claw Notify."""

from __future__ import annotations

import json
import subprocess

from job_notify.config import JobNotifyConfig, load_config


def send_firebase(payload: dict, dry_run: bool, config: JobNotifyConfig | None = None) -> None:
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    config = config or load_config()
    if not config.sender_command:
        raise RuntimeError("senderCommand is required when not running with --dry-run")
    subprocess.run(list(config.sender_command), input=json.dumps(payload, ensure_ascii=False), text=True, check=True)


class CommandNotificationSender:
    def __init__(self, config: JobNotifyConfig | None = None):
        self.config = config or load_config()

    def send(self, payload: dict) -> None:
        send_firebase(payload, dry_run=False, config=self.config)


class PrintNotificationSender:
    def send(self, payload: dict) -> None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


class RecordingNotificationSender:
    def __init__(self):
        self.payloads: list[dict] = []

    def send(self, payload: dict) -> None:
        self.payloads.append(payload)
