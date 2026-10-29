import os
import sys
import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    '''
    Local spark session for mock data frames
    '''
    os.environ["PYSPARK_PYTHON"] = sys.executable

    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield session
    session.stop()