"""
Testing config
"""
import os


debug = False
secret_key = "---- This is a fake secret key just for testing ----"

database = {
    "uri": os.getenv("DBTESTS_URI", "postgres://@localhost/[[ name ]]_tests"),
}
