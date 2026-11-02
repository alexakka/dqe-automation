import pytest

from src.connectors.file_system.parquet_reader import ParquetReader
from src.connectors.postgres.postgres_connector import PostgresConnectorContextManager
from src.data_quality.data_quality_validation_library import DataQualityLibrary


def pytest_addoption(parser):
    parser.addoption("--db_host", action="store", default="localhost", help="Database host")
    parser.addoption("--db_port", action="store", default="5434", help="Database port")
    parser.addoption("--db_name", action="store", default="mydatabase", help="Database name")
    parser.addoption("--db_user", action="store", default=None, help="Database user (required)")
    parser.addoption("--db_password", action="store", default=None, help="Database password (required)")


def pytest_configure(config):
    """Validate that all required command-line options are provided."""
    required_options = ["--db_user", "--db_password"]
    missing = [option for option in required_options if not config.getoption(option)]
    if missing:
        raise pytest.UsageError(f"Missing required option(s): {', '.join(missing)}")


@pytest.fixture(scope='session')
def db_connection(request):
    config = request.config
    try:
        with PostgresConnectorContextManager(
                db_user=config.getoption("--db_user"),
                db_password=config.getoption("--db_password"),
                db_host=config.getoption("--db_host"),
                db_name=config.getoption("--db_name"),
                db_port=config.getoption("--db_port")) as db_connector:
            yield db_connector
    except Exception as e:
        pytest.fail(f"Failed to initialize PostgresConnectorContextManager: {e}")


@pytest.fixture(scope='session')
def parquet_reader():
    yield ParquetReader()


@pytest.fixture(scope='session')
def data_quality_library():
    yield DataQualityLibrary()
