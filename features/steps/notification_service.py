# Copyright © 2021 Pavel Tisnovsky, Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Implementation of test steps that run CCX Notification Service and check its output."""

import json
import os
import subprocess
import requests

from behave import register_type, then, when, given


# default name of file generated by CCX Notification Service during testing
TEST_OUTPUT = "test"


def parse_max_age(max_age):
    """
    Return parsed text as str if it fits expected format (not really better than
    using {max_age:d} {age_unit:w}, but at least this way it is clear when it
    gets unexpected values).
    """
    assert isinstance(
        max_age, str
    ), f"expected max_age to be a string with 2 parts: " \
       f"the value and the unit. Got {type(max_age)} - {max_age}"  # noqa E501

    items = max_age.replace('"', "").split(" ")
    assert (
        len(items) == 2
    ), f"expected max_age to have 2 parts: the value and the unit. Got {max_age}"
    assert items[
        0
    ].isdigit(), f"expected max_age to start with an integer, got {items[0]}"
    assert items[
        1
    ].isalpha(), f"expected max_age to contain an alpha string for the max_age unit, got {items[1]}"
    return max_age


# register user-defined type
register_type(Age=parse_max_age)


def process_ccx_notification_service_output(context, out, return_codes):
    """Process CCX Notification Service output."""
    assert out is not None

    # interact with the process:
    # read data from stdout and stderr, until end-of-file is reached
    stdout, stderr = out.communicate()

    # basic checks
    assert stderr is None, "Error during check"
    assert stdout is not None, "No output from application"

    # check the return code of a process
    assert (
        out.returncode == 0 or out.returncode in return_codes
    ), f"Return code is {out.returncode}. Check the logs:\nvvvvv\n{stdout.decode('utf-8')}\n^^^^^\n"
    # try to decode output
    output = stdout.decode("utf-8").split("\n")

    assert output is not None

    # update testing context
    context.output = output
    context.stdout = stdout
    context.stderr = stderr
    context.returncode = out.returncode


@when("max-age {age:Age} command line flag is specified")
def store_max_age_flag(context, age):
    """Add max-age flag to CLI parameters of the CCX Notification Service."""
    # update context
    context.max_age = age


@when("cleanup-on-startup command line flag is specified")
def store_cleanup_flag(context):
    """Add cleanup-on-startup flag to CLI parameters of the CCX Notification Service."""
    # update context
    context.cleanup_on_startup = "--cleanup-on-startup"


@when("I start the CCX Notification Service with the {flag} command line flag")
def start_ccx_notification_service_with_flag(context, flag):
    """
    Start the CCX Notification Service with given command-line flag.

    You can pass environment variables in a table with columns "val" and "var":

        | val                                             | var   |
        | CCX_NOTIFICATION_SERVICE__KAFKA_BROKER__ENABLED | false |
    """
    params = ["ccx-notification-service", flag]
    if hasattr(context, "max_age"):
        params.append("--max-age=" + context.max_age)
    if hasattr(context, "cleanup_on_startup"):
        params.append(context.cleanup_on_startup)
    if not hasattr(context, "return_codes"):
        # 4 - Content service not available
        # 5 - Kafka broker not available
        # 9 - Prometheus push gateway not available
        # We don't care, unless explicitly configured for a test
        context.return_codes = [4, 5, 9]

    env = os.environ.copy()
    if context.table is not None:
        for row in context.table:
            env[row["val"]] = row["var"]

    out = subprocess.Popen(
        params, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env
    )
    assert out is not None
    process_ccx_notification_service_output(context, out, context.return_codes)


def check_help_from_ccx_notification_service(context):
    """Check if help is displayed by CCX Notification Service."""
    expected_output = [
        "  -cleanup-on-startup",
        "  -instant-reports",
        "  -max-age string",
        "  -new-reports-cleanup",
        "  -old-reports-cleanup",
        "  -print-new-reports-for-cleanup",
        "  -print-old-reports-for-cleanup",
        "  -show-authors",
        "  -show-configuration",
        "  -show-version",
        "  -weekly-reports",
    ]

    # preliminary checks
    assert context.output is not None
    assert isinstance(context.output, list), "wrong type of output"

    for item in expected_output:
        assert item in context.output, f"{item} not in {context.output}"


def check_version_from_ccx_notification_service(context):
    """Check if version info is displayed by CCX Notification Service."""
    # preliminary checks
    assert context.output is not None
    assert isinstance(context.output, list), "wrong type of output"

    # check the output
    assert (
        "Notification service version 1.0" in context.output
    ), f"Caught output: {context.output}"


def check_authors_info_from_ccx_notification_service(context):
    """Check if information about authors is displayed by CCX Notification Service."""
    # preliminary checks
    assert context.output is not None
    assert isinstance(context.output, list), "wrong type of output"

    # check the output
    assert (
        "Pavel Tisnovsky, Papa Bakary Camara, Red Hat Inc." in context.output
    ), f"Caught output: {context.output}"


@then("I should see the current configuration displayed on standard output")
def check_configuration_info_from_ccx_notification_service(context):
    """Check if information about authors is displayed by CCX Notification Service."""
    # preliminary checks
    assert context.output is not None
    assert isinstance(context.output, list), "wrong type of output"
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    expected_info = [
        "parsing configuration file",
        "Broker configuration",
        "Storage configuration",
        "Logging configuration",
        "Notifications configuration",
        "Metrics configuration",
        "ServiceLog configuration",
    ]

    for item in expected_info:
        assert item in stdout, f"Caught output: {stdout}"


@then(
    "I should see info about not notified reports older "
    "than {max_age:Age} displayed on standard output"
)
def check_print_new_reports_for_cleanup(context, max_age):
    """
    Check message with list of new reports to be cleaned.

    Check if information about new reports for cleanup is displayed
    by CCX Notification Service.
    """
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert "PrintReportsForCleanup operation" in stdout, f"Caught output: {stdout}"
    assert "FROM new_reports" in stdout, f"Caught output: {stdout}"
    assert max_age in stdout, f"Caught output: {stdout}"


@then(
    "I should see info about cleaned up not notified reports "
    "older than {max_age:Age} displayed on standard output"
)
def check_new_reports_cleanup(context, max_age):
    """
    Check cleanup of new reports message.

    Check if information about not notified reports cleanup is
    displayed by CCX Notification Service.
    """
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert (
        "Cleanup operation for all organizations" in stdout
    ), f"Caught output: {stdout}"
    assert "FROM new_reports" in stdout, f"Caught output: {stdout}"
    assert max_age in stdout, f"Caught output: {stdout}"
    assert "Cleanup `new_reports` finished" in stdout, f"Caught output: {stdout}"


@then(
    "I should see info about notified reports older "
    "than {max_age:d} {age_unit:w} displayed on standard output"
)  # noqa E501
def check_print_old_reports_for_cleanup(context, max_age, age_unit):
    """
    Check message with list of old reports to be cleaned.

    Check if information about notified reports for cleanup is displayed
    by CCX Notification Service.
    """  # noqa E501
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert "PrintReportsForCleanup operation" in stdout, f"Caught output: {stdout}"
    assert "FROM reported" in stdout, f"Caught output: {stdout}"
    assert str(max_age) + " " + age_unit in stdout, f"Caught output: {stdout}"


@then(
    "I should see info about cleaned up notified reports older "
    "than {max_age:d} {age_unit:w} displayed on standard output"
)
def check_old_reports_cleanup(context, max_age, age_unit):
    """
    Check if information about notified reports for cleanup
    is displayed by CCX Notification Service.
    """
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert (
        "Cleanup operation for all organizations" in stdout
    ), f"Caught output: {stdout}"
    assert "FROM reported" in stdout, f"Caught output: {stdout}"
    assert str(max_age) + " " + age_unit in stdout, f"Caught output: {stdout}"
    assert "Cleanup `reported` finished" in stdout, f"Caught output: {stdout}"


@then("I should see old reports from {table:w} for the following clusters")
def check_old_reports_in_table(context, table):
    """Check the old reports displayed for the given table."""
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert f"Old report from `{table}` table" in stdout, f"Caught output: {stdout}"
    for row in context.table:
        assert row["org id"] in stdout, f"Caught output: {stdout}"
        assert row["account number"] in stdout, f"Caught output: {stdout}"
        assert row["cluster name"] in stdout, f"Caught output: {stdout}"


@then("I should not see any old reports from {table:w}")
def check_no_old_reports_in_table(context, table):
    """Check the old reports displayed for the given table."""
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert f"Old report from `{table}` table" not in stdout, f"Caught output: {stdout}"
    assert "ClusterName" not in stdout


@then("the process should exit with status code set to {expected_code:d}")
def check_status_code(context, expected_code):
    """Check the status code of the last started process."""
    # check the return code of a process
    assert (
        context.returncode == expected_code
    ), f"Return code is {context.returncode}, but {expected_code} is expected. " \
       f"Check the logs:\n{context.stdout.decode('utf-8')}"


@then("It should clean items in {table:w} table older than {max_age:Age}")
def check_cleaned_items_on_standard_output(context, table, max_age):
    """Check stdout for cleaned report after CCX Notification Service execution."""
    # preliminary checks
    assert context.stdout is not None
    stdout = context.stdout.decode("utf-8").replace("\t", "    ")

    # preliminary checks
    assert stdout is not None, "stdout object should exist"
    assert isinstance(stdout, str), "wrong type of stdout object"

    assert (
        "Cleanup operation for all organizations" in stdout
    ), f"Caught output: {stdout}"
    assert f"Cleanup `{table}` finished" in stdout, f"Caught output: {stdout}"
    assert max_age in stdout, f"Caught output: {stdout}"


def get_events_kafka(num_event):
    """Get the latest {num_event} messages in Kafka."""
    # use the Kafkacat tool to retrieve metadata from Kafka broker:
    # -J enables Kafkacat to produce output in JSON format
    # -L flag choose mode: metadata list
    address = "localhost:9092"
    topic = "platform.notifications.ingress"

    params = [
        "kafkacat",
        "-b",
        address,
        "-C",
        "-t",
        topic,
        "-c",
        str(num_event),
        "-o",
        str(-num_event),
        "-e",
    ]

    print("subprocess: ", params)
    out = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # check if call was correct
    assert out is not None

    # interact with the process:
    # read data from stdout and stderr, until end-of-file is reached
    stdout, _ = out.communicate()

    # try to decode output
    output = stdout.decode("utf-8")

    if "Unknown topic or partition" in output:
        return []

    return [i for i in output.split("\n") if i and i[0] == "{"]


@then("it should have sent {num_event:d} notification events to Kafka")
def count_notification_events_kafka(context, num_event):
    """Get events from kafka topic and count them to check if matches."""
    events = get_events_kafka(num_event)
    assert (
        len(events) == num_event
    ), f"Retrieved {len(events)} events when {num_event} was expected"


@then("it should have sent the following {num_event:d} notification events to Kafka")
def retrieve_notification_events_kafka(context, num_event):
    """Get events from kafka topic and check they are the expected."""
    events = get_events_kafka(num_event)
    count_notification_events_kafka(context, num_event)

    for index, line in enumerate(events):
        print("The index: ", index, "The line: ", line)
        # JSON format is expected
        encoded = json.loads(line)

        # check encoding step
        assert encoded is not None

        # let's verify the data
        assert (
            "bundle" in encoded and encoded["bundle"] == "openshift"
        ), "Expected event to contain the `openshift` bundle"
        assert (
            "application" in encoded and encoded["application"] == "advisor"
        ), "Expected event to contain the `advisor` application"
        assert (
            "event_type" in encoded and encoded["event_type"] == "new-recommendation"
        ), "Expected event to contain the `new-recommendation` event type"
        assert (
            "account_id" in encoded
        ), "Expected `account_id` to be included in the event"

        account_id = context.table[index]["account number"]
        cluster_id = context.table[index]["cluster name"]
        total_risk = context.table[index]["total risk"]
        assert (
            account_id == encoded["account_id"]
        ), f"Expected account id to be {account_id}"
        assert (
            cluster_id in encoded["context"]
        ), f"Expected cluster name in event to be {cluster_id}."
        assert (
            f'"total_risk":"{total_risk}"' in encoded["events"][0]["payload"]
        ), f'"total_risk":"{total_risk}" not in {encoded["events"][0]["payload"]}'


def get_events_service_log():
    """Retrieve the events from service log."""
    address = "http://localhost:8000"
    response = requests.get(
        address + "/api/service_logs/v1/cluster_logs",
        headers={"Authorization": "TEST_TOKEN"},
    )
    assert (
        response.status_code == 200
    ), f'unexpected status code: got "{response.status_code}" want "200"'
    return response.json()["items"]


@given("service-log service is empty")
def remove_service_log_logs(context):
    """Delete all the logs from service log."""
    address = "http://localhost:8000"
    logs = get_events_service_log()
    for log in logs:
        response = requests.delete(
            address + "/api/service_logs/v1/cluster_logs/" + log["id"],
            headers={"Authorization": "TEST_TOKEN"},
        )
        assert (
            response.status_code == 204
        ), f'unexpected status code: got "{response.status_code}" want "204"'


@then("it should have sent {num_event:d} notification events to Service Log")
def count_notification_events_service_log(context, num_event):
    """Get events from kafka topic and count them to check if matches."""
    events = get_events_service_log()
    assert (
        len(events) == num_event
    ), f"Retrieved {len(events)} events when {num_event} was expected"


@then("the logs should match")
def check_logs(context):
    """Check if the notification service logs logs given the context,table.

    You can specify whether if the substring should be present or not.
    | log                      | contains |
    | this one should match    | yes      |
    | this one should't match  | no       |
    """
    output = context.stdout.decode("utf-8")

    for row in context.table:
        log, contains = row["log"], row["contains"]
        if contains == "yes":
            assert log in output, f'log "{log}" not found in output:\n{output}'
        elif contains == "no":
            assert log not in output, f'log "{log}" found in output:\n{output}'
        else:
            raise ValueError(f'option "{contains}" is other than "yes" or "no"')
