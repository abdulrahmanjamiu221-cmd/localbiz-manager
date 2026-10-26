from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


NIGERIA = ZoneInfo("Africa/Lagos")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def nigeria_today():
    return datetime.now(NIGERIA).date()


def nigeria_date_range_to_utc(start_date, end_date):
    start_local = datetime.combine(start_date, time.min, tzinfo=NIGERIA)
    end_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=NIGERIA)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )
