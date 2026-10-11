from gunicorn.workers.ggevent import GeventWorker

from .greenlet import ContextRecyclingWorkerMixin, OtelAwareWorkerMixin


class ContextRecyclingGeventWorker(ContextRecyclingWorkerMixin, GeventWorker):
    pass


class OtelAwareGeventWorker(OtelAwareWorkerMixin, GeventWorker):
    pass
