import time

from django.conf import settings
from django.core.management.base import BaseCommand

from topology.current_state import write_snapshot
from topology.influx import write_snapshot_metrics
from topology.snapshot import build_topology_snapshot


class Command(BaseCommand):
    help = "Poll network devices, store the latest snapshot, and write historical metrics to InfluxDB."

    def handle(self, *args, **options):
        interval = max(1, int(getattr(settings, "POLL_INTERVAL_SECONDS", 5)))
        self.stdout.write(self.style.SUCCESS(f"Polling every {interval}s"))

        while True:
            started_at = time.time()
            snapshot = build_topology_snapshot()
            write_snapshot(snapshot)
            write_snapshot_metrics(snapshot)

            elapsed = time.time() - started_at
            sleep_for = max(0.0, interval - elapsed)
            time.sleep(sleep_for)
