import random
import time
from socket import AF_INET, SOCK_DGRAM, gethostbyname, socket

import cachetools.func
from flask import current_app
from statsd.client.base import StatsClientBase


def time_monotonic_with_jitter():
    jitter = random.uniform(-3, 3)
    return time.monotonic() + jitter


class NotifyStatsClient(StatsClientBase):
    def __init__(self, host, port, prefix):
        self._host = host
        self._port = port
        self._prefix = prefix
        self._sock = socket(AF_INET, SOCK_DGRAM)

    def _resolve(self, addr):
        return gethostbyname(addr)

    @cachetools.func.ttl_cache(maxsize=2, ttl=15, timer=time_monotonic_with_jitter)
    def _cached_host(self):
        try:
            return self._resolve(self._host)
        except Exception as e:
            # if we get an error store None in the cache so that we don't keep trying to retrieve the DNS
            # if paas's dns server is having issues
            current_app.logger.warning('Error resolving statsd dns: {}'.format(str(e)))
            return None

    def _send(self, data):
        try:
            host = self._cached_host()

            # if we can't resolve DNS then host is none - just skip sending stats for next 15 secs
            if host:
                self._sock.sendto(data.encode('ascii'), (host, self._port))
        except Exception as e:
            current_app.logger.warning('Error sending statsd metric: {}'.format(str(e)))
            pass


class StatsdClient():
    def __init__(self):
        self.statsd_client = None

    def init_app(self, app, *args, **kwargs):
        app.statsd_client = self
        self.active = app.config.get('STATSD_ENABLED')
        self.namespace = "{}.notifications.{}.".format(
            app.config.get('NOTIFY_ENVIRONMENT'),
            app.config.get('NOTIFY_APP_NAME')
        )

        if self.active:
            self.statsd_client = NotifyStatsClient(
                app.config.get('STATSD_HOST'),
                app.config.get('STATSD_PORT'),
                prefix=app.config.get('STATSD_PREFIX')
            )

    def format_stat_name(self, stat):
        return self.namespace + stat

    def incr(self, stat, count=1, rate=1):
        if self.active:
            self.statsd_client.incr(self.format_stat_name(stat), count, rate)

    def gauge(self, stat, count):
        if self.active:
            self.statsd_client.gauge(self.format_stat_name(stat), count)

    def timing(self, stat, delta, rate=1):
        # delta should be in seconds
        if self.active:
            self.statsd_client.timing(self.format_stat_name(stat), delta * 1000, rate)

    def timing_with_dates(self, stat, start, end, rate=1):
        if self.active:
            delta = (start - end).total_seconds()
            self.statsd_client.timing(self.format_stat_name(stat), delta * 1000, rate)
