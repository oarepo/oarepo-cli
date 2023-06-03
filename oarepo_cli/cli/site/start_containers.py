import time

import click
import pika
import psycopg
from dotenv import dotenv_values
from minio import Minio
from opensearchpy import OpenSearch

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep

from ...utils import run_cmdline
import redis


class StartContainersStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I'm going to start docker containers (database, opensearch, message queue, cache etc.).
If this step fails, please fix the problem and run the wizard again.            
            """,
            **kwargs
        )

    def after_run(self):
        run_cmdline("docker", "compose", "up", "-d", cwd=self.site_dir)
        self._check_containers_running(False)

    def _check_containers_running(self, check_only):
        def retry(fn, tries=10, timeout=1):
            click.secho(f"Calling {fn}", fg="yellow")
            for i in range(tries):
                try:
                    return fn()
                except InterruptedError:
                    raise
                except Exception as e:
                    if i == tries-1:
                        click.secho(f" ... failed", fg="red")
                        raise
                    click.secho(f" ... not yet ready, sleeping for {int(timeout)} seconds", fg="yellow")
                    time.sleep(int(timeout))
                    timeout = timeout*1.5
        try:
            retry(self.check_redis)
            retry(self.check_db)
            retry(self.check_mq)
            retry(self.check_s3)
            retry(self.check_search)
        except:
            if check_only:
                return False
            raise

    def check_redis(self):
        host, port = self._get_configuration('INVENIO_REDIS_HOST', 'INVENIO_REDIS_PORT')
        pool = redis.ConnectionPool(host=host, port=port, db=0)
        r = redis.Redis(connection_pool=pool)
        r.keys('blahblahblah')      # fails if there is no connection
        pool.disconnect()

    def check_db(self):
        host, port, user, password, dbname = self._get_configuration('DATABASE_HOST', 'DATABASE_PORT',
                                                                     'DATABASE_USER', 'DATABASE_PASSWORD',
                                                                     'DATABASE_DBNAME')

        with psycopg.connect(dbname=dbname, host=host, port=port, user=user, password=password) as conn:
            assert conn.execute('SELECT 1').fetchone()[0] == 1

    def check_mq(self):
        host, port = self._get_configuration('INVENIO_RABBIT_HOST', 'INVENIO_RABBIT_PORT')
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))
        channel = connection.channel()
        connection.process_data_events(2)
        assert connection.is_open
        connection.close()

    def check_s3(self):
        host, port, access_key, secret_key = \
            self._get_configuration('INVENIO_S3_HOST', 'INVENIO_S3_PORT',
                                    'INVENIO_S3_ACCESS_KEY', 'INVENIO_S3_SECRET_KEY')

        client = Minio(
            f"{host}:{port}",
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        client.list_buckets()

    def check_search(self):
        host, port, prefix = self._get_configuration('INVENIO_OPENSEARCH_HOST',
                                                     'INVENIO_OPENSEARCH_PORT',
                                                     'INVENIO_SEARCH_INDEX_PREFIX')
        client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            use_ssl=True,
            verify_certs=False
        )
        info = client.info(pretty=True)
        print(info)

    def _get_configuration(self, *keys):
        values = dotenv_values(self.site_dir / '.env')
        try:
            return [values[x] for x in keys]
        except KeyError as e:
            raise KeyError(f'Configuration key not found in defaults: {values.keys()}: {e}')

    def should_run(self):
        return not self._check_containers_running(True)
