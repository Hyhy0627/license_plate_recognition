"""PostgreSQL job leases whose owner can run on a different host."""

from functools import lru_cache
from hashlib import blake2b

from filelock import Timeout
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


def job_lock_key(job_id):
    return int.from_bytes(blake2b(job_id.encode(), digest_size=8, person=b"alpr-video").digest(), "big", signed=True)


@lru_cache(maxsize=1)
def _lease_engine(url):
    # A dedicated physical connection stays open for each live job. This
    # keeps long job lifetimes from occupying regular request-pool slots.
    return create_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")


class PostgresJobLease:
    def __init__(self, url, job_id):
        self.url = url
        self.job_id = job_id
        self.connection = None

    def acquire(self):
        connection = _lease_engine(self.url).connect()
        try:
            locked = connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": job_lock_key(self.job_id)},
            )
            if not locked:
                raise Timeout(self.job_id)
        except BaseException:
            connection.close()
            raise
        self.connection = connection

    def release(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
