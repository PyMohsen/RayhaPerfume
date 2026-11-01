"""Read parcel tracking events from the Postex API."""

import logging
from datetime import datetime
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PostexTrackingService:
    BASE_URL = 'https://api.postex.ir/api/v1/tracking/events'
    TIMEOUT = (3, 8)
    CACHE_SECONDS = 300

    def __init__(self):
        self.api_key = getattr(settings, 'POSTEX_API_KEY', '').strip()
        self.courier = getattr(settings, 'POSTEX_COURIER', 'IR_POST').strip()

    def get_tracking(self, tracking_code):
        if not tracking_code or not self.api_key or not self.courier:
            return {'events': [], 'available': False}

        cache_key = f'postex_tracking:{self.courier}:{tracking_code}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        url = f'{self.BASE_URL}/{quote(self.courier, safe="")}/{quote(tracking_code, safe="")}'
        try:
            response = requests.get(
                url,
                headers={'X-API-Key': self.api_key},
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Do not log the request URL: it contains the customer's tracking code.
            logger.warning('Postex tracking request failed (%s).', type(exc).__name__)
            return {'events': [], 'available': False}

        if not isinstance(payload, (dict, list)):
            return {'events': [], 'available': False}

        # The API may wrap its event list in Data/data or return it directly.
        # Match keys case-insensitively because the service uses .NET casing.
        if isinstance(payload, dict):
            success = self._value(payload, 'IsSuccess', 'isSuccess', 'success')
            if success is False:
                logger.warning('Postex tracking API returned an unsuccessful response.')
                return {'events': [], 'available': False}

        rows = self._find_event_rows(payload)
        events = []
        dated_events = []
        for row in rows:
            event_name = self._value(
                row,
                'event_name', 'eventName', 'status_name', 'statusName',
                'description', 'message', 'type',
            )
            event_desc = self._value(
                row,
                'event_desc', 'eventDesc', 'event_description', 'eventDescription',
                'location',
            )
            raw_date = self._value(
                row,
                'event_date', 'eventDate', 'change_status_date',
                'changeStatusDate', 'date',
            )
            date = self._value(
                row,
                'friendly_event_date', 'local_event_date', 'event_date',
                'change_status_date', 'changeStatusDate', 'date',
            )
            time = self._value(row, 'event_time', 'change_status_time', 'changeStatusTime', 'time')
            if not any((event_name, event_desc)):
                continue
            event = {
                'name': str(event_name or event_desc),
                'description': str(event_desc or ''),
                'date': str(date or ''),
                'time': str(time or ''),
            }
            dated_events.append((self._event_datetime(raw_date, time), event))

        # Present a timeline from newest to oldest, with the current status first.
        if dated_events and all(event_date is not None for event_date, _ in dated_events):
            dated_events.sort(key=lambda entry: entry[0], reverse=True)
        events = [event for _, event in dated_events]

        result = {'events': events, 'available': bool(events)}
        cache.set(cache_key, result, self.CACHE_SECONDS if events else 60)
        return result

    @classmethod
    def _find_event_rows(cls, value):
        if isinstance(value, list):
            if value and all(isinstance(item, dict) for item in value):
                event_keys = (
                    'event_name', 'eventName', 'event_desc', 'eventDesc',
                    'description', 'event_date', 'eventDate', 'type',
                )
                if any(cls._value(item, *event_keys) for item in value):
                    return value
            for item in value:
                rows = cls._find_event_rows(item)
                if rows:
                    return rows
        elif isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in {'data', 'events', 'items', 'result', 'trackingevents'}:
                    rows = cls._find_event_rows(child)
                    if rows:
                        return rows
            for child in value.values():
                rows = cls._find_event_rows(child)
                if rows:
                    return rows
        return []

    @staticmethod
    def _event_datetime(event_date, event_time):
        if not event_date:
            return None
        date_text = str(event_date).strip()
        time_text = str(event_time or '00:00').strip()
        for date_format in ('%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(f'{date_text} {time_text}', f'{date_format} %H:%M')
            except ValueError:
                continue
        return None

    @staticmethod
    def _value(data, *keys):
        if not isinstance(data, dict):
            return None
        lowered = {key.lower(): value for key, value in data.items()}
        for key in keys:
            value = lowered.get(key.lower())
            if value not in (None, ''):
                return value
        return None
