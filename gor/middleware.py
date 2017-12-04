# coding: utf-8

import contextlib
import errno
import logging
import sys

from prometheus_client import start_http_server, Histogram
from tornado import gen, ioloop, queues
from tornado.stack_context import StackContext

from .base import Gor


@contextlib.contextmanager
def die_on_error():
    try:
        yield
    except Exception:
        logging.error("exception in asynchronous operation", exc_info=True)
        sys.exit(1)


class TornadoGor(Gor):

    def __init__(self, *args, **kwargs):
        super(TornadoGor, self).__init__(*args, **kwargs)
        self.q = queues.Queue()
        self.concurrency = kwargs.get('concurrency', 2)

        # Initialize Prometheus exporter as disabled
        self.prometheus_counter = None
        self.enable_prom_exporter = False
        self.prometheus_port = 8000

    @gen.coroutine
    def _process(self):
        line = yield self.q.get()
        try:
            msg = self.parse_message(line)
            if msg:
                self.emit(msg)
        finally:
            self.q.task_done()

    @gen.coroutine
    def _worker(self):
        while True:
            yield self._process()

    @gen.coroutine
    def _run(self):
        for _ in range(self.concurrency):
            self._worker()

        while True:
            try:
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                ioloop.IOLoop.instance().stop()
                break
            self.q.put(line)
            yield

    def run(self):
        with StackContext(die_on_error):
            if self.enable_prom_exporter:
                start_http_server(8000)
            self.io_loop = ioloop.IOLoop.current()
            self.io_loop.run_sync(self._run)
            sys.exit(errno.EINTR)

    def setup_prometheus(self, enable=True, port=8000):
        self.enable_prom_exporter = enable
        self.prometheus_port = port
        self.prometheus_counter = Counters()
        if self.enable_prom_exporter:
            self.on('request', self.on_request_stats, counter=self.prometheus_counter)

    def on_request_stats(self, proxy, msg , **kwargs):
        counter = kwargs['counter']
        self.on('replay', self.on_replay_stats, req=msg, counter=counter)

    def on_replay_stats(self, proxy, msg,  **kwargs):
        counter = kwargs['counter']
        replay_status = self.http_status(msg.http)
        req_http_path = self.http_path(kwargs['req'].http)
        req_http_base_path = req_http_path[:req_http_path.find('/', 1)]
        labels = {'http_status': replay_status,
                  'http_method': self.http_method(kwargs['req'].http),
                  'http_path': req_http_base_path
                  }
        counter.add_response(float(msg.meta[3]) / 1000000, labels)


class Counters:
    def __init__(self):
        self.responses = {}

    def add_response(self, latency, labels=None):
        key = ""
        for label_name in labels:
            key += "_" + label_name

        # If the counter is already there observe the sample
        if key in self.responses:
            self.responses[key].labels(**labels).observe(latency)
        # Otherwise create the counter
        else:
            self.responses[key] = Histogram('responses_latency', 'Response Time of Replayed Responses', labels.keys())

