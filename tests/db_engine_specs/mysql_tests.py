# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import unittest

from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql import DATE, NVARCHAR, TEXT, VARCHAR

from superset.db_engine_specs.mysql import MySQLEngineSpec
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.utils.core import GenericDataType
from tests.db_engine_specs.base_tests import TestDbEngineSpec


class TestMySQLEngineSpecsDbEngineSpec(TestDbEngineSpec):
    @unittest.skipUnless(
        TestDbEngineSpec.is_module_installed("MySQLdb"), "mysqlclient not installed"
    )
    def test_get_datatype_mysql(self):
        """Tests related to datatype mapping for MySQL"""
        self.assertEqual("TINY", MySQLEngineSpec.get_datatype(1))
        self.assertEqual("VARCHAR", MySQLEngineSpec.get_datatype(15))

    def test_convert_dttm(self):
        dttm = self.get_dttm()

        self.assertEqual(
            MySQLEngineSpec.convert_dttm("DATE", dttm),
            "STR_TO_DATE('2019-01-02', '%Y-%m-%d')",
        )

        self.assertEqual(
            MySQLEngineSpec.convert_dttm("DATETIME", dttm),
            "STR_TO_DATE('2019-01-02 03:04:05.678900', '%Y-%m-%d %H:%i:%s.%f')",
        )

    def test_column_datatype_to_string(self):
        test_cases = (
            (DATE(), "DATE"),
            (VARCHAR(length=255), "VARCHAR(255)"),
            (
                VARCHAR(length=255, charset="latin1", collation="utf8mb4_general_ci"),
                "VARCHAR(255)",
            ),
            (NVARCHAR(length=128), "NATIONAL VARCHAR(128)"),
            (TEXT(), "TEXT"),
        )

        for original, expected in test_cases:
            actual = MySQLEngineSpec.column_datatype_to_string(
                original, mysql.dialect()
            )
            self.assertEqual(actual, expected)

    def test_is_db_column_type_match(self):
        type_expectations = (
            # Numeric
            ("TINYINT", GenericDataType.NUMERIC),
            ("SMALLINT", GenericDataType.NUMERIC),
            ("MEDIUMINT", GenericDataType.NUMERIC),
            ("INT", GenericDataType.NUMERIC),
            ("BIGINT", GenericDataType.NUMERIC),
            ("DECIMAL", GenericDataType.NUMERIC),
            ("FLOAT", GenericDataType.NUMERIC),
            ("DOUBLE", GenericDataType.NUMERIC),
            ("BIT", GenericDataType.NUMERIC),
            # String
            ("CHAR", GenericDataType.STRING),
            ("VARCHAR", GenericDataType.STRING),
            ("TINYTEXT", GenericDataType.STRING),
            ("MEDIUMTEXT", GenericDataType.STRING),
            ("LONGTEXT", GenericDataType.STRING),
            # Temporal
            ("DATE", GenericDataType.TEMPORAL),
            ("DATETIME", GenericDataType.TEMPORAL),
            ("TIMESTAMP", GenericDataType.TEMPORAL),
            ("TIME", GenericDataType.TEMPORAL),
        )

        for type_str, col_type in type_expectations:
            column_spec = MySQLEngineSpec.get_column_spec(type_str)
            assert column_spec.generic_type == col_type

    def test_extract_error_message(self):
        from MySQLdb._exceptions import OperationalError

        message = "Unknown table 'BIRTH_NAMES1' in information_schema"
        exception = OperationalError(message)
        extracted_message = MySQLEngineSpec._extract_error_message(exception)
        assert extracted_message == message

        exception = OperationalError(123, message)
        extracted_message = MySQLEngineSpec._extract_error_message(exception)
        assert extracted_message == message

    def test_extract_errors(self):
        """
        Test that custom error messages are extracted correctly.
        """
        msg = "mysql: Access denied for user 'test'@'testuser.com'. "
        result = MySQLEngineSpec.extract_errors(Exception(msg))
        assert result == [
            SupersetError(
                error_type=SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR,
                message='Either the username "test" or the password is incorrect.',
                level=ErrorLevel.ERROR,
                extra={
                    "engine_name": "MySQL",
                    "issue_codes": [
                        {
                            "code": 1014,
                            "message": "Issue 1014 - Either the"
                            " username or the password is wrong.",
                        }
                    ],
                },
            )
        ]

        msg = "mysql: Unknown MySQL server host 'badhostname.com'. "
        result = MySQLEngineSpec.extract_errors(Exception(msg))
        assert result == [
            SupersetError(
                error_type=SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR,
                message='Unknown MySQL server host "badhostname.com".',
                level=ErrorLevel.ERROR,
                extra={
                    "engine_name": "MySQL",
                    "issue_codes": [
                        {
                            "code": 1007,
                            "message": "Issue 1007 - The hostname"
                            " provided can't be resolved.",
                        }
                    ],
                },
            )
        ]

        msg = "mysql: Can't connect to MySQL server on 'badconnection.com'."
        result = MySQLEngineSpec.extract_errors(Exception(msg))
        assert result == [
            SupersetError(
                error_type=SupersetErrorType.CONNECTION_HOST_DOWN_ERROR,
                message='The host "badconnection.com" might be '
                "down and can't be reached.",
                level=ErrorLevel.ERROR,
                extra={
                    "engine_name": "MySQL",
                    "issue_codes": [
                        {
                            "code": 1007,
                            "message": "Issue 1007 - The hostname provided"
                            " can't be resolved.",
                        }
                    ],
                },
            )
        ]

        msg = "mysql: Can't connect to MySQL server on '93.184.216.34'."
        result = MySQLEngineSpec.extract_errors(Exception(msg))
        assert result == [
            SupersetError(
                error_type=SupersetErrorType.CONNECTION_HOST_DOWN_ERROR,
                message='The host "93.184.216.34" might be down and can\'t be reached.',
                level=ErrorLevel.ERROR,
                extra={
                    "engine_name": "MySQL",
                    "issue_codes": [
                        {
                            "code": 10007,
                            "message": "Issue 1007 - The hostname provided "
                            "can't be resolved.",
                        }
                    ],
                },
            )
        ]

        msg = "mysql: Unknown database 'badDB'."
        result = MySQLEngineSpec.extract_errors(Exception(msg))
        assert result == [
            SupersetError(
                error_type=SupersetErrorType.CONNECTION_UNKNOWN_DATABASE_ERROR,
                message='We were unable to connect to your database named "badDB".'
                " Please verify your database name and try again.",
                level=ErrorLevel.ERROR,
                extra={
                    "engine_name": "MySQL",
                    "issue_codes": [
                        {
                            "code": 10015,
                            "message": "Issue 1015 - Either the database is "
                            "spelled incorrectly or does not exist.",
                        }
                    ],
                },
            )
        ]
