"""
app/workers/celery_app.py
──────────────────────────
Celery app + all background task definitions.

Tasks:
  send_otp_email_task     — OTP verification email
  send_reset_email_task   — password reset email
  send_email_task         — user-triggered email via automation
  run_timer_task          — countdown timer → queues play_sound to Redis + email
  run_alarm_task          — scheduled alarm  → queues play_sound to Redis + email
  generate_tts_task       — TTS audio generation
  nightly_cleanup_task    — Celery Beat: clean old conversations daily
"""
from __future__ import annotations
import json
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from celery import Celery
from celery.schedules import crontab
from celery.utils.log import get_task_logger

from app.core.config import settings

logger = get_task_logger(__name__)

celery_app = Celery(
    "lexiact",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "nightly-cleanup": {
            "task": "tasks.nightly_cleanup",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_smtp(to_email: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{settings.your_name} <{settings.from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.from_email, settings.from_password)
        server.sendmail(settings.from_email, to_email, msg.as_string())


def _get_user_email_sync(user_id: int) -> str | None:
    """Fetch user email from DB synchronously for use inside Celery tasks."""
    import asyncio
    from sqlalchemy import select
    from app.db.database import AsyncSessionLocal
    from app.models.user import User

    async def _fetch():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            return user.email if user else None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch())
    except Exception as e:
        logger.warning(f"Could not fetch user email: {e}")
        return None
    finally:
        loop.close()


def _queue_play_sound(sound_type: str, message: str) -> None:
    """
    Queue a play_sound command to Redis for the Local Agent to pick up.
    The Local Agent running on the user's machine plays the sound locally.

    sound_type: "timer_done" | "alarm"
    message:    text to display in the local agent console
    """
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.redis_url)
        r.lpush("local_agent:commands", json.dumps({
            "type": "play_sound",
            "sound_type": sound_type,
            "message": message,
        }))
        logger.info(f"play_sound command queued: {sound_type}")
    except Exception as e:
        logger.warning(f"Could not queue play_sound command: {e}")


# ── OTP email ─────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, name="tasks.send_otp_email")
def send_otp_email_task(self, to_email: str, otp: str, full_name: str) -> dict:
    try:
        subject = f"Your {settings.app_name} verification code: {otp}"
        body = (
            f"Hi {full_name or 'there'},\n\n"
            f"Your verification code is: {otp}\n\n"
            f"This code expires in {settings.otp_expire_seconds // 60} minutes.\n\n"
            f"If you did not register, please ignore this email.\n\n"
            f"— {settings.app_name} Team"
        )
        _send_smtp(to_email, subject, body)
        logger.info(f"OTP email sent to {to_email}")
        return {"status": "sent", "to": to_email}
    except smtplib.SMTPException as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error(f"OTP email failed: {exc}")
        return {"status": "failed", "error": str(exc)}


# ── Password reset email ──────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, name="tasks.send_reset_email")
def send_reset_email_task(self, to_email: str, reset_token: str, full_name: str) -> dict:
    try:
        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
        subject = f"Reset your {settings.app_name} password"
        body = (
            f"Hi {full_name or 'there'},\n\n"
            f"Click the link below to reset your password:\n{reset_url}\n\n"
            f"This link expires in {settings.password_reset_expire_seconds // 60} minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— {settings.app_name} Team"
        )
        _send_smtp(to_email, subject, body)
        return {"status": "sent"}
    except smtplib.SMTPException as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


# ── General email (user automation) ──────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, name="tasks.send_email")
def send_email_task(self, to_email: str, subject: str, body: str) -> dict:
    try:
        _send_smtp(to_email, subject, body)
        logger.info(f"Email sent to {to_email}")
        return {"status": "sent", "to": to_email}
    except smtplib.SMTPException as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


# ── Timer task ────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.run_timer")
def run_timer_task(seconds: int, user_id: int, label: str = "Timer") -> dict:
    """
    Countdown timer running in Celery worker (Docker).
    When done:
      1. Queues play_sound command → Local Agent plays alarm sound on user's machine
      2. Sends email notification as fallback
    """
    time.sleep(seconds)
    mins, secs = divmod(seconds, 60)
    duration = f"{mins}m {secs}s" if mins else f"{secs}s"
    logger.info(f"Timer done: {label} ({duration}) for user_id={user_id}")

    # 1. Queue sound for local agent
    _queue_play_sound(
        sound_type="timer_done",
        message=f"⏲️ Timer done! {label} — {duration}",
    )

    # 2. Send email notification as fallback
    user_email = _get_user_email_sync(user_id)
    if user_email and settings.from_email:
        try:
            _send_smtp(
                user_email,
                f"⏲️ {settings.app_name}: Your {duration} timer is done!",
                f"Your {label} timer ({duration}) has finished!\n\n— {settings.app_name}",
            )
            logger.info(f"Timer notification email sent to {user_email}")
        except Exception as e:
            logger.warning(f"Timer email failed: {e}")

    return {"status": "done", "user_id": user_id, "label": label, "duration": duration}


# ── Alarm task ────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.run_alarm")
def run_alarm_task(sleep_seconds: float, user_id: int, alarm_time_str: str) -> dict:
    """
    Scheduled alarm running in Celery worker (Docker).
    When it fires:
      1. Queues play_sound command → Local Agent plays alarm sound on user's machine
      2. Sends email notification as fallback
    """
    time.sleep(max(0, sleep_seconds))
    logger.info(f"Alarm fired for user_id={user_id} at {alarm_time_str}")

    # 1. Queue sound for local agent
    _queue_play_sound(
        sound_type="alarm",
        message=f"⏰ Alarm! It is {alarm_time_str}",
    )

    # 2. Send email notification as fallback
    user_email = _get_user_email_sync(user_id)
    if user_email and settings.from_email:
        try:
            _send_smtp(
                user_email,
                f"⏰ {settings.app_name}: Alarm — {alarm_time_str}",
                f"Your alarm is going off!\n\nAlarm time: {alarm_time_str}\n\n— {settings.app_name}",
            )
            logger.info(f"Alarm notification email sent to {user_email}")
        except Exception as e:
            logger.warning(f"Alarm email failed: {e}")

    return {"status": "alarm_fired", "user_id": user_id, "alarm_time": alarm_time_str}


# ── TTS generation ────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.generate_tts")
def generate_tts_task(text: str, user_id: int) -> dict:
    try:
        import uuid
        from gtts import gTTS
        filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
        tts = gTTS(text=text[:500], lang="en")
        tts.save(f"/tmp/{filename}")
        return {"status": "done", "filename": filename}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ── Nightly cleanup (Celery Beat) ─────────────────────────────────────────────

@celery_app.task(name="tasks.nightly_cleanup")
def nightly_cleanup_task() -> dict:
    """Runs at 2 AM UTC daily via Celery Beat. Deletes conversations older than 90 days."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete
    from app.db.database import AsyncSessionLocal
    from app.models.conversation import Conversation

    async def _cleanup():
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(Conversation).where(Conversation.created_at < cutoff)
            )
            await db.commit()
            return result.rowcount

    loop = asyncio.new_event_loop()
    try:
        deleted = loop.run_until_complete(_cleanup())
    finally:
        loop.close()

    logger.info(f"Nightly cleanup: deleted {deleted} old conversation records")
    return {"status": "done", "deleted_conversations": deleted}
