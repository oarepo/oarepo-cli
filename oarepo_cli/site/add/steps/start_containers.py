import time

import click
import pika
import psycopg
import redis
from minio import Minio
from opensearchpy import OpenSearch

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.utils import run_cmdline
from oarepo_cli.wizard import WizardStep


class StartContainersStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I'm going to start docker containers (database, opensearch, message queue, cache etc.).
If this step fails, please fix the problem and run the wizard again.            
            """,
            **kwargs,
        )

    def after_run(self):
        run_cmdline(
            "docker",
            "compose",
            "up",
            "-d",
            "cache",
            "db",
            "mq",
            "search",
            "opensearch-dashboards",
            "pgadmin",
            "s3",
            cwd=self.site_dir,
            with_tty=False,
        )
        self._check_containers_running(False)

    def _check_containers_running(self, check_only):
        def retry(fn, tries=10, timeout=1):
            click.secho(f"Calling {fn.__name__}", fg="yellow")
            for i in range(tries):
                try:
                    fn()
                    click.secho(f"  ... alive", fg="green")
                    return
                except InterruptedError:
                    raise
                except Exception as e:
                    if check_only:
                        raise
                    self.vprint(e)
                    if i == tries - 1:
                        click.secho(f" ... failed", fg="red")
                        raise
                    click.secho(
                        f" ... not yet ready, sleeping for {int(timeout)} seconds",
                        fg="yellow",
                    )
                    time.sleep(int(timeout))
                    nt = timeout * 1.5
                    if int(nt) == int(timeout):
                        timeout = timeout + 1
                    else:
                        timeout = nt

        try:
            retry(self.check_redis)
            retry(self.check_db)
            retry(self.check_mq)
            retry(self.check_s3)
            retry(self.check_search)
            return True
        except InterruptedError:
            raise
        except:
            if check_only:
                return False
            raise

    def check_redis(self):
        host, port = self.get_invenio_configuration(
            "INVENIO_REDIS_HOST", "INVENIO_REDIS_PORT"
        )
        pool = redis.ConnectionPool(host=host, port=port, db=0)
        r = redis.Redis(connection_pool=pool)
        r.keys("blahblahblah")  # fails if there is no connection
        pool.disconnect()

    def check_db(self):
        host, port, user, password, dbname = self.get_invenio_configuration(
            "INVENIO_DATABASE_HOST",
            "INVENIO_DATABASE_PORT",
            "INVENIO_DATABASE_USER",
            "INVENIO_DATABASE_PASSWORD",
            "INVENIO_DATABASE_DBNAME",
        )

        with psycopg.connect(
            dbname=dbname, host=host, port=port, user=user, password=password
        ) as conn:
            assert conn.execute("SELECT 1").fetchone()[0] == 1

    def check_mq(self):
        host, port = self.get_invenio_configuration(
            "INVENIO_RABBIT_HOST", "INVENIO_RABBIT_PORT"
        )
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port)
        )
        channel = connection.channel()
        connection.process_data_events(2)
        assert connection.is_open
        connection.close()

    def check_s3(self):
        host, port, access_key, secret_key = self.get_invenio_configuration(
            "INVENIO_S3_HOST",
            "INVENIO_S3_PORT",
            "INVENIO_S3_ACCESS_KEY",
            "INVENIO_S3_SECRET_KEY",
        )

        client = Minio(
            f"{host}:{port}",
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        client.list_buckets()

    def check_search(self):
        (
            host,
            port,
            prefix,
            use_ssl,
            verify_certs,
            ssl_assert_hostname,
            ssl_show_warn,
        ) = self.get_invenio_configuration(
            "INVENIO_OPENSEARCH_HOST",
            "INVENIO_OPENSEARCH_PORT",
            "INVENIO_SEARCH_INDEX_PREFIX",
            "INVENIO_OPENSEARCH_USE_SSL",
            "INVENIO_OPENSEARCH_VERIFY_CERTS",
            "INVENIO_OPENSEARCH_ASSERT_HOSTNAME",
            "INVENIO_OPENSEARCH_SHOW_WARN",
        )
        try:
            ca_certs = self.get_invenio_configuration(
                "INVENIO_OPENSEARCH_CA_CERTS_PATH"
            )[0]
        except:
            ca_certs = None
        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            ssl_assert_hostname=ssl_assert_hostname,
            ssl_show_warn=ssl_show_warn,
            ca_certs=ca_certs,
        )
        info = client.info(pretty=True)
        self.vprint(info)

    def should_run(self):
        return not self._check_containers_running(True)
