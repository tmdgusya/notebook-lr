"""
Tests for NotebookKernel namespace operations.

Covers: get_namespace, restore_namespace, get_variable, set_variable,
del_variable, get_defined_names, and _setup_namespace behavior.
"""

import pytest
from notebook_lr.kernel import NotebookKernel


class TestGetNamespace:
    """Tests for get_namespace()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_get_namespace_returns_dict(self):
        """get_namespace returns a dict."""
        ns = self.kernel.get_namespace()
        assert isinstance(ns, dict)

    def test_get_namespace_contains_defined_variables(self):
        """Variables defined via execute_cell appear in namespace."""
        self.kernel.execute_cell("foo = 42")
        ns = self.kernel.get_namespace()
        assert "foo" in ns
        assert ns["foo"] == 42

    def test_get_namespace_excludes_private_keys(self):
        """Private/dunder variables (starting with _) are excluded."""
        ns = self.kernel.get_namespace()
        for key in ns:
            assert not key.startswith("_"), f"Private key {key!r} found in namespace"

    def test_get_namespace_contains_notebook_sentinel(self):
        """__notebook__ sentinel is set but must not appear (starts with _)."""
        # _setup_namespace sets __notebook__ = True, but get_namespace filters _-prefixed keys
        ns = self.kernel.get_namespace()
        assert "__notebook__" not in ns

    def test_get_namespace_returns_copy(self):
        """Mutating the returned dict does not affect the kernel namespace."""
        self.kernel.execute_cell("bar = 99")
        ns = self.kernel.get_namespace()
        ns["bar"] = 0
        assert self.kernel.get_variable("bar") == 99

    def test_get_namespace_multiple_types(self):
        """Namespace can hold different Python types."""
        self.kernel.execute_cell("n = 1; s = 'hello'; lst = [1, 2]; d = {'k': 'v'}")
        ns = self.kernel.get_namespace()
        assert ns["n"] == 1
        assert ns["s"] == "hello"
        assert ns["lst"] == [1, 2]
        assert ns["d"] == {"k": "v"}

    def test_get_namespace_empty_after_reset(self):
        """After reset, only non-private vars remain (none by default)."""
        self.kernel.execute_cell("z = 7")
        self.kernel.reset()
        ns = self.kernel.get_namespace()
        assert "z" not in ns

    def test_get_namespace_after_del_variable(self):
        """Deleted variable no longer appears in namespace."""
        self.kernel.execute_cell("x = 5")
        self.kernel.del_variable("x")
        ns = self.kernel.get_namespace()
        assert "x" not in ns

    def test_get_namespace_reflects_latest_value(self):
        """Namespace reflects updated variable value."""
        self.kernel.execute_cell("val = 10")
        self.kernel.execute_cell("val = 20")
        ns = self.kernel.get_namespace()
        assert ns["val"] == 20


class TestRestoreNamespace:
    """Tests for restore_namespace()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_restore_namespace_adds_variables(self):
        """restore_namespace injects variables into the kernel."""
        self.kernel.restore_namespace({"alpha": 1, "beta": 2})
        assert self.kernel.get_variable("alpha") == 1
        assert self.kernel.get_variable("beta") == 2

    def test_restore_namespace_then_execute(self):
        """Variables restored via restore_namespace are accessible in code."""
        self.kernel.restore_namespace({"restored_val": 100})
        result = self.kernel.execute_cell("restored_val + 1")
        assert result.success
        assert result.return_value == 101

    def test_restore_namespace_overwrites_existing(self):
        """restore_namespace overwrites variables already in namespace."""
        self.kernel.execute_cell("x = 1")
        self.kernel.restore_namespace({"x": 999})
        assert self.kernel.get_variable("x") == 999

    def test_restore_namespace_preserves_other_variables(self):
        """restore_namespace does not remove pre-existing variables."""
        self.kernel.execute_cell("keep = 'here'")
        self.kernel.restore_namespace({"new_var": 42})
        assert self.kernel.get_variable("keep") == "here"
        assert self.kernel.get_variable("new_var") == 42

    def test_restore_namespace_empty_dict(self):
        """Restoring an empty namespace is a no-op."""
        self.kernel.execute_cell("existing = 7")
        self.kernel.restore_namespace({})
        assert self.kernel.get_variable("existing") == 7

    def test_restore_namespace_roundtrip(self):
        """get_namespace -> restore_namespace roundtrip preserves values."""
        self.kernel.execute_cell("a = 10; b = 'world'")
        snapshot = self.kernel.get_namespace()

        new_kernel = NotebookKernel()
        new_kernel.restore_namespace(snapshot)

        assert new_kernel.get_variable("a") == 10
        assert new_kernel.get_variable("b") == "world"

    def test_restore_namespace_with_complex_objects(self):
        """restore_namespace handles complex Python objects."""
        data = {"key": [1, 2, 3], "nested": {"inner": True}}
        self.kernel.restore_namespace({"complex": data})
        assert self.kernel.get_variable("complex") == data


class TestGetVariable:
    """Tests for get_variable()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_get_variable_existing(self):
        """get_variable returns value for a defined variable."""
        self.kernel.execute_cell("my_var = 55")
        assert self.kernel.get_variable("my_var") == 55

    def test_get_variable_missing_returns_none(self):
        """get_variable returns None for undefined variables."""
        result = self.kernel.get_variable("nonexistent_xyz")
        assert result is None

    def test_get_variable_after_update(self):
        """get_variable reflects the latest assignment."""
        self.kernel.execute_cell("v = 1")
        self.kernel.execute_cell("v = 2")
        assert self.kernel.get_variable("v") == 2

    def test_get_variable_private_key(self):
        """get_variable can access private keys (no filter unlike get_namespace)."""
        # __notebook__ is set by _setup_namespace
        val = self.kernel.get_variable("__notebook__")
        assert val is True

    def test_get_variable_various_types(self):
        """get_variable works for int, str, list, dict, bool, None."""
        self.kernel.execute_cell("i = 1; s = 'a'; l = []; d = {}; b = True; n = None")
        assert self.kernel.get_variable("i") == 1
        assert self.kernel.get_variable("s") == "a"
        assert self.kernel.get_variable("l") == []
        assert self.kernel.get_variable("d") == {}
        assert self.kernel.get_variable("b") is True
        assert self.kernel.get_variable("n") is None

    def test_get_variable_set_directly(self):
        """get_variable reads variables set via set_variable."""
        self.kernel.set_variable("direct", 77)
        assert self.kernel.get_variable("direct") == 77


class TestSetVariable:
    """Tests for set_variable()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_set_variable_basic(self):
        """set_variable stores value accessible via get_variable."""
        self.kernel.set_variable("x", 42)
        assert self.kernel.get_variable("x") == 42

    def test_set_variable_accessible_in_code(self):
        """Variables set via set_variable are accessible in executed code."""
        self.kernel.set_variable("injected", 100)
        result = self.kernel.execute_cell("injected * 2")
        assert result.success
        assert result.return_value == 200

    def test_set_variable_overwrites(self):
        """set_variable overwrites an existing variable."""
        self.kernel.set_variable("y", 1)
        self.kernel.set_variable("y", 999)
        assert self.kernel.get_variable("y") == 999

    def test_set_variable_none(self):
        """set_variable can store None."""
        self.kernel.set_variable("nothing", None)
        assert self.kernel.get_variable("nothing") is None

    def test_set_variable_complex_object(self):
        """set_variable can store complex objects."""
        obj = {"nested": [1, 2, 3]}
        self.kernel.set_variable("obj", obj)
        assert self.kernel.get_variable("obj") == obj

    def test_set_variable_appears_in_namespace(self):
        """Variable set via set_variable appears in get_namespace."""
        self.kernel.set_variable("visible", 5)
        ns = self.kernel.get_namespace()
        assert "visible" in ns
        assert ns["visible"] == 5

    def test_set_variable_appears_in_defined_names(self):
        """Variable set via set_variable appears in get_defined_names."""
        self.kernel.set_variable("named", 1)
        names = self.kernel.get_defined_names()
        assert "named" in names


class TestDelVariable:
    """Tests for del_variable()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_del_variable_removes_it(self):
        """del_variable removes a variable from namespace."""
        self.kernel.execute_cell("to_del = 10")
        self.kernel.del_variable("to_del")
        assert self.kernel.get_variable("to_del") is None

    def test_del_variable_nonexistent_is_noop(self):
        """del_variable on a nonexistent variable does not raise."""
        # Should not raise
        self.kernel.del_variable("never_existed_xyz")

    def test_del_variable_removed_from_namespace(self):
        """Deleted variable no longer appears in get_namespace."""
        self.kernel.execute_cell("gone = 3")
        self.kernel.del_variable("gone")
        ns = self.kernel.get_namespace()
        assert "gone" not in ns

    def test_del_variable_removed_from_defined_names(self):
        """Deleted variable no longer appears in get_defined_names."""
        self.kernel.set_variable("temp", 1)
        self.kernel.del_variable("temp")
        names = self.kernel.get_defined_names()
        assert "temp" not in names

    def test_del_variable_code_raises_after_deletion(self):
        """Code referring to deleted variable raises NameError."""
        self.kernel.execute_cell("exists = 1")
        self.kernel.del_variable("exists")
        result = self.kernel.execute_cell("exists")
        assert not result.success

    def test_del_variable_multiple(self):
        """Multiple variables can be deleted independently."""
        self.kernel.execute_cell("a = 1; b = 2; c = 3")
        self.kernel.del_variable("a")
        self.kernel.del_variable("b")
        assert self.kernel.get_variable("a") is None
        assert self.kernel.get_variable("b") is None
        assert self.kernel.get_variable("c") == 3


class TestGetDefinedNames:
    """Tests for get_defined_names()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_get_defined_names_returns_list(self):
        """get_defined_names returns a list."""
        names = self.kernel.get_defined_names()
        assert isinstance(names, list)

    def test_get_defined_names_includes_user_vars(self):
        """User-defined variables appear in defined names."""
        self.kernel.execute_cell("my_name = 1")
        names = self.kernel.get_defined_names()
        assert "my_name" in names

    def test_get_defined_names_excludes_private(self):
        """Private/dunder names (starting with _) are excluded."""
        names = self.kernel.get_defined_names()
        for name in names:
            assert not name.startswith("_"), f"Private key {name!r} found"

    def test_get_defined_names_empty_after_reset(self):
        """After reset, user-defined names are cleared."""
        self.kernel.execute_cell("clear_me = 1")
        self.kernel.reset()
        names = self.kernel.get_defined_names()
        assert "clear_me" not in names

    def test_get_defined_names_multiple_vars(self):
        """Multiple defined variables all appear."""
        self.kernel.execute_cell("x1 = 1; x2 = 2; x3 = 3")
        names = self.kernel.get_defined_names()
        assert "x1" in names
        assert "x2" in names
        assert "x3" in names

    def test_get_defined_names_after_del(self):
        """Deleted variable is removed from defined names."""
        self.kernel.execute_cell("will_del = 0")
        self.kernel.del_variable("will_del")
        names = self.kernel.get_defined_names()
        assert "will_del" not in names

    def test_get_defined_names_includes_set_variable(self):
        """Variables set via set_variable appear in defined names."""
        self.kernel.set_variable("injected_name", 99)
        names = self.kernel.get_defined_names()
        assert "injected_name" in names


class TestSetupNamespace:
    """Tests for _setup_namespace() and reset() interactions."""

    def test_notebook_sentinel_set_on_init(self):
        """__notebook__ sentinel is True after initialization."""
        kernel = NotebookKernel()
        assert kernel.get_variable("__notebook__") is True

    def test_notebook_sentinel_restored_after_reset(self):
        """__notebook__ sentinel is re-set after reset()."""
        kernel = NotebookKernel()
        kernel.ip.user_ns.pop("__notebook__", None)
        kernel.reset()
        assert kernel.get_variable("__notebook__") is True

    def test_reset_clears_user_variables(self):
        """reset() removes user-defined variables."""
        kernel = NotebookKernel()
        kernel.execute_cell("temp = 42")
        kernel.reset()
        assert kernel.get_variable("temp") is None

    def test_reset_resets_execution_count(self):
        """reset() resets execution_count to 0."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 1")
        kernel.execute_cell("y = 2")
        kernel.reset()
        assert kernel.execution_count == 0

    def test_reset_clears_history(self):
        """reset() clears execution history."""
        kernel = NotebookKernel()
        kernel.execute_cell("a = 1")
        kernel.reset()
        assert kernel.get_history() == []

    def test_can_execute_after_reset(self):
        """Kernel remains functional after reset."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 1")
        kernel.reset()
        result = kernel.execute_cell("2 + 2")
        assert result.success
        assert result.return_value == 4
