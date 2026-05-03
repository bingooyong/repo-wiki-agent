"""Tests for source span extractor.

Run with: uv run pytest tests/test_source_spans.py -v
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.scanner.source_spans import (
    SourceSpan,
    SourceSpanExtractor,
    _extract_java,
    _extract_markdown,
    # Language extractors
    _extract_python,
    _extract_sql,
    _extract_typescript,
    _extract_yaml,
    compute_span_digest,
    filter_spans_by_language,
    group_spans_by_file,
    spans_to_citations,
)

# ---------------------------------------------------------------------------
# Python fixtures
# ---------------------------------------------------------------------------

PYTHON_SIMPLE = """
def hello():
    print("hello")


class MyClass:
    def method(self):
        pass
"""

PYTHON_MULTILINE = '''
def complex_function(arg1, arg2, arg3=None):
    """
    A complex function with multiple
    lines of documentation.
    """
    if arg1:
        for i in range(10):
            print(i)
    return arg1 + arg2


async def async_handler():
    result = await some_call()
    return result
'''


# ---------------------------------------------------------------------------
# Java fixtures
# ---------------------------------------------------------------------------

JAVA_SIMPLE = """
public class MyService {
    private String name;

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }
}
"""

JAVA_INTERFACE = """
public interface UserRepository {
    User findById(Long id);

    List<User> findAll();
}
"""


# ---------------------------------------------------------------------------
# TypeScript fixtures
# ---------------------------------------------------------------------------

TYPESCRIPT_SIMPLE = """
export class UserService {
    private users: User[] = [];

    public addUser(user: User): void {
        this.users.push(user);
    }

    public getUsers(): User[] {
        return this.users;
    }
}

export const CONFIG = { debug: true };

export interface User {
    id: number;
    name: string;
}
"""

TYPESCRIPT_ARROW = """
const fetchData = async (url: string): Promise<Response> => {
    const response = await fetch(url);
    return response.json();
};

export const helper = (x: number) => x * 2;
"""


# ---------------------------------------------------------------------------
# SQL fixtures
# ---------------------------------------------------------------------------

SQL_SIMPLE = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
"""

SQL_VIEW = """
CREATE VIEW active_users AS
SELECT id, name, email
FROM users
WHERE active = 1;
"""

SQL_FUNCTION = """
CREATE FUNCTION get_user_count()
RETURNS INTEGER AS $$
DECLARE
    count_val INTEGER;
BEGIN
    SELECT COUNT(*) INTO count_val FROM users;
    RETURN count_val;
END;
$$ LANGUAGE plpgsql;
"""


# ---------------------------------------------------------------------------
# YAML fixtures
# ---------------------------------------------------------------------------

YAML_SIMPLE = """
# Configuration file
server:
  host: localhost
  port: 8080

database:
  host: db.example.com
  port: 5432
  name: myapp

logging:
  level: info
  format: json
"""

YAML_NESTED = """
root_key:
  child1:
    value: 1
  child2:
    value: 2
"""


# ---------------------------------------------------------------------------
# Markdown fixtures
# ---------------------------------------------------------------------------

MARKDOWN_SIMPLE = """
# Project Overview

This is the overview section.

## Architecture

Here we describe the architecture.

### Components

- Component A
- Component B

## Usage

How to use the project.
"""

MARKDOWN_CODE_BLOCKS = """
# API Documentation

## GET /users

Returns a list of users.

```json
{
  "users": []
}
```

## POST /users

Create a new user.

```python
def create_user(data):
    pass
```
"""


# ---------------------------------------------------------------------------
# Python extractor tests
# ---------------------------------------------------------------------------


class TestPythonExtractor:
    def test_extract_function(self):
        file_path = Path("test.py")
        spans = _extract_python(file_path, PYTHON_SIMPLE)

        func_names = [s.symbol for s in spans if "function" in s.summary.lower()]
        assert "hello" in func_names

    def test_extract_multiline_function(self):
        file_path = Path("test.py")
        spans = _extract_python(file_path, PYTHON_MULTILINE)

        func_names = [s.symbol for s in spans if "function" in s.summary.lower()]
        assert "complex_function" in func_names

    def test_extract_class(self):
        file_path = Path("test.py")
        spans = _extract_python(file_path, PYTHON_SIMPLE)

        class_names = [s.symbol for s in spans if "class" in s.summary.lower()]
        assert "MyClass" in class_names

    def test_line_numbers_accurate(self):
        file_path = Path("test.py")
        spans = _extract_python(file_path, PYTHON_SIMPLE)

        hello_span = next(s for s in spans if s.symbol == "hello")
        assert hello_span.line_start == 2  # def hello(): is on line 2
        assert hello_span.line_end >= hello_span.line_start

    def test_async_function(self):
        file_path = Path("test.py")
        spans = _extract_python(file_path, PYTHON_MULTILINE)

        async_names = [s.symbol for s in spans if "async" in s.summary.lower()]
        assert "async_handler" in async_names

    def test_digest_computed(self):
        spans = _extract_python(Path("test.py"), PYTHON_SIMPLE)
        for span in spans:
            assert len(span.digest) == 16
            assert span.digest.isalnum()


# ---------------------------------------------------------------------------
# Java extractor tests
# ---------------------------------------------------------------------------


class TestJavaExtractor:
    def test_extract_class(self):
        file_path = Path("MyService.java")
        spans = _extract_java(file_path, JAVA_SIMPLE)

        class_names = [s.symbol for s in spans if "class" in s.summary.lower()]
        assert "MyService" in class_names

    def test_extract_interface(self):
        file_path = Path("UserRepository.java")
        spans = _extract_java(file_path, JAVA_INTERFACE)

        assert any(s.symbol == "UserRepository" for s in spans)

    def test_extract_method(self):
        file_path = Path("MyService.java")
        spans = _extract_java(file_path, JAVA_SIMPLE)

        method_names = [s.symbol for s in spans if "method" in s.summary.lower()]
        assert "getName" in method_names
        assert "setName" in method_names

    def test_line_numbers(self):
        file_path = Path("MyService.java")
        spans = _extract_java(file_path, JAVA_SIMPLE)

        my_service = next(s for s in spans if s.symbol == "MyService")
        # class declaration should be around line 2
        assert my_service.line_start >= 1
        assert my_service.line_end >= my_service.line_start


# ---------------------------------------------------------------------------
# TypeScript extractor tests
# ---------------------------------------------------------------------------


class TestTypeScriptExtractor:
    def test_extract_class(self):
        file_path = Path("UserService.ts")
        spans = _extract_typescript(file_path, TYPESCRIPT_SIMPLE)

        class_names = [s.symbol for s in spans if "class" in s.summary.lower()]
        assert "UserService" in class_names

    def test_extract_interface(self):
        file_path = Path("types.ts")
        spans = _extract_typescript(file_path, TYPESCRIPT_SIMPLE)

        interface_names = [s.symbol for s in spans if "interface" in s.summary.lower()]
        assert "User" in interface_names

    def test_extract_const(self):
        file_path = Path("config.ts")
        spans = _extract_typescript(file_path, TYPESCRIPT_SIMPLE)

        const_names = [s.symbol for s in spans if "variable" in s.summary.lower()]
        assert "CONFIG" in const_names

    def test_arrow_function(self):
        file_path = Path("arrow.ts")
        spans = _extract_typescript(file_path, TYPESCRIPT_ARROW)

        func_names = [s.symbol for s in spans]
        assert "fetchData" in func_names
        assert "helper" in func_names


# ---------------------------------------------------------------------------
# SQL extractor tests
# ---------------------------------------------------------------------------


class TestSQLExtractor:
    def test_extract_table(self):
        file_path = Path("schema.sql")
        spans = _extract_sql(file_path, SQL_SIMPLE)

        table_names = [s.symbol for s in spans if "table" in s.summary.lower()]
        assert "users" in table_names

    def test_extract_index(self):
        file_path = Path("schema.sql")
        spans = _extract_sql(file_path, SQL_SIMPLE)

        index_names = [s.symbol for s in spans if "index" in s.summary.lower()]
        assert "idx_users_email" in index_names

    def test_extract_view(self):
        file_path = Path("views.sql")
        spans = _extract_sql(file_path, SQL_VIEW)

        view_names = [s.symbol for s in spans if "view" in s.summary.lower()]
        assert "active_users" in view_names

    def test_extract_function(self):
        file_path = Path("functions.sql")
        spans = _extract_sql(file_path, SQL_FUNCTION)

        func_names = [s.symbol for s in spans if "routine" in s.summary.lower()]
        assert "get_user_count" in func_names

    def test_line_numbers(self):
        file_path = Path("schema.sql")
        spans = _extract_sql(file_path, SQL_SIMPLE)

        users = next(s for s in spans if s.symbol == "users")
        # CREATE TABLE users should be around line 2
        assert users.line_start >= 1


# ---------------------------------------------------------------------------
# YAML extractor tests
# ---------------------------------------------------------------------------


class TestYAMLExtractor:
    def test_extract_keys(self):
        file_path = Path("config.yaml")
        spans = _extract_yaml(file_path, YAML_SIMPLE)

        key_names = [s.symbol for s in spans]
        assert "server" in key_names
        assert "database" in key_names
        assert "logging" in key_names

    def test_nested_keys(self):
        file_path = Path("config.yaml")
        spans = _extract_yaml(file_path, YAML_NESTED)

        key_names = [s.symbol for s in spans]
        assert "root_key" in key_names

    def test_line_numbers(self):
        file_path = Path("config.yaml")
        spans = _extract_yaml(file_path, YAML_SIMPLE)

        server = next(s for s in spans if s.symbol == "server")
        # server: should be around line 5
        assert server.line_start >= 1


# ---------------------------------------------------------------------------
# Markdown extractor tests
# ---------------------------------------------------------------------------


class TestMarkdownExtractor:
    def test_extract_headings(self):
        file_path = Path("README.md")
        spans = _extract_markdown(file_path, MARKDOWN_SIMPLE)

        heading_names = [s.symbol for s in spans]
        assert "Project Overview" in heading_names
        assert "Architecture" in heading_names
        assert "Components" in heading_names
        assert "Usage" in heading_names

    def test_hierarchy(self):
        file_path = Path("README.md")
        spans = _extract_markdown(file_path, MARKDOWN_SIMPLE)

        # Verify sections have line ranges
        for span in spans:
            assert span.line_start >= 1
            assert span.line_end >= span.line_start

    def test_line_numbers(self):
        file_path = Path("README.md")
        spans = _extract_markdown(file_path, MARKDOWN_SIMPLE)

        overview = next(s for s in spans if s.symbol == "Project Overview")
        # # Project Overview should be on line 2
        assert overview.line_start >= 1


# ---------------------------------------------------------------------------
# SourceSpan data class tests
# ---------------------------------------------------------------------------


class TestSourceSpan:
    def test_citation_format(self):
        span = SourceSpan(
            file="src/main.py",
            symbol="hello",
            line_start=10,
            line_end=15,
            language="python",
        )
        assert span.citation() == "src/main.py:10-15"

    def test_is_valid(self):
        valid = SourceSpan(file="a.py", symbol="x", line_start=1, line_end=10, language="python")
        invalid = SourceSpan(file="a.py", symbol="x", line_start=10, line_end=5, language="python")

        assert valid.is_valid()
        assert not invalid.is_valid()

    def test_digest_deterministic(self):
        span1 = SourceSpan(file="a.py", symbol="x", line_start=1, line_end=10, language="python")
        span2 = SourceSpan(file="a.py", symbol="x", line_start=1, line_end=10, language="python")

        assert span1.digest == span2.digest

    def test_digest_changes_with_content(self):
        span1 = SourceSpan(file="a.py", symbol="x", line_start=1, line_end=10, language="python")
        span2 = SourceSpan(file="a.py", symbol="x", line_start=2, line_end=10, language="python")

        assert span1.digest != span2.digest


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestSourceSpanExtractorIntegration:
    """Test the full extractor with multiple files."""

    def test_detect_language(self):
        extractor = SourceSpanExtractor()

        assert extractor._detect_language(Path("main.py")) == "python"
        assert extractor._detect_language(Path("Main.java")) == "java"
        assert extractor._detect_language(Path("service.ts")) == "typescript"
        assert extractor._detect_language(Path("service.tsx")) == "typescript"
        assert extractor._detect_language(Path("schema.sql")) == "sql"
        assert extractor._detect_language(Path("config.yaml")) == "yaml"
        assert extractor._detect_language(Path("README.md")) == "markdown"
        assert extractor._detect_language(Path("unknown.xyz")) == "unknown"

    def test_extract_from_multiple_files(self):
        extractor = SourceSpanExtractor()
        files = [
            (Path("test.py"), PYTHON_SIMPLE),
            (Path("MyService.java"), JAVA_SIMPLE),
            (Path("config.yaml"), YAML_SIMPLE),
            (Path("README.md"), MARKDOWN_SIMPLE),
        ]

        spans = extractor.extract_from_files(files)

        # Should have spans from all file types
        languages = {s.language for s in spans}
        assert "python" in languages
        assert "java" in languages
        assert "yaml" in languages
        assert "markdown" in languages

    def test_group_by_file(self):
        extractor = SourceSpanExtractor()
        spans = extractor.extract_from_files(
            [
                (Path("test.py"), PYTHON_SIMPLE),
                (Path("config.yaml"), YAML_SIMPLE),
            ]
        )

        grouped = group_spans_by_file(spans)

        assert "test.py" in grouped
        assert "config.yaml" in grouped
        assert len(grouped["test.py"]) > 0
        assert len(grouped["config.yaml"]) > 0

    def test_filter_by_language(self):
        extractor = SourceSpanExtractor()
        spans = extractor.extract_from_files(
            [
                (Path("test.py"), PYTHON_SIMPLE),
                (Path("MyService.java"), JAVA_SIMPLE),
            ]
        )

        python_only = filter_spans_by_language(spans, ["python"])

        assert all(s.language == "python" for s in python_only)
        assert len(python_only) < len(spans)

    def test_spans_to_citations(self):
        spans = [
            SourceSpan(file="a.py", symbol="x", line_start=1, line_end=10, language="python"),
            SourceSpan(file="b.java", symbol="y", line_start=5, line_end=20, language="java"),
        ]

        citations = spans_to_citations(spans)

        assert "a.py:1-10" in citations
        assert "b.java:5-20" in citations


# ---------------------------------------------------------------------------
# Line accuracy tests
# ---------------------------------------------------------------------------


class TestLineAccuracy:
    """Critical tests to ensure line numbers are accurate."""

    def test_python_class_line_accuracy(self):
        """Verify Python class line numbers are accurate."""
        content = """# line 1
# line 2

class MyClass:  # line 4
    pass
"""
        spans = _extract_python(Path("test.py"), content)
        my_class = next((s for s in spans if s.symbol == "MyClass"), None)

        assert my_class is not None
        assert my_class.line_start == 4

    def test_python_function_line_accuracy(self):
        """Verify Python function line numbers are accurate."""
        content = """# comment line

def my_function():  # line 3
    return 42
"""
        spans = _extract_python(Path("test.py"), content)
        my_func = next((s for s in spans if s.symbol == "my_function"), None)

        assert my_func is not None
        assert my_func.line_start == 3

    def test_java_class_line_accuracy(self):
        """Verify Java class line numbers are accurate."""
        content = """package com.example;  // line 1

public class MyClass {  // line 3
    public void method() {}
}
"""
        spans = _extract_java(Path("MyClass.java"), content)
        my_class = next((s for s in spans if s.symbol == "MyClass"), None)

        assert my_class is not None
        assert my_class.line_start == 3

    def test_markdown_heading_line_accuracy(self):
        """Verify Markdown heading line numbers are accurate."""
        content = """# Title

Some text.

## Section One

More text.

### Subsection
"""
        spans = _extract_markdown(Path("README.md"), content)

        title = next((s for s in spans if s.symbol == "Title"), None)
        section = next((s for s in spans if s.symbol == "Section One"), None)

        assert title is not None
        assert title.line_start == 1

        assert section is not None
        assert section.line_start == 5

    def test_sql_table_line_accuracy(self):
        """Verify SQL table definition line numbers are accurate."""
        content = """-- line 1

CREATE TABLE users (  -- line 3
    id INTEGER PRIMARY KEY
);
"""
        spans = _extract_sql(Path("schema.sql"), content)
        users = next((s for s in spans if s.symbol == "users"), None)

        assert users is not None
        assert users.line_start == 3

    def test_yaml_key_line_accuracy(self):
        """Verify YAML key line numbers are accurate."""
        content = """key1: value1  # line 1

key2:  # line 3
  nested: value
"""
        spans = _extract_yaml(Path("config.yaml"), content)
        key2 = next((s for s in spans if s.symbol == "key2"), None)

        assert key2 is not None
        assert key2.line_start == 3

    def test_multifile_line_numbers_consistent(self):
        """Verify line numbers are consistent across multiple extractions."""
        content1 = """def foo():
    pass
"""
        content2 = """def bar():
    pass
"""
        extractor = SourceSpanExtractor()

        spans1 = extractor.extract_from_file(Path("a.py"), content1)
        spans2 = extractor.extract_from_file(Path("b.py"), content2)

        foo = next(s for s in spans1 if s.symbol == "foo")
        bar = next(s for s in spans2 if s.symbol == "bar")

        # Both are on line 1 in their respective files
        assert foo.line_start == 1
        assert bar.line_start == 1


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestUtilityFunctions:
    def test_compute_span_digest(self):
        digest = compute_span_digest("file.py", 10, 20)
        assert len(digest) == 16
        assert digest.isalnum()

    def test_compute_span_digest_deterministic(self):
        d1 = compute_span_digest("file.py", 10, 20)
        d2 = compute_span_digest("file.py", 10, 20)
        assert d1 == d2

    def test_compute_span_digest_different_spans(self):
        d1 = compute_span_digest("file.py", 10, 20)
        d2 = compute_span_digest("file.py", 10, 21)
        assert d1 != d2
