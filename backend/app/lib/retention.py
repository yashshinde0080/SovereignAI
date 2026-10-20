"""Retention period map — seconds, from DataRetentionPeriod values.

Session auto-delete and any other retention consumer reads this instead of
re-implementing the day math.
"""
from app.settings.schemas import DataRetentionPeriod

_D = 24 * 60 * 60
RETENTION_SECONDS = {
    DataRetentionPeriod.ONE_DAY.value: _D,
    DataRetentionPeriod.SEVEN_DAYS.value: 7 * _D,
    DataRetentionPeriod.THIRTY_DAYS.value: 30 * _D,
    DataRetentionPeriod.NINETY_DAYS.value: 90 * _D,
}
