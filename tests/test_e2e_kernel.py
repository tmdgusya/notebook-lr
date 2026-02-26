"""
E2E tests for NotebookKernel execution engine and state persistence.

Tests verify the kernel's ability to maintain state across cell executions,
capture outputs correctly, and handle errors gracefully.

Note: InteractiveShell.instance() is a singleton. Each test class uses
setup_method to call kernel.reset(), ensuring a clean slate per test.
"""

import pytest
from notebook_lr.kernel import NotebookKernel, ExecutionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stdout_text(result: ExecutionResult) -> str:
    """Return concatenated stdout text from a result."""
    parts = [
        o["text"]
        for o in result.outputs
        if o.get("type") == "stream" and o.get("name") == "stdout"
    ]
    return "".join(parts)


def _error_outputs(result: ExecutionResult) -> list:
    return [o for o in result.outputs if o.get("type") == "error"]


def _execute_result_outputs(result: ExecutionResult) -> list:
    return [o for o in result.outputs if o.get("type") == "execute_result"]


# ---------------------------------------------------------------------------
# 1. Variable Persistence
# ---------------------------------------------------------------------------

class TestVariablePersistenceE2E:
    """Variables defined in earlier cells must survive into later cells."""

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    # --- basic cross-cell reference ---

    def test_int_persists_across_cells(self):
        self.kernel.execute_cell("x = 10")
        result = self.kernel.execute_cell("x * 3")
        assert result.success
        assert result.return_value == 30

    def test_float_persists(self):
        self.kernel.execute_cell("pi_approx = 3.14159")
        result = self.kernel.execute_cell("pi_approx * 2")
        assert result.success
        assert abs(result.return_value - 6.28318) < 1e-4

    def test_string_persists(self):
        self.kernel.execute_cell("greeting = 'hello'")
        result = self.kernel.execute_cell("greeting.upper()")
        assert result.success
        assert result.return_value == "HELLO"

    def test_list_persists(self):
        self.kernel.execute_cell("items = [1, 2, 3]")
        result = self.kernel.execute_cell("sum(items)")
        assert result.success
        assert result.return_value == 6

    def test_dict_persists(self):
        self.kernel.execute_cell("config = {'debug': True, 'version': 2}")
        result = self.kernel.execute_cell("config['version']")
        assert result.success
        assert result.return_value == 2

    def test_set_persists(self):
        self.kernel.execute_cell("unique = {1, 2, 3, 2, 1}")
        result = self.kernel.execute_cell("len(unique)")
        assert result.success
        assert result.return_value == 3

    def test_tuple_persists(self):
        self.kernel.execute_cell("coords = (10, 20)")
        result = self.kernel.execute_cell("coords[1]")
        assert result.success
        assert result.return_value == 20

    # --- mutation visible in next cell ---

    def test_list_mutation_visible_in_next_cell(self):
        self.kernel.execute_cell("nums = [1, 2, 3]")
        self.kernel.execute_cell("nums.append(4)")
        result = self.kernel.execute_cell("nums")
        assert result.success
        assert result.return_value == [1, 2, 3, 4]

    def test_dict_mutation_visible_in_next_cell(self):
        self.kernel.execute_cell("d = {'a': 1}")
        self.kernel.execute_cell("d['b'] = 2")
        result = self.kernel.execute_cell("d")
        assert result.success
        assert result.return_value == {"a": 1, "b": 2}

    # --- variable shadowing ---

    def test_variable_shadowing(self):
        self.kernel.execute_cell("x = 1")
        self.kernel.execute_cell("x = 999")
        assert self.kernel.get_variable("x") == 999

    def test_shadowing_with_different_type(self):
        self.kernel.execute_cell("val = 42")
        self.kernel.execute_cell("val = 'now a string'")
        assert self.kernel.get_variable("val") == "now a string"

    # --- accumulator pattern ---

    def test_accumulator_pattern(self):
        """Append to a list across 5 separate cells."""
        self.kernel.execute_cell("acc = []")
        for i in range(1, 6):
            self.kernel.execute_cell(f"acc.append({i})")
        result = self.kernel.execute_cell("acc")
        assert result.success
        assert result.return_value == [1, 2, 3, 4, 5]

    # --- 10+ sequential cells building on each other ---

    def test_sequential_chain_of_ten_cells(self):
        cells = [
            "a = 1",
            "b = a + 1",
            "c = b * 2",
            "d = c - 1",
            "e = d ** 2",
            "f = e // 3",
            "g = f + a",
            "h = g * b",
            "i = h - c",
            "j = i + d",
        ]
        for code in cells:
            r = self.kernel.execute_cell(code)
            assert r.success, f"Cell failed: {code!r} — {r.error}"

        # Verify the chain: a=1,b=2,c=4,d=3,e=9,f=3,g=4,h=8,i=4,j=7
        assert self.kernel.get_variable("a") == 1
        assert self.kernel.get_variable("b") == 2
        assert self.kernel.get_variable("c") == 4
        assert self.kernel.get_variable("d") == 3
        assert self.kernel.get_variable("e") == 9
        assert self.kernel.get_variable("f") == 3
        assert self.kernel.get_variable("g") == 4
        assert self.kernel.get_variable("h") == 8
        assert self.kernel.get_variable("i") == 4
        assert self.kernel.get_variable("j") == 7

    # --- define in cell 1, use in 2, modify in 3, verify in 4 ---

    def test_define_use_modify_verify(self):
        self.kernel.execute_cell("data = {'score': 0, 'name': 'Alice'}")
        self.kernel.execute_cell("score_copy = data['score']")
        self.kernel.execute_cell("data['score'] = score_copy + 100")
        result = self.kernel.execute_cell("data['score']")
        assert result.success
        assert result.return_value == 100


# ---------------------------------------------------------------------------
# 2. Import Persistence
# ---------------------------------------------------------------------------

class TestImportPersistenceE2E:
    """Imports in one cell must be available in subsequent cells."""

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def test_import_math_use_in_next_cell(self):
        self.kernel.execute_cell("import math")
        result = self.kernel.execute_cell("math.sqrt(16)")
        assert result.success
        assert result.return_value == 4.0

    def test_import_os_use_getcwd(self):
        self.kernel.execute_cell("import os")
        result = self.kernel.execute_cell("isinstance(os.getcwd(), str)")
        assert result.success
        assert result.return_value is True

    def test_import_sys_use_version(self):
        self.kernel.execute_cell("import sys")
        result = self.kernel.execute_cell("sys.version_info.major")
        assert result.success
        assert result.return_value >= 3

    def test_import_json_encode_decode(self):
        self.kernel.execute_cell("import json")
        self.kernel.execute_cell("raw = json.dumps({'key': 'value'})")
        result = self.kernel.execute_cell("json.loads(raw)['key']")
        assert result.success
        assert result.return_value == "value"

    def test_from_import_style(self):
        self.kernel.execute_cell("from math import sqrt, pi")
        result = self.kernel.execute_cell("sqrt(pi ** 2)")
        assert result.success
        assert abs(result.return_value - 3.14159) < 0.001

    def test_from_collections_import_defaultdict(self):
        self.kernel.execute_cell("from collections import defaultdict")
        self.kernel.execute_cell("dd = defaultdict(int)")
        self.kernel.execute_cell("dd['x'] += 5")
        result = self.kernel.execute_cell("dd['x']")
        assert result.success
        assert result.return_value == 5

    def test_from_collections_import_counter(self):
        self.kernel.execute_cell("from collections import Counter")
        self.kernel.execute_cell("c = Counter('aabbcc')")
        result = self.kernel.execute_cell("c['a']")
        assert result.success
        assert result.return_value == 2

    def test_multiple_imports_both_usable(self):
        self.kernel.execute_cell("import math")
        self.kernel.execute_cell("import os")
        r1 = self.kernel.execute_cell("math.floor(2.9)")
        r2 = self.kernel.execute_cell("os.path.sep")
        assert r1.success and r1.return_value == 2
        assert r2.success

    def test_import_collections_ordered_dict(self):
        self.kernel.execute_cell("from collections import OrderedDict")
        self.kernel.execute_cell("od = OrderedDict()")
        self.kernel.execute_cell("od['first'] = 1")
        self.kernel.execute_cell("od['second'] = 2")
        result = self.kernel.execute_cell("list(od.keys())")
        assert result.success
        assert result.return_value == ["first", "second"]

    def test_import_datetime_use_in_later_cell(self):
        self.kernel.execute_cell("from datetime import date")
        result = self.kernel.execute_cell("isinstance(date.today(), date)")
        assert result.success
        assert result.return_value is True

    def test_import_functools_reduce(self):
        self.kernel.execute_cell("from functools import reduce")
        self.kernel.execute_cell("nums = [1, 2, 3, 4, 5]")
        result = self.kernel.execute_cell("reduce(lambda a, b: a + b, nums)")
        assert result.success
        assert result.return_value == 15

    def test_import_itertools_chain(self):
        self.kernel.execute_cell("import itertools")
        self.kernel.execute_cell("a = [1, 2]")
        self.kernel.execute_cell("b = [3, 4]")
        result = self.kernel.execute_cell("list(itertools.chain(a, b))")
        assert result.success
        assert result.return_value == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# 3. Function and Class Persistence
# ---------------------------------------------------------------------------

class TestFunctionPersistenceE2E:
    """Functions and classes defined in one cell must work in later cells."""

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def test_function_defined_then_called(self):
        self.kernel.execute_cell("def double(n): return n * 2")
        result = self.kernel.execute_cell("double(7)")
        assert result.success
        assert result.return_value == 14

    def test_class_defined_instantiated_method_called(self):
        self.kernel.execute_cell(
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self.count = 0\n"
            "    def increment(self):\n"
            "        self.count += 1\n"
            "    def value(self):\n"
            "        return self.count\n"
        )
        self.kernel.execute_cell("c = Counter()")
        self.kernel.execute_cell("c.increment()")
        self.kernel.execute_cell("c.increment()")
        result = self.kernel.execute_cell("c.value()")
        assert result.success
        assert result.return_value == 2

    def test_helper_function_called_by_another_function(self):
        self.kernel.execute_cell("def square(x): return x * x")
        self.kernel.execute_cell(
            "def sum_of_squares(lst):\n"
            "    return sum(square(x) for x in lst)\n"
        )
        result = self.kernel.execute_cell("sum_of_squares([1, 2, 3, 4])")
        assert result.success
        assert result.return_value == 30

    def test_closure_captures_outer_variable(self):
        self.kernel.execute_cell("base = 10")
        self.kernel.execute_cell(
            "def add_base(x):\n"
            "    return x + base\n"
        )
        result = self.kernel.execute_cell("add_base(5)")
        assert result.success
        assert result.return_value == 15

    def test_decorator_defined_then_applied(self):
        self.kernel.execute_cell(
            "def shout(func):\n"
            "    def wrapper(*args, **kwargs):\n"
            "        return func(*args, **kwargs).upper()\n"
            "    return wrapper\n"
        )
        self.kernel.execute_cell(
            "@shout\n"
            "def greet(name):\n"
            "    return f'hello {name}'\n"
        )
        result = self.kernel.execute_cell("greet('world')")
        assert result.success
        assert result.return_value == "HELLO WORLD"

    def test_lambda_persists(self):
        self.kernel.execute_cell("triple = lambda x: x * 3")
        result = self.kernel.execute_cell("triple(6)")
        assert result.success
        assert result.return_value == 18

    def test_class_inheritance_across_cells(self):
        self.kernel.execute_cell(
            "class Animal:\n"
            "    def speak(self):\n"
            "        return 'generic sound'\n"
        )
        self.kernel.execute_cell(
            "class Dog(Animal):\n"
            "    def speak(self):\n"
            "        return 'woof'\n"
        )
        self.kernel.execute_cell("dog = Dog()")
        result = self.kernel.execute_cell("dog.speak()")
        assert result.success
        assert result.return_value == "woof"

    def test_function_with_default_arg_from_earlier_cell(self):
        self.kernel.execute_cell("default_val = 42")
        self.kernel.execute_cell(
            "def get_or_default(x=None):\n"
            "    return x if x is not None else default_val\n"
        )
        r1 = self.kernel.execute_cell("get_or_default()")
        r2 = self.kernel.execute_cell("get_or_default(99)")
        assert r1.success and r1.return_value == 42
        assert r2.success and r2.return_value == 99

    def test_recursive_function(self):
        self.kernel.execute_cell(
            "def fact(n):\n"
            "    return 1 if n <= 1 else n * fact(n - 1)\n"
        )
        result = self.kernel.execute_cell("fact(6)")
        assert result.success
        assert result.return_value == 720

    def test_generator_function_persists(self):
        self.kernel.execute_cell(
            "def count_up(n):\n"
            "    for i in range(n):\n"
            "        yield i\n"
        )
        result = self.kernel.execute_cell("list(count_up(4))")
        assert result.success
        assert result.return_value == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# 4. Complex Workflow
# ---------------------------------------------------------------------------

class TestComplexWorkflowE2E:
    """Multi-step workflows that span many cells."""

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def test_data_processing_pipeline(self):
        """Create -> filter -> transform -> aggregate across 5 cells."""
        self.kernel.execute_cell("raw = list(range(1, 11))")          # [1..10]
        self.kernel.execute_cell("evens = [x for x in raw if x % 2 == 0]")  # [2,4,6,8,10]
        self.kernel.execute_cell("doubled = [x * 2 for x in evens]")  # [4,8,12,16,20]
        self.kernel.execute_cell("total = sum(doubled)")
        result = self.kernel.execute_cell("total")
        assert result.success
        assert result.return_value == 60

    def test_class_hierarchy_across_cells(self):
        self.kernel.execute_cell(
            "class Shape:\n"
            "    def area(self): return 0\n"
        )
        self.kernel.execute_cell(
            "class Rectangle(Shape):\n"
            "    def __init__(self, w, h):\n"
            "        self.w, self.h = w, h\n"
            "    def area(self):\n"
            "        return self.w * self.h\n"
        )
        self.kernel.execute_cell(
            "class Square(Rectangle):\n"
            "    def __init__(self, side):\n"
            "        super().__init__(side, side)\n"
        )
        self.kernel.execute_cell("sq = Square(5)")
        result = self.kernel.execute_cell("sq.area()")
        assert result.success
        assert result.return_value == 25

    def test_fibonacci_step_by_step(self):
        self.kernel.execute_cell("fib_cache = {0: 0, 1: 1}")
        self.kernel.execute_cell(
            "def fib(n):\n"
            "    if n in fib_cache:\n"
            "        return fib_cache[n]\n"
            "    fib_cache[n] = fib(n-1) + fib(n-2)\n"
            "    return fib_cache[n]\n"
        )
        self.kernel.execute_cell("sequence = [fib(i) for i in range(8)]")
        result = self.kernel.execute_cell("sequence")
        assert result.success
        assert result.return_value == [0, 1, 1, 2, 3, 5, 8, 13]

    def test_counter_initialize_increment_verify(self):
        self.kernel.execute_cell("counter = 0")
        for _ in range(5):
            self.kernel.execute_cell("counter += 1")
        result = self.kernel.execute_cell("counter")
        assert result.success
        assert result.return_value == 5

    def test_error_recovery_does_not_corrupt_state(self):
        """Variables set before an error must remain accessible after it."""
        self.kernel.execute_cell("safe_var = 'still here'")
        # This cell fails
        error_result = self.kernel.execute_cell("raise ValueError('deliberate')")
        assert not error_result.success
        # safe_var must still be intact
        result = self.kernel.execute_cell("safe_var")
        assert result.success
        assert result.return_value == "still here"

    def test_string_building_pipeline(self):
        self.kernel.execute_cell("words = ['the', 'quick', 'brown', 'fox']")
        self.kernel.execute_cell("capitalized = [w.capitalize() for w in words]")
        self.kernel.execute_cell("sentence = ' '.join(capitalized)")
        result = self.kernel.execute_cell("sentence")
        assert result.success
        assert result.return_value == "The Quick Brown Fox"

    def test_nested_data_structure_workflow(self):
        self.kernel.execute_cell(
            "students = [\n"
            "    {'name': 'Alice', 'score': 90},\n"
            "    {'name': 'Bob', 'score': 75},\n"
            "    {'name': 'Charlie', 'score': 85},\n"
            "]\n"
        )
        self.kernel.execute_cell("scores = [s['score'] for s in students]")
        self.kernel.execute_cell("average = sum(scores) / len(scores)")
        result = self.kernel.execute_cell("average")
        assert result.success
        assert abs(result.return_value - 83.33) < 0.01

    def test_stateful_object_across_many_cells(self):
        self.kernel.execute_cell(
            "class Stack:\n"
            "    def __init__(self):\n"
            "        self._data = []\n"
            "    def push(self, v): self._data.append(v)\n"
            "    def pop(self): return self._data.pop()\n"
            "    def peek(self): return self._data[-1]\n"
            "    def size(self): return len(self._data)\n"
        )
        self.kernel.execute_cell("stack = Stack()")
        self.kernel.execute_cell("stack.push(10)")
        self.kernel.execute_cell("stack.push(20)")
        self.kernel.execute_cell("stack.push(30)")
        self.kernel.execute_cell("stack.pop()")
        result = self.kernel.execute_cell("stack.peek()")
        assert result.success
        assert result.return_value == 20
        result2 = self.kernel.execute_cell("stack.size()")
        assert result2.success
        assert result2.return_value == 2


# ---------------------------------------------------------------------------
# 5. Output Capture
# ---------------------------------------------------------------------------

class TestOutputCaptureE2E:
    """Comprehensive tests for stdout, stderr, return value, and error output."""

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def test_print_captured_as_stdout(self):
        result = self.kernel.execute_cell('print("hello output")')
        assert result.success
        text = _stdout_text(result)
        assert "hello output" in text

    def test_multiple_prints_all_captured(self):
        result = self.kernel.execute_cell(
            'print("line one")\n'
            'print("line two")\n'
            'print("line three")\n'
        )
        assert result.success
        text = _stdout_text(result)
        assert "line one" in text
        assert "line two" in text
        assert "line three" in text

    def test_return_value_captured(self):
        result = self.kernel.execute_cell("6 * 7")
        assert result.success
        assert result.return_value == 42
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0
        assert "42" in exec_results[0]["data"]["text/plain"]

    def test_assignment_produces_no_output(self):
        result = self.kernel.execute_cell("x = 100")
        assert result.success
        assert result.return_value is None
        assert len(_execute_result_outputs(result)) == 0
        assert len(_stdout_text(result)) == 0

    def test_error_output_captures_ename(self):
        result = self.kernel.execute_cell("1 / 0")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "ZeroDivisionError"

    def test_mixed_print_and_return_value(self):
        result = self.kernel.execute_cell(
            'print("side effect")\n'
            '2 + 2\n'
        )
        assert result.success
        assert "side effect" in _stdout_text(result)
        assert result.return_value == 4

    def test_print_does_not_produce_execute_result(self):
        result = self.kernel.execute_cell('print("just printing")')
        assert result.success
        # print returns None, so no execute_result output
        assert len(_execute_result_outputs(result)) == 0

    def test_execution_count_in_execute_result_output(self):
        self.kernel.execute_cell("1")  # count = 1
        result = self.kernel.execute_cell("2")  # count = 2
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0
        assert exec_results[0]["execution_count"] == 2

    def test_string_return_value(self):
        result = self.kernel.execute_cell("'hello world'")
        assert result.success
        assert result.return_value == "hello world"

    def test_list_return_value(self):
        result = self.kernel.execute_cell("[1, 2, 3]")
        assert result.success
        assert result.return_value == [1, 2, 3]

    def test_none_return_for_none_expression(self):
        result = self.kernel.execute_cell("None")
        assert result.success
        # IPython does not display None as an execute_result
        assert result.return_value is None

    def test_multiline_print_with_loop(self):
        result = self.kernel.execute_cell(
            "for i in range(3):\n"
            "    print(i)\n"
        )
        assert result.success
        text = _stdout_text(result)
        assert "0" in text
        assert "1" in text
        assert "2" in text


# ---------------------------------------------------------------------------
# 6. Display Objects (IPython rich output)
# ---------------------------------------------------------------------------

class TestDisplayObjectsE2E:
    """Full-pipeline tests for IPython display objects (HTML, Markdown, etc.).

    The kernel must extract MIME-type data dicts from display objects rather
    than falling back to str(obj) which produces unhelpful repr strings.
    """

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def test_html_object_produces_html_mime_type(self):
        """Full pipeline: HTML() → execute_result with text/html data."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\nHTML("<h1>Hello</h1>")'
        )
        assert result.success
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0, "No execute_result output found"
        data = exec_results[0]["data"]
        assert "text/html" in data, (
            f"Expected text/html in data, got: {list(data.keys())}"
        )
        assert "<h1>Hello</h1>" in data["text/html"]

    def test_html_content_is_actual_html_not_repr(self):
        """The data dict must contain actual HTML, not the object repr."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\n'
            'HTML("<p>Real content</p>")'
        )
        assert result.success
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0
        data = exec_results[0]["data"]
        # Check all values — none should be the repr string
        for mime, content in data.items():
            assert "<IPython.core.display.HTML object>" not in str(content), (
                f"MIME type {mime!r} contains repr string instead of real content"
            )
        # Actual HTML must appear somewhere
        html_found = any("<p>Real content</p>" in str(v) for v in data.values())
        assert html_found, f"HTML content not found in data dict: {data}"

    def test_mixed_print_and_html_display(self):
        """Cell with print() and HTML() should produce both stream and execute_result."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\n'
            'print("printed line")\n'
            'HTML("<em>italic</em>")'
        )
        assert result.success
        # stdout must be captured
        assert "printed line" in _stdout_text(result)
        # execute_result must have text/html
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0, "Expected execute_result for HTML()"
        data = exec_results[0]["data"]
        assert "text/html" in data, (
            f"Expected text/html key, got: {list(data.keys())}"
        )

    def test_multiple_mime_types_in_data_dict(self):
        """The data dict for a display object should carry multiple MIME types."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\nHTML("<div>multi</div>")'
        )
        assert result.success
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0
        data = exec_results[0]["data"]
        # Must have at least text/html AND text/plain
        assert "text/html" in data, "Missing text/html"
        assert "text/plain" in data, "Missing text/plain fallback"
        # text/plain must not be the ugly repr
        assert "<IPython.core.display.HTML object>" not in data["text/plain"]

    def test_display_object_with_variable_persistence(self):
        """An HTML object stored in a variable in cell 1 can be returned in cell 2."""
        self.kernel.execute_cell(
            'from IPython.display import HTML\n'
            'banner = HTML("<h2>Banner</h2>")'
        )
        result = self.kernel.execute_cell("banner")
        assert result.success
        exec_results = _execute_result_outputs(result)
        assert len(exec_results) > 0, "Expected execute_result when returning stored HTML"
        data = exec_results[0]["data"]
        assert "text/html" in data, (
            f"Expected text/html for stored HTML variable, got: {list(data.keys())}"
        )
        assert "<h2>Banner</h2>" in data["text/html"]


# ---------------------------------------------------------------------------
# 7. Error Handling
# ---------------------------------------------------------------------------

class TestErrorHandlingE2E:
    """Error scenarios: errors reported correctly and state is not corrupted."""

    def setup_method(self):
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def test_syntax_error_reported(self):
        # IPython handles SyntaxError specially: it prints the error to stdout
        # and returns success=True (no error_in_exec). We verify the error
        # text is present in the output rather than checking result.success.
        result = self.kernel.execute_cell("def bad(:\n    pass\n")
        text = _stdout_text(result)
        assert "SyntaxError" in text

    def test_name_error_reported(self):
        result = self.kernel.execute_cell("undefined_variable_xyz")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "NameError"

    def test_type_error_reported(self):
        result = self.kernel.execute_cell("1 + 'string'")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "TypeError"

    def test_zero_division_error_reported(self):
        result = self.kernel.execute_cell("10 / 0")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "ZeroDivisionError"

    def test_import_error_reported(self):
        result = self.kernel.execute_cell("import module_that_does_not_exist_xyz")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] in ("ModuleNotFoundError", "ImportError")

    def test_state_preserved_after_name_error(self):
        self.kernel.execute_cell("good_var = 123")
        bad = self.kernel.execute_cell("bad_var + 1")  # NameError
        assert not bad.success
        # good_var must still be accessible
        assert self.kernel.get_variable("good_var") == 123

    def test_state_preserved_after_type_error(self):
        self.kernel.execute_cell("x = [1, 2, 3]")
        self.kernel.execute_cell("x + 'oops'")  # TypeError — ignored
        result = self.kernel.execute_cell("x")
        assert result.success
        assert result.return_value == [1, 2, 3]

    def test_multiple_errors_do_not_corrupt_kernel(self):
        self.kernel.execute_cell("stable = 'safe'")
        self.kernel.execute_cell("1 / 0")
        self.kernel.execute_cell("undefined_name")
        self.kernel.execute_cell("1 + 'bad'")
        result = self.kernel.execute_cell("stable")
        assert result.success
        assert result.return_value == "safe"

    def test_error_result_success_flag_false(self):
        result = self.kernel.execute_cell("raise RuntimeError('test')")
        assert result.success is False
        assert result.error is not None

    def test_error_followed_by_successful_cell(self):
        err_result = self.kernel.execute_cell("1 / 0")
        assert not err_result.success
        ok_result = self.kernel.execute_cell("2 + 2")
        assert ok_result.success
        assert ok_result.return_value == 4

    def test_execution_count_increments_even_on_error(self):
        """Execution count should increment regardless of success/failure."""
        r1 = self.kernel.execute_cell("x = 1")
        r2 = self.kernel.execute_cell("1 / 0")
        r3 = self.kernel.execute_cell("x")
        assert r1.execution_count == 1
        assert r2.execution_count == 2
        assert r3.execution_count == 3

    def test_attribute_error_reported(self):
        self.kernel.execute_cell("n = 42")
        result = self.kernel.execute_cell("n.nonexistent_attr")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "AttributeError"

    def test_index_error_reported(self):
        self.kernel.execute_cell("lst = [1, 2, 3]")
        result = self.kernel.execute_cell("lst[100]")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "IndexError"

    def test_key_error_reported(self):
        self.kernel.execute_cell("d = {'a': 1}")
        result = self.kernel.execute_cell("d['missing_key']")
        assert not result.success
        errs = _error_outputs(result)
        assert len(errs) > 0
        assert errs[0]["ename"] == "KeyError"
