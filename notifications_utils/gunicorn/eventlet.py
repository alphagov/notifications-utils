from gunicorn.workers.geventlet import EventletWorker

from .greenlet import ContextRecyclingWorkerMixin, OtelAwareWorkerMixin


class ContextRecyclingEventletWorker(ContextRecyclingWorkerMixin, EventletWorker):
    pass


class OtelAwareEventletWorker(OtelAwareWorkerMixin, EventletWorker):
    pass
