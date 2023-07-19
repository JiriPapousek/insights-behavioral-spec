# Copyright © 2022, 2023 Pavel Tisnovsky, Red Hat, Inc.
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

"""Tooling to process output generated by finished process."""
from behave.runner import Context


# Services and tools written in Go can be compiled with -cover compilation option.
# In this case each run of such service/tool will generated code coverage report,
# but only incase GOCOVERDIR environment variable is set up. If not, the binary
# print warning message which we must ignore in several tests (like check if help
# is displayed onto standard output).
COVERAGE_MESSAGE = "warning: GOCOVERDIR not set, no coverage data emitted"


def process_generated_output(context: Context, out, return_code=None):
    """Process output generated by finished process."""
    assert out is not None

    # interact with the process:
    # read data from stdout and stderr, until end-of-file is reached
    stdout, stderr = out.communicate()

    # basic checks if process was able to communicate with its parent
    assert stderr is None, "Error during check"
    assert stdout is not None, "No output from process"

    # check the return code of a process
    # TODO: we will need to support more return codes later
    if return_code:
        assert (
            out.returncode == 0 or out.returncode == return_code
        ), "Return code is {}".format(out.returncode)

    # try to decode output as flow of text lines
    output = stdout.decode("utf-8").split("\n")

    # filter coverage message
    output = [line for line in output if line != COVERAGE_MESSAGE]

    # check again, just for sure
    assert output is not None

    # update testing context
    context.output = output
    context.stdout = stdout
    context.stderr = stderr

    context.return_code = out.returncode


def filter_coverage_message(output: str) -> str:
    """Filter message about missing GOCOVERDIR etc."""
    return output.replace(COVERAGE_MESSAGE + "\n", "")


if __name__ == "__main__":
    # just check functions defined above
    print(filter_coverage_message("foo bar baz\n"))
    print(filter_coverage_message("foo\nbar\nbaz\n"))
    print(filter_coverage_message("foo\nwarning: GOCOVERDIR not set, no coverage data emitted\nbaz\n"))  # noqa E501
