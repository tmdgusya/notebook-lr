"""
Comprehensive E2E tests for complex realistic notebook scenarios.

Each test class simulates a real-world notebook workflow using only
Python stdlib (no numpy, pandas, matplotlib, sklearn).
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from notebook_lr.kernel import NotebookKernel, ExecutionResult
from notebook_lr.notebook import Notebook, Cell, CellType
from notebook_lr.session import SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_stdout(result: ExecutionResult) -> str:
    """Return concatenated stdout text from an ExecutionResult."""
    parts = [
        o.get("text", "")
        for o in result.outputs
        if o.get("type") == "stream" and o.get("name") == "stdout"
    ]
    return "".join(parts)


def assert_success(result: ExecutionResult, msg: str = ""):
    """Assert that a cell executed successfully."""
    assert result.success, (
        f"Cell failed{': ' + msg if msg else ''}. Error: {result.error}"
    )


# ---------------------------------------------------------------------------
# 1. Data Analysis Scenario
# ---------------------------------------------------------------------------

class TestDataAnalysisScenarioE2E:
    """Simulate a data analysis notebook using stdlib only."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    # Cell 1 – create dataset
    CELL1 = """
dataset = [
    {"name": "Alice",   "age": 30, "score": 88.5, "city": "New York"},
    {"name": "Bob",     "age": 22, "score": 74.0, "city": "Chicago"},
    {"name": "Carol",   "age": 35, "score": 92.3, "city": "New York"},
    {"name": "David",   "age": 28, "score": 65.1, "city": "Chicago"},
    {"name": "Eva",     "age": 24, "score": 81.0, "city": "Boston"},
    {"name": "Frank",   "age": 40, "score": 55.9, "city": "New York"},
    {"name": "Grace",   "age": 19, "score": 97.8, "city": "Boston"},
    {"name": "Hank",    "age": 33, "score": 70.4, "city": "Chicago"},
    {"name": "Iris",    "age": 27, "score": 83.6, "city": "Boston"},
    {"name": "Jake",    "age": 45, "score": 61.2, "city": "New York"},
    {"name": "Karen",   "age": 31, "score": 78.9, "city": "Chicago"},
    {"name": "Leo",     "age": 26, "score": 90.0, "city": "Boston"},
]
"""

    # Cell 2 – statistics
    CELL2 = """
import statistics

scores = [r["score"] for r in dataset]
ages   = [r["age"]   for r in dataset]

score_mean   = statistics.mean(scores)
score_median = statistics.median(scores)
score_stdev  = statistics.stdev(scores)
age_mean     = statistics.mean(ages)
"""

    # Cell 3 – filter
    CELL3 = """
over_25 = [r for r in dataset if r["age"] > 25]
"""

    # Cell 4 – group by city
    CELL4 = """
from collections import defaultdict

by_city = defaultdict(list)
for r in dataset:
    by_city[r["city"]].append(r)
city_names = sorted(by_city.keys())
"""

    # Cell 5 – top-N by score
    CELL5 = """
top3 = sorted(dataset, key=lambda r: r["score"], reverse=True)[:3]
top3_names = [r["name"] for r in top3]
"""

    # Cell 6 – summary string
    CELL6 = """
summary = (
    f"Dataset: {len(dataset)} records\\n"
    f"Score mean={score_mean:.2f}, median={score_median:.2f}, "
    f"stdev={score_stdev:.2f}\\n"
    f"Over-25 filter: {len(over_25)} records\\n"
    f"Cities: {', '.join(city_names)}\\n"
    f"Top-3 by score: {', '.join(top3_names)}"
)
print(summary)
"""

    def test_cell1_dataset_created(self):
        r = self.kernel.execute_cell(self.CELL1)
        assert_success(r, "cell 1")
        dataset = self.kernel.get_variable("dataset")
        assert isinstance(dataset, list)
        assert len(dataset) == 12
        assert dataset[0]["name"] == "Alice"

    def test_cell2_statistics(self):
        self.kernel.execute_cell(self.CELL1)
        r = self.kernel.execute_cell(self.CELL2)
        assert_success(r, "cell 2")

        import statistics as _stats
        scores = [rec["score"] for rec in self.kernel.get_variable("dataset")]
        expected_mean = _stats.mean(scores)
        expected_stdev = _stats.stdev(scores)

        assert abs(self.kernel.get_variable("score_mean") - expected_mean) < 1e-9
        assert abs(self.kernel.get_variable("score_stdev") - expected_stdev) < 1e-9

    def test_cell3_filter(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        r = self.kernel.execute_cell(self.CELL3)
        assert_success(r, "cell 3")

        over_25 = self.kernel.get_variable("over_25")
        assert isinstance(over_25, list)
        assert all(rec["age"] > 25 for rec in over_25)
        # Verify count manually
        dataset = self.kernel.get_variable("dataset")
        assert len(over_25) == sum(1 for rec in dataset if rec["age"] > 25)

    def test_cell4_group_by_city(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        r = self.kernel.execute_cell(self.CELL4)
        assert_success(r, "cell 4")

        by_city = self.kernel.get_variable("by_city")
        city_names = self.kernel.get_variable("city_names")
        assert set(city_names) == {"Boston", "Chicago", "New York"}
        assert all(isinstance(v, list) for v in by_city.values())
        # All records accounted for
        total = sum(len(v) for v in by_city.values())
        assert total == 12

    def test_cell5_top_n(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        self.kernel.execute_cell(self.CELL4)
        r = self.kernel.execute_cell(self.CELL5)
        assert_success(r, "cell 5")

        top3 = self.kernel.get_variable("top3")
        top3_names = self.kernel.get_variable("top3_names")
        assert len(top3) == 3
        assert len(top3_names) == 3
        # Scores should be descending
        assert top3[0]["score"] >= top3[1]["score"] >= top3[2]["score"]
        # Grace has 97.8 – highest score in dataset
        assert "Grace" in top3_names

    def test_cell6_summary_output(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        self.kernel.execute_cell(self.CELL4)
        self.kernel.execute_cell(self.CELL5)
        r = self.kernel.execute_cell(self.CELL6)
        assert_success(r, "cell 6")

        out = get_stdout(r)
        assert "Dataset: 12" in out
        assert "Score mean=" in out
        assert "Cities:" in out
        assert "Top-3 by score:" in out

    def test_all_cells_variables_persist(self):
        """Run all cells and verify every variable is accessible."""
        for cell in [
            self.CELL1, self.CELL2, self.CELL3,
            self.CELL4, self.CELL5, self.CELL6,
        ]:
            r = self.kernel.execute_cell(cell)
            assert_success(r)

        ns = self.kernel.get_namespace()
        for name in [
            "dataset", "scores", "ages", "score_mean", "score_median",
            "score_stdev", "age_mean", "over_25", "by_city", "city_names",
            "top3", "top3_names", "summary",
        ]:
            assert name in ns, f"Variable '{name}' missing from namespace"


# ---------------------------------------------------------------------------
# 2. Math Computation Scenario
# ---------------------------------------------------------------------------

class TestMathComputationScenarioE2E:
    """Math-heavy notebook with factorial, fibonacci, primes, pi approximation."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    CELL1 = """
import math

E  = math.e
PI = math.pi
TAU = math.tau
"""

    CELL2 = """
def factorial(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
"""

    CELL3 = """
def fibonacci(n):
    if n <= 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
"""

    CELL4 = """
def is_prime(n):
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True
"""

    CELL5 = """
primes_to_100 = [n for n in range(2, 101) if is_prime(n)]
"""

    CELL6 = """
def leibniz_pi(terms=100_000):
    total = 0.0
    for k in range(terms):
        total += ((-1) ** k) / (2 * k + 1)
    return 4 * total

pi_approx = leibniz_pi()
"""

    CELL7 = """
assert factorial(10) == 3628800, f"factorial(10) = {factorial(10)}"
assert factorial(0) == 1,        f"factorial(0) = {factorial(0)}"
assert fibonacci(10) == 55,      f"fibonacci(10) = {fibonacci(10)}"
assert fibonacci(0) == 0
assert fibonacci(1) == 1
assert len(primes_to_100) == 25, f"prime count = {len(primes_to_100)}"
assert abs(pi_approx - math.pi) < 0.001, f"pi_approx = {pi_approx}"
print("All math assertions passed")
"""

    def _run_all(self):
        for cell in [
            self.CELL1, self.CELL2, self.CELL3,
            self.CELL4, self.CELL5, self.CELL6,
        ]:
            assert_success(self.kernel.execute_cell(cell))

    def test_constants_defined(self):
        r = self.kernel.execute_cell(self.CELL1)
        assert_success(r, "cell 1")
        import math as _math
        assert abs(self.kernel.get_variable("PI") - _math.pi) < 1e-12

    def test_factorial(self):
        self.kernel.execute_cell(self.CELL1)
        r = self.kernel.execute_cell(self.CELL2)
        assert_success(r, "cell 2")
        fact = self.kernel.get_variable("factorial")
        assert fact(10) == 3628800
        assert fact(0) == 1
        assert fact(5) == 120

    def test_fibonacci(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        r = self.kernel.execute_cell(self.CELL3)
        assert_success(r, "cell 3")
        fib = self.kernel.get_variable("fibonacci")
        assert fib(0) == 0
        assert fib(1) == 1
        assert fib(10) == 55
        assert fib(20) == 6765

    def test_is_prime(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        r = self.kernel.execute_cell(self.CELL4)
        assert_success(r, "cell 4")
        is_prime = self.kernel.get_variable("is_prime")
        assert is_prime(2) is True
        assert is_prime(3) is True
        assert is_prime(4) is False
        assert is_prime(97) is True
        assert is_prime(100) is False

    def test_primes_to_100(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        self.kernel.execute_cell(self.CELL4)
        r = self.kernel.execute_cell(self.CELL5)
        assert_success(r, "cell 5")
        primes = self.kernel.get_variable("primes_to_100")
        assert len(primes) == 25
        assert primes[0] == 2
        assert primes[-1] == 97

    def test_pi_approximation(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        self.kernel.execute_cell(self.CELL4)
        self.kernel.execute_cell(self.CELL5)
        r = self.kernel.execute_cell(self.CELL6)
        assert_success(r, "cell 6")
        import math as _math
        pi_approx = self.kernel.get_variable("pi_approx")
        assert abs(pi_approx - _math.pi) < 0.001

    def test_cell7_assertions_pass(self):
        self._run_all()
        r = self.kernel.execute_cell(self.CELL7)
        assert_success(r, "cell 7 assertions")
        assert "All math assertions passed" in get_stdout(r)


# ---------------------------------------------------------------------------
# 3. OOP Scenario
# ---------------------------------------------------------------------------

class TestOOPScenarioE2E:
    """Object-oriented programming notebook."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    CELL1 = """
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return f"{self.name} makes a sound"

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r})"
"""

    CELL2 = """
class Dog(Animal):
    def speak(self):
        return f"{self.name} says: Woof!"

class Cat(Animal):
    def speak(self):
        return f"{self.name} says: Meow!"
"""

    CELL3 = """
animals = [Dog("Rex"), Cat("Whiskers"), Dog("Buddy"), Cat("Luna")]
sounds  = [a.speak() for a in animals]
"""

    CELL4 = """
class SerializeMixin:
    def to_dict(self):
        return {"type": self.__class__.__name__, "name": self.name}

class DogV2(SerializeMixin, Dog):
    pass

class CatV2(SerializeMixin, Cat):
    pass

d2 = DogV2("Rex2")
c2 = CatV2("Luna2")
"""

    CELL5 = """
class AnimalCollection:
    def __init__(self):
        self._animals = []

    def add(self, animal):
        self._animals.append(animal)
        return self

    def count(self):
        return len(self._animals)

    def all_sounds(self):
        return [a.speak() for a in self._animals]

    def by_type(self, animal_type):
        return [a for a in self._animals if isinstance(a, animal_type)]

    def serialize(self):
        result = []
        for a in self._animals:
            if hasattr(a, "to_dict"):
                result.append(a.to_dict())
            else:
                result.append({"type": type(a).__name__, "name": a.name})
        return result

collection = AnimalCollection()
for a in animals:
    collection.add(a)
collection.add(d2).add(c2)
"""

    CELL6 = """
all_sounds = collection.all_sounds()
dogs = collection.by_type(Dog)
cats = collection.by_type(Cat)
serialized = collection.serialize()
total_count = collection.count()
"""

    def _run_up_to(self, n):
        cells = [
            self.CELL1, self.CELL2, self.CELL3,
            self.CELL4, self.CELL5, self.CELL6,
        ]
        for cell in cells[:n]:
            r = self.kernel.execute_cell(cell)
            assert_success(r)

    def test_cell1_base_class(self):
        r = self.kernel.execute_cell(self.CELL1)
        assert_success(r, "cell 1")
        Animal = self.kernel.get_variable("Animal")
        a = Animal("Creature")
        assert a.speak() == "Creature makes a sound"

    def test_cell2_subclasses(self):
        self._run_up_to(2)
        Dog = self.kernel.get_variable("Dog")
        Cat = self.kernel.get_variable("Cat")
        assert Dog("Fido").speak() == "Fido says: Woof!"
        assert Cat("Kitty").speak() == "Kitty says: Meow!"

    def test_cell3_polymorphism(self):
        self._run_up_to(3)
        sounds = self.kernel.get_variable("sounds")
        assert len(sounds) == 4
        assert any("Woof" in s for s in sounds)
        assert any("Meow" in s for s in sounds)

    def test_cell4_mixin(self):
        self._run_up_to(4)
        d2 = self.kernel.get_variable("d2")
        c2 = self.kernel.get_variable("c2")
        assert d2.speak() == "Rex2 says: Woof!"
        assert c2.to_dict() == {"type": "CatV2", "name": "Luna2"}

    def test_cell5_collection_manager(self):
        self._run_up_to(5)
        collection = self.kernel.get_variable("collection")
        assert collection.count() == 6  # 4 original + d2 + c2

    def test_cell6_full_system(self):
        self._run_up_to(6)
        Dog = self.kernel.get_variable("Dog")
        Cat = self.kernel.get_variable("Cat")
        all_sounds = self.kernel.get_variable("all_sounds")
        dogs = self.kernel.get_variable("dogs")
        cats = self.kernel.get_variable("cats")
        serialized = self.kernel.get_variable("serialized")
        total_count = self.kernel.get_variable("total_count")

        assert total_count == 6
        assert len(all_sounds) == 6
        assert len(dogs) == 3   # Rex, Buddy, Rex2
        assert len(cats) == 3   # Whiskers, Luna, Luna2
        assert len(serialized) == 6
        # Every serialized entry has type and name
        for entry in serialized:
            assert "type" in entry
            assert "name" in entry


# ---------------------------------------------------------------------------
# 4. Iterative Refinement Scenario
# ---------------------------------------------------------------------------

class TestIterativeRefinementE2E:
    """Iterative development: redefine functions across cells."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    CELL1 = """
def smart_sort(items):
    \"\"\"Initial version – basic sort.\"\"\"
    return sorted(items)
"""

    CELL2 = """
# Test basic case
result_basic = smart_sort([3, 1, 4, 1, 5, 9])
assert result_basic == [1, 1, 3, 4, 5, 9], f"Got {result_basic}"
print("Basic sort works:", result_basic)
"""

    CELL3 = """
def smart_sort(items, key=None, reverse=False, default=None):
    \"\"\"Improved version – handles None, custom key, reverse.\"\"\"
    if items is None:
        return [] if default is None else default
    cleaned = [x for x in items if x is not None]
    return sorted(cleaned, key=key, reverse=reverse)
"""

    CELL4 = """
# Test edge cases with the improved version
result_none_list  = smart_sort(None)
result_with_nones = smart_sort([3, None, 1, None, 4])
result_reversed   = smart_sort([3, 1, 4], reverse=True)
result_strings    = smart_sort(["banana", "apple", "cherry"])

assert result_none_list  == []
assert result_with_nones == [1, 3, 4]
assert result_reversed   == [4, 3, 1]
assert result_strings    == ["apple", "banana", "cherry"]
print("Edge cases passed")
"""

    CELL5 = """
def sort_records(records, field, reverse=False):
    \"\"\"Wrapper that sorts dicts by a given field.\"\"\"
    return smart_sort(records, key=lambda r: r.get(field, 0), reverse=reverse)
"""

    CELL6 = """
people = [
    {"name": "Zara",  "age": 25},
    {"name": "Alice", "age": 30},
    {"name": "Bob",   "age": 20},
]
by_age   = sort_records(people, "age")
by_name  = sort_records(people, "name")
by_age_r = sort_records(people, "age", reverse=True)

assert by_age[0]["name"] == "Bob"
assert by_name[0]["name"] == "Alice"
assert by_age_r[0]["name"] == "Alice"
print("Integration test passed")
"""

    def test_cell1_initial_sort(self):
        r = self.kernel.execute_cell(self.CELL1)
        assert_success(r, "cell 1")
        smart_sort = self.kernel.get_variable("smart_sort")
        assert smart_sort([3, 1, 2]) == [1, 2, 3]

    def test_cell2_basic_test(self):
        self.kernel.execute_cell(self.CELL1)
        r = self.kernel.execute_cell(self.CELL2)
        assert_success(r, "cell 2")
        assert "Basic sort works" in get_stdout(r)

    def test_cell3_overwrite_definition(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        r = self.kernel.execute_cell(self.CELL3)
        assert_success(r, "cell 3")
        # The function should now accept keyword args
        smart_sort = self.kernel.get_variable("smart_sort")
        assert smart_sort([3, None, 1]) == [1, 3]

    def test_cell4_edge_cases(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        r = self.kernel.execute_cell(self.CELL4)
        assert_success(r, "cell 4")
        assert "Edge cases passed" in get_stdout(r)

    def test_cell5_wrapper(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        self.kernel.execute_cell(self.CELL3)
        self.kernel.execute_cell(self.CELL4)
        r = self.kernel.execute_cell(self.CELL5)
        assert_success(r, "cell 5")
        sort_records = self.kernel.get_variable("sort_records")
        data = [{"x": 3}, {"x": 1}, {"x": 2}]
        assert sort_records(data, "x")[0]["x"] == 1

    def test_cell6_integration(self):
        for cell in [
            self.CELL1, self.CELL2, self.CELL3,
            self.CELL4, self.CELL5,
        ]:
            assert_success(self.kernel.execute_cell(cell))
        r = self.kernel.execute_cell(self.CELL6)
        assert_success(r, "cell 6")
        assert "Integration test passed" in get_stdout(r)

    def test_redefinition_overwrites(self):
        """Verify that CELL3 properly overwrites CELL1's definition."""
        self.kernel.execute_cell(self.CELL1)
        # Before redefinition, None input raises TypeError
        r_before = self.kernel.execute_cell("smart_sort(None)")
        assert not r_before.success

        self.kernel.execute_cell(self.CELL3)
        # After redefinition, None returns []
        r_after = self.kernel.execute_cell("smart_sort(None)")
        assert_success(r_after)
        assert r_after.return_value == []


# ---------------------------------------------------------------------------
# 5. File / Text Processing Scenario
# ---------------------------------------------------------------------------

class TestFileProcessingScenarioE2E:
    """Text parsing, regex, word frequencies, transformation."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    CELL1 = (
        'text_data = """\\n'
        'Alice sent an email to bob@example.com on 2024-01-15.\\n'
        'Visit https://www.example.com for more info.\\n'
        'Bob replied to alice@company.org at https://company.org/path?q=1.\\n'
        'The meeting is on 2024-02-20 at 10:00 AM.\\n'
        'Contact support@helpdesk.io or visit http://help.io.\\n'
        'Random numbers: 42, 3.14, 100, 7.\\n'
        '"""'
    )

    CELL2 = r"""
import re

# Extract dates (YYYY-MM-DD)
dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text_data)

# Extract emails
emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text_data)

# Extract URLs
urls = re.findall(r'https?://[^\s,]+', text_data)

# Extract numbers
numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text_data)
"""

    CELL3 = r"""
from collections import Counter

# Tokenise to words, lowercase, strip punctuation
words = re.findall(r'[a-zA-Z]+', text_data.lower())
word_freq = Counter(words)
top5_words = word_freq.most_common(5)
"""

    CELL4 = r"""
# Check for patterns
has_emails = len(emails) > 0
has_urls   = len(urls) > 0
has_dates  = len(dates) > 0

unique_domains = set()
for email in emails:
    domain = email.split("@")[1]
    unique_domains.add(domain)
"""

    CELL5 = r"""
# Transform: uppercase names that appear before "sent" or "replied"
lines = text_data.strip().split("\n")
transformed = []
for line in lines:
    line_up = re.sub(
        r'^([A-Z][a-z]+)',
        lambda m: m.group(1).upper(),
        line,
    )
    transformed.append(line_up.strip())
"""

    CELL6 = r"""
# Aggregate results
aggregate = {
    "total_words":    len(words),
    "unique_words":   len(word_freq),
    "emails_found":   len(emails),
    "urls_found":     len(urls),
    "dates_found":    len(dates),
    "unique_domains": sorted(unique_domains),
    "top5_words":     top5_words,
}
print(f"Words: {aggregate['total_words']}, "
      f"Emails: {aggregate['emails_found']}, "
      f"URLs: {aggregate['urls_found']}, "
      f"Dates: {aggregate['dates_found']}")
"""

    def _run_up_to(self, n):
        cells = [
            self.CELL1, self.CELL2, self.CELL3,
            self.CELL4, self.CELL5, self.CELL6,
        ]
        for cell in cells[:n]:
            r = self.kernel.execute_cell(cell)
            assert_success(r)

    def test_cell1_text_data(self):
        r = self.kernel.execute_cell(self.CELL1)
        assert_success(r, "cell 1")
        text = self.kernel.get_variable("text_data")
        assert "bob@example.com" in text
        assert "https://" in text

    def test_cell2_regex_extractions(self):
        self._run_up_to(2)
        emails = self.kernel.get_variable("emails")
        urls = self.kernel.get_variable("urls")
        dates = self.kernel.get_variable("dates")

        assert len(emails) >= 3
        assert "bob@example.com" in emails
        assert len(urls) >= 2
        assert len(dates) >= 2
        assert "2024-01-15" in dates

    def test_cell3_word_frequencies(self):
        self._run_up_to(3)
        word_freq = self.kernel.get_variable("word_freq")
        top5 = self.kernel.get_variable("top5_words")
        assert len(top5) == 5
        # "at" or "to" should be among high-freq words
        assert sum(1 for w, _ in top5 if w in {"at", "to", "or", "on"}) >= 1

    def test_cell4_pattern_checks(self):
        self._run_up_to(4)
        assert self.kernel.get_variable("has_emails") is True
        assert self.kernel.get_variable("has_urls") is True
        assert self.kernel.get_variable("has_dates") is True
        domains = self.kernel.get_variable("unique_domains")
        assert len(domains) >= 3

    def test_cell5_transform(self):
        self._run_up_to(5)
        transformed = self.kernel.get_variable("transformed")
        assert isinstance(transformed, list)
        assert len(transformed) > 0
        # First word of first line should be uppercased
        assert transformed[0].startswith("ALICE")

    def test_cell6_aggregate(self):
        self._run_up_to(6)
        agg = self.kernel.get_variable("aggregate")
        assert agg["emails_found"] >= 3
        assert agg["urls_found"] >= 2
        assert agg["dates_found"] >= 2
        assert agg["total_words"] > 20


# ---------------------------------------------------------------------------
# 6. Error Recovery Scenario
# ---------------------------------------------------------------------------

class TestErrorRecoveryScenarioE2E:
    """Errors in a cell do not corrupt the kernel state."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    CELL1 = """
base_value = 100
multiplier = 5
safe_result = base_value * multiplier

def compute(x):
    return x ** 2 + base_value

items = list(range(1, 11))
"""

    CELL2_BAD = """
# This will fail: division by zero
zero = 0
bad_result = base_value / zero
"""

    CELL3_CHECK = """
# State from cell 1 must still be intact
assert base_value == 100,      f"base_value corrupted: {base_value}"
assert multiplier == 5,        f"multiplier corrupted: {multiplier}"
assert safe_result == 500,     f"safe_result corrupted: {safe_result}"
assert compute(4) == 116,      f"compute(4) = {compute(4)}"
assert items == list(range(1, 11))
print("State intact after error")
"""

    CELL4_FIX = """
denominator = 10
fixed_result = base_value / denominator
"""

    CELL5_CHAIN = """
# Use both cell-1 variables and cell-4 fix
chained = [compute(x) + fixed_result for x in items]
chained_sum = sum(chained)
expected_sum = sum((x**2 + base_value) + fixed_result for x in range(1, 11))
assert abs(chained_sum - expected_sum) < 1e-9
print(f"Chained sum: {chained_sum}")
"""

    def test_cell2_fails(self):
        self.kernel.execute_cell(self.CELL1)
        r = self.kernel.execute_cell(self.CELL2_BAD)
        assert not r.success
        assert r.error is not None

    def test_cell1_state_survives_error(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2_BAD)  # error
        r = self.kernel.execute_cell(self.CELL3_CHECK)
        assert_success(r, "state check after error")
        assert "State intact after error" in get_stdout(r)

    def test_cell4_fix_continues(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2_BAD)
        self.kernel.execute_cell(self.CELL3_CHECK)
        r = self.kernel.execute_cell(self.CELL4_FIX)
        assert_success(r, "cell 4 fix")
        assert self.kernel.get_variable("fixed_result") == 10.0

    def test_cell5_chain_uses_both(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2_BAD)
        self.kernel.execute_cell(self.CELL3_CHECK)
        self.kernel.execute_cell(self.CELL4_FIX)
        r = self.kernel.execute_cell(self.CELL5_CHAIN)
        assert_success(r, "cell 5 chain")
        assert "Chained sum:" in get_stdout(r)

    def test_multiple_errors_do_not_accumulate(self):
        """Multiple failed cells should not corrupt good state."""
        self.kernel.execute_cell(self.CELL1)
        for _ in range(3):
            r = self.kernel.execute_cell("1 / 0")
            assert not r.success
        # Good state must still be accessible
        assert self.kernel.get_variable("base_value") == 100
        assert self.kernel.get_variable("items") == list(range(1, 11))

    def test_error_outputs_contain_error_type(self):
        r = self.kernel.execute_cell("1 / 0")
        error_outs = [o for o in r.outputs if o.get("type") == "error"]
        assert len(error_outs) > 0
        assert error_outs[0].get("ename") == "ZeroDivisionError"

    def test_name_error_recovery(self):
        self.kernel.execute_cell(self.CELL1)
        r_bad = self.kernel.execute_cell("result = undefined_variable + 1")
        assert not r_bad.success
        # base_value still fine
        assert self.kernel.get_variable("base_value") == 100


# ---------------------------------------------------------------------------
# 7. Large State Scenario
# ---------------------------------------------------------------------------

class TestLargeStateScenarioE2E:
    """Stress test: many variables, functions, classes, then session save/load."""

    def setup_method(self):
        self.temp_dir = TemporaryDirectory()
        self.kernel = NotebookKernel()
        self.session_manager = SessionManager(
            sessions_dir=Path(self.temp_dir.name)
        )

    def teardown_method(self):
        self.temp_dir.cleanup()

    CELL1 = "\n".join(
        [f"var_{i} = {i * 10}" for i in range(50)]
        + [f"str_var_{i} = 'value_{i}'" for i in range(10)]
        + [f"list_var_{i} = list(range({i}, {i+5}))" for i in range(5)]
    )

    CELL2 = "\n".join([
        f"def func_{i}(x): return x + {i}"
        for i in range(10)
    ])

    CELL3 = "\n".join([
        f"""
class Class_{i}:
    value = {i}
    def method(self):
        return self.value * {i + 1}
    def __repr__(self):
        return f'Class_{i}()'
""".strip()
        for i in range(5)
    ])

    CELL4 = """
# Use all variables, functions and classes together
totals = [func_0(var_0), func_1(var_1), func_2(var_2),
          func_5(var_5), func_9(var_9)]

instances = [Class_0(), Class_1(), Class_2(), Class_3(), Class_4()]
method_results = [inst.method() for inst in instances]

combined = sum(totals) + sum(method_results)
print(f"combined={combined}")
"""

    CELL5_TEMPLATE = """
# Save and load session
import importlib
"""

    CELL6_VERIFY = """
# After session restore, verify key variables
assert var_0  == 0
assert var_10 == 100
assert var_49 == 490
assert str_var_0 == 'value_0'
assert list_var_0 == list(range(0, 5))
assert func_0(10) == 10
assert func_9(10) == 19
assert Class_0().method() == 0
assert Class_4().method() == 20
print("Large state verified")
"""

    def _run_cells_1_to_4(self):
        for cell in [self.CELL1, self.CELL2, self.CELL3, self.CELL4]:
            r = self.kernel.execute_cell(cell)
            assert_success(r)

    def test_cell1_many_variables(self):
        r = self.kernel.execute_cell(self.CELL1)
        assert_success(r, "cell 1")
        ns = self.kernel.get_namespace()
        # 50 int vars + 10 str vars + 5 list vars
        int_vars = [k for k in ns if k.startswith("var_") and k[4:].isdigit()]
        assert len(int_vars) == 50
        assert ns["var_0"] == 0
        assert ns["var_49"] == 490

    def test_cell2_ten_functions(self):
        self.kernel.execute_cell(self.CELL1)
        r = self.kernel.execute_cell(self.CELL2)
        assert_success(r, "cell 2")
        for i in range(10):
            fn = self.kernel.get_variable(f"func_{i}")
            assert fn is not None
            assert fn(0) == i

    def test_cell3_five_classes(self):
        self.kernel.execute_cell(self.CELL1)
        self.kernel.execute_cell(self.CELL2)
        r = self.kernel.execute_cell(self.CELL3)
        assert_success(r, "cell 3")
        for i in range(5):
            cls = self.kernel.get_variable(f"Class_{i}")
            assert cls is not None
            inst = cls()
            assert inst.method() == i * (i + 1)

    def test_cell4_combined_usage(self):
        self._run_cells_1_to_4()
        combined = self.kernel.get_variable("combined")
        assert isinstance(combined, int)
        assert combined > 0

    def test_cell5_save_and_load_session(self):
        self._run_cells_1_to_4()

        path = self.session_manager.save_session(
            self.kernel, name="large_state_test"
        )
        assert path.exists()

        new_kernel = NotebookKernel()
        info = self.session_manager.load_session(new_kernel, path)

        restored = info["restored_vars"]
        # Key variables should be in restored list
        assert "var_0" in restored
        assert "var_49" in restored
        assert "func_0" in restored
        assert "Class_0" in restored

    def test_cell6_verify_after_restore(self):
        self._run_cells_1_to_4()

        path = self.session_manager.save_session(
            self.kernel, name="large_state_verify"
        )

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        r = new_kernel.execute_cell(self.CELL6_VERIFY)
        assert_success(r, "cell 6 verify after restore")
        assert "Large state verified" in get_stdout(r)

    def test_namespace_size(self):
        """Verify the namespace actually contains 65+ user-defined entries."""
        self._run_cells_1_to_4()
        ns = self.kernel.get_namespace()
        user_keys = [k for k in ns.keys() if not k.startswith("_")]
        # 50 int vars + 10 str vars + 5 list vars + 10 funcs + 5 classes
        # + a few more from cell 4
        assert len(user_keys) >= 65
