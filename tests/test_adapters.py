from __future__ import annotations

from job_notify.firestore_admin import FixtureFeedbackStore
from job_notify.notify_sender import RecordingNotificationSender


def test_fixture_feedback_store_records_writes():
    store = FixtureFeedbackStore([{"uid": "u1", "status": "interested"}])

    assert store.list_feedback() == [{"uid": "u1", "status": "interested"}]

    store.write_document("profiles", "u1", {"score": 1})

    assert store.writes == [("profiles", "u1", {"score": 1})]


def test_recording_notification_sender_collects_payloads():
    sender = RecordingNotificationSender()

    sender.send({"type": "demo"})

    assert sender.payloads == [{"type": "demo"}]
