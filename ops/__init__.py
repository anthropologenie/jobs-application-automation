"""
Operations seam (Phase B: no scheduler).

Recurring runs, schedulers (cron/systemd/n8n) and network discovery loops are
explicitly deferred (Phase B §35-§36). The run lock (store.lock.RunLock) and
the migration runner (store.migrate) are the only operational pieces built so
far. Any future orchestrator must take the run lock and must never submit an
application.
"""
