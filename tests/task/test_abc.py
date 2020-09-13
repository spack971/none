# tests/task/test_abc.py
# ======================
#
# Copying
# -------
#
# Copyright (c) 2020 none authors and contributors.
#
# This file is part of the *none* project.
#
# None is a free software project. You can redistribute it and/or
# modify it following the terms of the MIT License.
#
# This software project is distributed *as is*, WITHOUT WARRANTY OF ANY
# KIND; including but not limited to the WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE and NONINFRINGEMENT.
#
# You should have received a copy of the MIT License along with
# *none*. If not, see <http://opensource.org/licenses/MIT>.
#
"""Test cases for :mod:`none.task.abc`."""
from itertools import zip_longest

import pytest

import none


@pytest.fixture
def EOFTask():
    """Generate a task class failing with ``EOFError``."""

    class EOFTask(none.task.abc.Task):
        """A task raising ``EOFError``.

        This task fails by default.

        """

        def __call__(self, *args, **kwargs):
            raise EOFError()

    return EOFTask


@pytest.fixture
def EOFArgumentTask(EOFTask):
    """Generate an argument task class failing with ``EOFError``."""

    class EOFArgumentTask(EOFTask, none.task.abc.ArgumentTask):
        def __init__(self, with_version: bool = False, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.with_version = with_version

        @property
        def version(self):
            if self.with_version:
                return "0.0.0"

    return EOFArgumentTask


@pytest.fixture
def SequenceBatch():
    """Generate a batch task which count up to provided number."""

    class SequenceBatch(none.task.abc.Batch, none.task.abc.Task):
        """A counter."""

        def __init__(self, stop: int = 0, *args, **kwargs):
            super(SequenceBatch, self).__init__(*args, **kwargs)
            self.stack = []
            self.stop = stop
            self.batch_size = 1

        def __call__(self, number: int):
            self.stack.append(number)

        @property
        def data(self):
            yield from range(self.stop)

    return SequenceBatch


@pytest.fixture
def SuperBatch():
    """Generate a batch task which just call the super class."""

    class SuperBatch(none.task.abc.Batch, none.task.abc.Task):
        def __init__(self, stop: int = 0, *args, **kwargs):
            super(SuperBatch, self).__init__(*args, **kwargs)
            self.stop = stop
            self.batch_size = 1

        def __call__(self, *args, **kwargs):
            super(SuperBatch, self).__call__(*args, **kwargs)

        @property
        def data(self):
            yield from range(self.stop)

    return SuperBatch


@pytest.fixture
def eoftask(EOFTask):
    """Generate an instance of ``EOFTask``."""
    return EOFTask()


@pytest.fixture
def eofargumenttask(EOFArgumentTask):
    """Generate an instance of ``EOFArgumentTask``."""
    return EOFArgumentTask()


@pytest.fixture
def sequencebatch(SequenceBatch):
    """Generate an instance of ``SequenceBatch``."""
    return SequenceBatch()


class TestTask(object):
    """Test cases for :class:`none.task.abc.Task`."""

    def test_description_defaults_to_docstring(self, eoftask):
        """The task description defaults to the first line in the docstring."""
        assert eoftask.description == eoftask.__doc__.splitlines()[0]

    def test_name_defaults_to_lower_class_name(self, eoftask):
        """The task name defaults to the class' name lower cased."""
        assert eoftask.name == eoftask.__class__.__name__.lower()

    def test_run_default_should_raises(self, eoftask):
        """By default a task will raise on failure."""
        with pytest.raises(EOFError):
            eoftask.run()

    def test_run_raise_exc_to_false_should_not_raise(self, eoftask):
        """Setting ``raise_exc`` to ``False`` should not raise the exception."""
        eoftask.raise_exc = False
        eoftask.run()

    def test_run_ignore_exc_are_raised(self, eoftask):
        """An ignored exception is be raised when ``raise_exc`` is ``True``."""
        eoftask.raise_exc = True
        eoftask.ignore_exc = (EOFError,)
        with pytest.raises(EOFError):
            eoftask.run()

    def test_run_ignore_exc_can_be_inhibited(self, eoftask):
        """An ignored exception can be inhibited when ``raise_exc`` is
        ``False``.

        """
        eoftask.raise_exc = False
        eoftask.ignore_exc = (EOFError,)
        eoftask.run()

    def test_run_events_should_be_called_in_order(self, EOFTask):
        """Events should be called following the execution flow."""
        stack = []

        class T(EOFTask):
            def on_call(self):
                stack.append("on_call")

            def on_done(self):
                stack.append("on_done")

            def on_exit(self):
                stack.append("on_exit")

        t = T()
        with pytest.raises(EOFError):
            t.run()

        assert stack == ["on_call", "on_done", "on_exit"]

    def test_run_caught_events_should_be_called_in_order(self, EOFTask):
        """Events can be caught nd hanging functions should be called following
        the execution flow.

        """
        stack = []

        class T(EOFTask):
            @none.callable.catch("on_call")
            def catch_call(self):
                stack.append("on_call")

            @none.callable.catch("on_done")
            def catch_done(self):
                stack.append("on_done")

            @none.callable.catch("on_exit")
            def catch_exit(self):
                stack.append("on_exit")

        t = T()
        with pytest.raises(EOFError):
            t.run()

        assert stack == ["on_call", "on_done", "on_exit"]

    def test_run_on_failure_should_be_called_on_exception(self, EOFTask):
        """In case of error, the ``on_failure()`` event should be called with
        the raised exception.

        """
        stack = []

        # EOFTask raises ``EOFError`` when called.
        class T(EOFTask):
            def on_failure(self, *exc):
                for e in exc:
                    stack.append(e)

        t = T()
        with pytest.raises(EOFError):
            t.run()

        for a, b in zip_longest(stack, [EOFError]):
            assert isinstance(a, b)

    def test_run_all_exception_raised_should_be_passed_to_on_failure_in_order(
        self, EOFTask
    ):
        """When the ``on_done()`` event is raising an exception it should also
        be passed along with the original exception.

        """
        stack = []

        # EOFTask raises ``EOFError`` when called.
        class T(EOFTask):
            def on_done(self):
                raise InterruptedError

            def on_failure(self, *exc):
                self.raise_exc = False
                for e in exc:
                    stack.append(e)

        t = T()
        t.run()

        for a, b in zip_longest(stack, [EOFError, InterruptedError]):
            assert isinstance(a, b)

    def test_run_last_exception_is_raised(self, EOFTask):
        """In case, multiple exception are raised during the task execution,
        only the last one will be raised upwards.

        """
        # EOFTask raises ``EOFError`` when called.
        stack = []

        class T(EOFTask):
            def on_done(self):
                raise InterruptedError

            def on_failure(self, *exc):
                for e in exc:
                    stack.append(e)

        t = T()
        with pytest.raises(InterruptedError) as exc:
            t.run()

        assert isinstance(stack[-1], exc.type)

    def test_run_ignored_exception_should_be_passed_to_on_success(self, EOFTask):
        """Ignored raised exceptions should be passed to the ``on_success()``
        event.

        """
        stack = []

        # EOFTask raises ``EOFError`` when called.
        class T(EOFTask):
            def on_success(self, *exc):
                for e in exc:
                    stack.append(e)

        t = T(ignore_exc=(EOFError,))
        with pytest.raises(EOFError):
            t.run()

        for a, b in zip_longest(stack, [EOFError]):
            assert isinstance(a, b)

    def test_on_failure_can_inhibit_error_propagation(self, EOFTask):
        """The ``on_failure()`` event can prevent the exception to propagate
        towards upper layers.

        """
        # EOFTask raises ``EOFError`` when called.
        class T(EOFTask):
            def on_failure(self, *exc):
                self.raise_exc = False

        t = T()
        t.run()


class TestArgumentTask(object):
    """Test cases for :class:`none.task.abc.ArgumentTask`."""

    def test_parse_args_no_version_when_empty(self, eofargumenttask):
        """The version option should not be generated when the task's version
        is null.

        """
        with pytest.raises(SystemExit):
            eofargumenttask.parse_args(["--version"])

    @pytest.mark.parametrize(
        "with_version,stream,expected",
        [
            (True, "out", "eofargumenttask 0.0.0"),
            (False, "err", "eofargumenttask: error: unrecognized arguments: --version"),
        ],
    )
    def test_parse_args_no_version_when_empty(
        self, capsys, eofargumenttask, with_version, stream, expected
    ):
        """The version option should not be generated when the task's version
        is null.

        """
        eofargumenttask.with_version = with_version
        with pytest.raises(SystemExit):
            eofargumenttask.parse_args(["--version"])

        captured = capsys.readouterr()
        assert getattr(captured, stream).splitlines()[-1] == expected

    def test_parse_args_to_opts(self, EOFArgumentTask):
        """Make sure ``parse_args`` produces the expected options."""

        class T(EOFArgumentTask):
            @property
            def arguments(self):
                return (
                    (("-o", "--opt"), {"action": "store_true"}),
                    (("positional",), {}),
                )

        t = T()
        t.parse_args(["--opt", "REQUIRED"])

        assert not hasattr(t.opts, "INVALID")
        assert hasattr(t.opts, "opt")
        assert hasattr(t.opts, "positional")
        assert t.opts.opt is True
        assert t.opts.positional == "REQUIRED"

    def test_parse_args_should_call_on_argparse(self, EOFArgumentTask):
        """Parsing command line arguments must trigger the ``on_argparse()``
        event.

        """
        stack = []

        class T(EOFArgumentTask):
            def on_argparse(self):
                stack.append("on_argparse")

        t = T()
        t.parse_args([])

        assert stack == ["on_argparse"]

    def test_on_argparse_can_be_caught(self, EOFArgumentTask):
        """Parsing command line arguments must trigger the ``on_argparse()``
        event.

        """
        stack = []

        class T(EOFArgumentTask):
            @none.callable.catch("on_argparse")
            def catch_argparse(self):
                stack.append("catch_argparse")

        t = T()
        t.parse_args([])

        assert stack == ["catch_argparse"]


class TestBatch(object):
    """Test cases for :class:`none.task.abc.Batch`."""

    def test_run_ensure_expected(self, sequencebatch):
        """Make sure the batch task executes as expected."""
        nruns = 5

        sequencebatch.stop = nruns
        sequencebatch.run()

        assert sequencebatch.stack == list(range(nruns))

    def test_run_should_call_a_new_task(self, SequenceBatch):
        stack = []
        nruns = 5

        class T(SequenceBatch):
            def on_call(self):
                stack.append("called")

        t = T(stop=nruns)
        t.run()

        assert len(stack) == nruns

    def test_run_ignored_exception_are_raised(self, SuperBatch, EOFTask):
        """Ignored exceptions are raised when ``raise_exc`` is ``True``."""
        stack = []
        nruns = 3

        # EOFTask raises ``EOFError`` when called.
        class T(SuperBatch, EOFTask):
            pass

        t = T(stop=nruns, raise_exc=True, ignore_exc=(EOFError,))
        with pytest.raises(EOFError):
            t.run()

    def test_run_ignored_exception_can_be_inhibited(self, SuperBatch, EOFTask):
        """Ignored exceptions are *not* raised when ``raise_exc`` is ``False``.

        """
        stack = []
        nruns = 3

        # EOFTask raises ``EOFError`` when called.
        class T(SuperBatch, EOFTask):
            pass

        t = T(stop=nruns, raise_exc=False, ignore_exc=(EOFError,))
        t.run()

    def test_run_events_should_be_called_in_order(self, SequenceBatch):
        """Events should be called following the execution flow."""
        stack = []

        class T(SequenceBatch):
            def on_batch_call(self):
                stack.append("on_batch_call")

            def on_batch_done(self):
                stack.append("on_batch_done")

            def on_batch_exit(self):
                stack.append("on_batch_exit")

        t = T()
        t.run()

        assert stack == ["on_batch_call", "on_batch_done", "on_batch_exit"]

    def test_run_caught_events_should_be_called_in_order(self, SequenceBatch):
        """Events can be caught and hanging functions should be called following
        the execution flow.

        """
        stack = []

        class T(SequenceBatch):
            @none.callable.catch("on_batch_call")
            def catch_batch_call(self):
                stack.append("on_batch_call")

            @none.callable.catch("on_batch_done")
            def catch_batch_done(self):
                stack.append("on_batch_done")

            @none.callable.catch("on_batch_exit")
            def catch_batch_exit(self):
                stack.append("on_batch_exit")

        t = T()
        t.run()

        assert stack == ["on_batch_call", "on_batch_done", "on_batch_exit"]

    def test_run_on_batch_failure_should_be_called_on_exception(
        self, SuperBatch, EOFTask
    ):
        """In case of error, the ``on_batch_failure()`` event should be called
        with the raised exception.

        """
        stack = []
        nruns = 2

        # EOFTask raises ``EOFError`` when called.
        class T(SuperBatch, EOFTask):
            def on_batch_failure(self, *exc):
                for e in exc:
                    stack.append(e)

        t = T(stop=nruns)
        with pytest.raises(EOFError):
            t.run()

        for a, b in zip_longest(stack, [EOFError]):
            assert isinstance(a, b)

    def test_run_all_exception_raised_should_be_passed_to_on_batch_failure_in_order(
        self, SuperBatch, EOFTask
    ):
        """When the ``on_batch_done()`` event is raising an exception it should
        also be passed along with the original exception.

        """
        stack = []
        nruns = 2

        # EOFTask raises ``EOFError`` when called.
        class T(SuperBatch, EOFTask):
            def on_batch_done(self):
                raise InterruptedError

            def on_batch_failure(self, *exc):
                self.batch_raise_exc = False
                for e in exc:
                    stack.append(e)

        t = T(stop=nruns)
        t.run()

        for a, b in zip_longest(stack, [EOFError, InterruptedError]):
            assert isinstance(a, b)

    def test_run_last_exception_is_raised(self, SuperBatch, EOFTask):
        """In case, multiple exception are raised during the task execution,
        only the last one will be raised upwards.

        """
        # EOFTask raises ``EOFError`` when called.
        stack = []
        nruns = 2

        class T(SuperBatch, EOFTask):
            def on_batch_done(self):
                raise InterruptedError

            def on_batch_failure(self, *exc):
                for e in exc:
                    stack.append(e)

        t = T(stop=nruns)
        with pytest.raises(InterruptedError) as exc:
            t.run()

        assert isinstance(stack[-1], exc.type)

    def test_run_ignored_exception_should_be_passed_to_on_batch_success(
        self, SuperBatch, EOFTask
    ):
        """Ignored raised exceptions should be passed to the
        ``on_batch_success()`` event.

        """
        stack = []
        nruns = 3

        # EOFTask raises ``EOFError`` when called.
        class T(SuperBatch, EOFTask):
            def on_batch_success(self, *exc):
                for e in exc:
                    stack.append(e)

        t = T(stop=nruns, ignore_exc=(EOFError,))
        with pytest.raises(EOFError):
            t.run()

        for a, b in zip_longest(stack, [EOFError] * nruns):
            assert isinstance(a, b)

    def test_on_batch_failure_can_inhibit_error_propagation(self, SuperBatch, EOFTask):
        """The ``on_failure()`` event can prevent the exception to propagate
        towards upper layers.

        """
        nruns = 2

        # EOFTask raises ``EOFError`` when called.
        class T(SuperBatch, EOFTask):
            def on_batch_failure(self, *exc):
                self.batch_raise_exc = False

        t = T(stop=nruns)
        t.run()