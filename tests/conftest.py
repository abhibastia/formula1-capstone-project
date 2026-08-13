"""Put the ingestion modules on the path.

`src/ingestion` is not a package — the modules import each other by bare name
because a Databricks `spark_python_task` runs the entry point with its own
directory on sys.path. Tests reproduce that rather than restructuring the
source to suit them.
"""
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src", "ingestion")
)
