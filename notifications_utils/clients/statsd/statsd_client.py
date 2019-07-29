from statsd import StatsClient
from threading import Timer


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
        self.host = app.config.get('STATSD_HOST')
        self.port = app.config.get('STATSD_PORT')
        self.prefix = app.config.get('STATSD_PREFIX')

        if self.active:
            self._refresh_client()

    def _refresh_client(self):
        self.statsd_client = StatsClient(self.host, self.port, self.prefix)
        Timer(1, self._refresh_client).start()

    def format_stat_name(self, stat):
        return self.namespace + stat

    def incr(self, stat, count=1, rate=1):
        if self.active:
            self.statsd_client.incr(self.format_stat_name(stat), count, rate)

    def gauge(self, stat, count):
        if self.active:
            self.statsd_client.gauge(self.format_stat_name(stat), count)

    def timing(self, stat, delta, rate=1):
        if self.active:
            self.statsd_client.timing(self.format_stat_name(stat), delta, rate)

    def timing_with_dates(self, stat, start, end, rate=1):
        if self.active:
            delta = (start - end).total_seconds()
            self.statsd_client.timing(self.format_stat_name(stat), delta, rate)
