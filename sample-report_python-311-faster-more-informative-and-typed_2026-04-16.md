---
title: 'Python 3.11: Faster, More Informative, and Typed'
type: research
date: '2026-04-16'
time: '13:59:19'
tags:
- python
- performance
- typing
- error-handling
prompt_summary: Summary of python 3.11 features
tokens_used: 24602
estimated_cost: $0.0602
follow_up_count: 0
last_updated: '2026-04-16 13:59:19'
---

# Python 3.11: Faster, More Informative, and Typed

## Research Report

# Comprehensive Analysis of Python 3.11: Architectural Enhancements, Performance Optimizations, and Typological Advancements

**Key Points:**
*   It seems likely that Python 3.11 represents one of the most substantial architectural optimizations in the language's history, predominantly due to the integration of the Faster CPython initiative.
*   Research suggests an average performance speedup of approximately 25% compared to Python 3.10, with some computational workloads experiencing gains of up to 60%.
*   The evidence leans toward a significantly improved developer experience, driven by the implementation of fine-grained error tracebacks that pinpoint exact expression failures.
*   It is generally understood that Python 3.11 modernizes concurrent programming paradigms through the introduction of Exception Groups and asynchronous TaskGroups.
*   Advances in static typing, including variadic generics and the `Self` type, appear to offer profound benefits for data science libraries and enterprise-scale codebases.

**Executive Overview:**
The release of Python 3.11 introduces a confluence of performance scaling, syntax refinement, and static analysis enhancements. As Python continues to dominate fields such as artificial intelligence, data science, and backend infrastructure, mitigating its historical execution speed bottlenecks has become a critical objective for the core development team. This update addresses these concerns head-on.

**Performance and Execution:**
At the core of Python 3.11's appeal is the Specializing Adaptive Interpreter, which dynamically optimizes repetitive operations at runtime. Combined with streamlined stack frames, frozen core modules for faster startup, and zero-cost exceptions, the interpreter executes instructions significantly faster while utilizing system memory more efficiently.

**Developer Ergonomics and Debugging:**
Debugging complex applications has historically been hindered by ambiguous traceback reports. Python 3.11 revolutionizes this process by highlighting the exact node in the abstract syntax tree (AST) that triggered an exception. Furthermore, the ability to annotate exceptions with custom notes provides localized context to runtime errors.

**Typing and Standard Library Augmentations:**
To support the growing reliance on static type checkers (such as `mypy`), Python 3.11 expands the `typing` module to accommodate multi-dimensional data arrays, recursive class methods, and strict dictionary structures. Simultaneously, the standard library has been fortified with native TOML parsing capabilities and safer, more intuitive constructs for asynchronous programming. 

***

## 1. Introduction and Release Chronology

Python 3.11 was officially released on October 24, 2022, following a seventeen-month development cycle characterized by extensive community testing and architectural overhauls [cite: 1, 2]. The iteration introduces a myriad of features aimed at both execution efficiency and developer ergonomics, cementing Python's frequently cited position as a cornerstone of modern programming, particularly in data science and artificial intelligence [cite: 3]. 

The life cycle of Python 3.11 follows the release calendar specified in PEP 664. Following its initial stable release, the version proceeded through regular bugfix updates. Currently, Python 3.11 has entered the "security fixes only" stage of its lifecycle, during which it no longer receives regular binary installer updates but continues to receive vital source-only security patches until October 2027 [cite: 4, 5]. 

| Release Phase | Date | Description |
| :--- | :--- | :--- |
| **Development Begins** | May 3, 2021 | Initial architectural planning and alpha stages [cite: 5]. |
| **Stable Release (3.11.0)** | October 24, 2022 | Final release ready for production environments [cite: 2, 6]. |
| **Final Bugfix (3.11.9)** | April 2, 2024 | Final regular bugfix release with compiled binary installers [cite: 5, 7]. |
| **Security Release (3.11.15)** | March 3, 2026 | Source-only release addressing memory safety and DoS vulnerabilities [cite: 4, 5]. |

The overarching philosophy of Python 3.11 revolves around minimizing overhead without sacrificing the dynamic nature of the language. This delicate balance is achieved by isolating bottlenecks within the CPython interpreter and rewriting foundational execution logic, ultimately producing an iteration that feels familiar to developers but behaves with markedly superior efficiency [cite: 8].

## 2. Performance Optimizations: The Faster CPython Project

Perhaps the most heralded advancement in Python 3.11 is its profound increase in execution speed. The culmination of the "Faster CPython" project, this release asserts a benchmarked performance gain of 10% to 60% depending on the specific workload, with the standard `pyperformance` benchmark suite measuring an average speedup of 1.25x (or 25%) relative to Python 3.10 [cite: 1, 3]. 

These improvements are transparent to the user; they require zero modifications to existing codebases, making them an immediate net positive for legacy systems and modern applications alike [cite: 9, 10].

### 2.1 Specializing Adaptive Interpreter (PEP 659)
The cornerstone of Python 3.11's speed is the implementation of PEP 659, which introduces a specializing adaptive interpreter. Because Python is a dynamically typed language, the interpreter typically wastes computational cycles repeatedly determining the types of variables during execution [cite: 8]. 

The adaptive interpreter acts similarly to a Just-In-Time (JIT) compiler, though without actual machine-code compilation [cite: 2]. At runtime, the interpreter observes the execution of bytecode. If it detects that a specific instruction (such as an addition operation or a method call) is executed repeatedly with identical data types, it "adapts" the bytecode, replacing the generic, slow instruction with a highly specialized, type-specific instruction [cite: 8, 10]. 

For example, if a function is iteratively summing integer values, the interpreter replaces the standard binary operation opcode with one specifically optimized for C-level integer addition. This specialization bypasses the need for repetitive type checking and method resolution. If the data type subsequently changes (e.g., from an integer to a string), the interpreter smoothly "de-optimizes" back to the generic operation, ensuring that the language's dynamic flexibility is preserved [cite: 8]. 

Mathematical modeling of this optimization shows a significant reduction in constant time overhead per operation:
\[ T_{total} = N \cdot (T_{dispatch} + T_{check} + T_{execute}) \]
In Python 3.11, for frequently executed paths, \( T_{check} \) approaches zero, thereby yielding a higher overall throughput ($S \approx 1.25$) [cite: 1, 10].

### 2.2 Reduced Startup Time and Frozen Modules
The time it takes for the Python interpreter to initialize has historically been a friction point, particularly for short-lived command-line interface (CLI) scripts and serverless functions. Python 3.11 targets this by heavily optimizing module loading and caching execution environments.

During the startup sequence, Python must import foundational modules. In Python 3.11, the set of "frozen" modules—modules pre-compiled into the Python executable itself—has been expanded significantly. Core modules such as `abc`, `codecs`, `io`, `os`, `posixpath`, and `site` are now statically embedded within the CPython binaries (specifically generated at build time via `Python/frozen.c`) [cite: 9]. 

By bypassing the file system completely during the initial import phase, the interpreter avoids costly I/O operations and disk lookups, leading to measurably faster boot times [cite: 9, 10]. 

### 2.3 Streamlined Stack Frames and Inlined Function Calls
Function calls in Python have traditionally been expensive due to the overhead of creating and destroying execution frames on the C stack. Python 3.11 introduces "Streamlined Stack Frames." When a Python function calls another Python function, the interpreter now avoids using the C stack altogether, opting instead to allocate frame objects dynamically within a contiguous chunk of memory managed directly by CPython [cite: 9].

Furthermore, Python 3.11 heavily aggressively inlines calls to built-in C functions for built-in types. For instance, invoking the `len()` function on a string object directly routes to the underlying C-code execution, bypassing the standard Python calling convention. This specific optimization alone can yield up to a 20% speedup for fundamental operations [cite: 9].

Namespace lookups have also been aggressively cached. The memory index in the `globals` namespace is stored, mitigating the need for dictionary lookups on repeated access. Similarly, the memory address of method functions is cached, allowing for near-instantaneous resolution even across long, complex object-oriented inheritance chains [cite: 9].

### 2.4 Zero-Cost Exceptions
In previous iterations of Python, the `try`/`except` block incurred a minor performance penalty even if an exception was never raised, due to the setup and teardown overhead of the exception-handling mechanisms. Python 3.11 introduces "Zero-Cost Exceptions," an architectural shift where the `try` block imposes absolutely zero computational overhead [cite: 2, 11]. The performance cost is strictly deferred to the moment an exception is actually thrown. In codebases where exception handling is primarily used for rare error conditions, this leads to an immediate aggregate performance lift.

## 3. Advanced Error Handling and Exception Management

Historically, debugging Python code—particularly complex nested dictionaries or chained mathematical operations—has required developers to parse vague error messages. Python 3.11 radically alters the debugging landscape by enhancing tracebacks, grouping exceptions, and allowing contextual metadata [cite: 12, 13].

### 3.1 Fine-Grained Error Locations in Tracebacks (PEP 657)
Prior to 3.11, an unhandled exception generated a traceback that indicated the file and the specific line number where the error occurred [cite: 14]. However, if the line contained a deeply nested dictionary lookup or chained arithmetic, isolating the precise fault was tedious.

Python 3.11 resolves this via PEP 657, which prints fine-grained error locations. The interpreter now underlines the exact expression that triggered the failure using a series of caret (`^`) and tilde (`~`) symbols [cite: 1, 8]. 

Consider the following function processing nested data:
```python
def get_margin(data):
    margin = data['profits']['monthly'] / 10 + data['profits']['yearly'] / 2
    return margin

data = {
    'profits': {'monthly': 0.82, 'yearly': None},
    'losses': {'monthly': 0.23, 'yearly': 1.38},
}
print(get_margin(data))
```
In Python 3.10, this raised a `TypeError` stating `unsupported operand type(s) for /: 'NoneType' and 'int'`, pointing generically to line 2 [cite: 14]. The developer would have to deduce whether `['monthly']` or `['yearly']` evaluated to `None`. 

In Python 3.11, the traceback vividly highlights the exact point of failure:
```text
Traceback (most recent call last):
  File "asd.py", line 15, in <module>
    print(get_margin(data))
          ^^^^^^^^^^^^^^^^
  File "asd.py", line 2, in print_margin
    margin = data['profits']['monthly'] / 10 + data['profits']['yearly'] / 2
                                               ~~~~~~~~~~~~~~~~~~~~~~~~~~^~~
TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'
```
This precision drastically reduces debugging latency and enhances code maintainability [cite: 13, 14].

### 3.2 Exception Groups and the `except*` Syntax (PEP 654)
As concurrent and asynchronous programming paradigms have proliferated within the Python ecosystem, the limitation of raising and catching only one exception at a time became a glaring bottleneck. Python 3.11 introduces PEP 654, which actualizes `ExceptionGroup` and `BaseExceptionGroup`, permitting multiple exceptions to be bundled and raised concurrently [cite: 2, 12].

To interface with these groups, Python 3.11 introduces a novel syntactic construct: `except*` [cite: 1, 12]. The asterisk denotes that the block will catch subsets of exceptions within a group that match a specific type, leaving the unhandled exceptions to propagate upward.

```python
try:
    raise ExceptionGroup("Multiple failures", [
        ValueError("Invalid input"),
        KeyError("Missing configuration"),
        TypeError("Type mismatch")
    ])
except* ValueError as e:
    print(f"Handled ValueErrors: {e.exceptions}")
except* KeyError as e:
    print(f"Handled KeyErrors: {e.exceptions}")
```
In this scenario, both the `ValueError` and `KeyError` blocks execute sequentially, processing their respective exceptions out of the group, while the `TypeError` is automatically propagated [cite: 10, 12]. This paradigm is indispensable for asynchronous workflows where multiple tasks might fail simultaneously [cite: 2].

### 3.3 Exception Notes (PEP 678)
In highly modular applications, exceptions are often caught, wrapped, and re-raised, losing their original contextual narrative. Python 3.11 imbues the base `Exception` class with a `__note__` attribute (defaulting to `None`) and a corresponding `.add_note()` method [cite: 12, 13].

Developers can dynamically append string notes to an exception object as it traverses the call stack [cite: 14]. When the traceback is eventually printed, the interpreter systematically outputs these notes at the termination of the error report, supplying vital domain-specific context (e.g., "Note: This occurred during the database retry loop") [cite: 13].

## 4. Typological Advancements and Static Analysis

While Python remains dynamically typed at runtime, the ecosystem has aggressively adopted static type checking via modules like `typing` and external linters like `mypy`. Python 3.11 further robustifies this type system, bringing it closer to the strictness of languages like TypeScript or Rust, thereby mitigating large-scale enterprise errors [cite: 2, 8].

### 4.1 Variadic Generics (PEP 646)
Prior to Python 3.11, the `typing.Generic` class was constrained. It could not natively articulate multidimensional shapes—a critical requirement for data science libraries such as NumPy, Pandas, and TensorFlow [cite: 14]. 

PEP 646 solves this by introducing "Variadic Generics," powered by `TypeVarTuple` and the new unpack syntax `*`. Developers can now parameterize a type with an arbitrary, variable number of types [cite: 1, 14].
```python
from typing import TypeVarTuple, Generic

Shape = TypeVarTuple('Shape')

class Array(Generic[*Shape]):
    pass

# Represents a 3-dimensional array
image: Array[Height, Width, Channels] 
```
For legacy codebases utilizing Python 3.10 or older, compatibility can be achieved using `Generic[Unpack[Shape]]` [cite: 14]. This implementation effectively eliminates an entire class of shape-mismatch bugs in machine learning pipelines during the static analysis phase.

### 4.2 The `Self` Type (PEP 673)
Object-oriented programming in Python often involves class methods that return an instance of the class itself (e.g., builder patterns or fluent interfaces). Historically, annotating these return types was convoluted, often requiring the use of string literals or cumbersome `TypeVar` declarations [cite: 1].

Python 3.11 introduces the explicit `Self` type annotation [cite: 1, 3]. 
```python
from typing import Self

class DatabaseConnection:
    def connect(self) -> Self:
        self._initialize_socket()
        return self

    @classmethod
    def from_config(cls, config_path: str) -> Self:
        return cls()
```
The `Self` annotation intuitively communicates that the method yields an instance of the enclosing class, vastly simplifying inheritance logic, as subclasses calling inherited methods will correctly infer the subclass type rather than the parent class type [cite: 1, 3].

### 4.3 Arbitrary Literal Strings (PEP 675)
Security vulnerabilities, particularly SQL injection and cross-site scripting (XSS), commonly arise when unsanitized user inputs are passed into execution strings. Python 3.11 introduces `LiteralString` to statically enforce safe string handling [cite: 1, 12].

By annotating a function parameter with `LiteralString`, the developer mandates that the function can only accept a string literal defined strictly within the source code, or a string dynamically composed exclusively of other literal strings [cite: 12].
```python
from typing import LiteralString

def execute_query(query: LiteralString):
    db.execute(query)

# Valid: Static literal string
execute_query("SELECT * FROM users") 

# Invalid: Type checker will reject this due to potential injection
user_input = get_user_input()
execute_query(f"SELECT * FROM users WHERE name = {user_input}") 
```
Static analyzers will proactively reject non-static argument injections, providing an ironclad, compile-time defense against injection attacks [cite: 1, 12].

### 4.4 Granular `TypedDict` Fields (PEP 655)
When defining strict dictionary schemas using `TypedDict`, developers previously struggled with dictionaries where only specific keys were optional. Python 3.11 introduces the `Required` and `NotRequired` type qualifiers [cite: 1, 12]. These allow for granular, per-item annotations, ensuring that API responses or JSON payloads align perfectly with their expected structures without requiring highly complex subclassing workarounds [cite: 1].

## 5. Standard Library Additions and Asynchronous Paradigm Shifts

The Python Standard Library, often described as "batteries included," receives highly targeted expansions in version 3.11, particularly aimed at modernizing configuration management and asynchronous execution [cite: 3, 8].

### 5.1 Native TOML Parsing (`tomllib`, PEP 680)
TOML (Tom's Obvious Minimal Language) has rapidly become the de facto standard for Python project configuration, chiefly manifested in the ubiquitous `pyproject.toml` file [cite: 8, 13]. Prior to 3.11, parsing these files required third-party libraries. 

Python 3.11 integrates `tomllib` directly into the standard library [cite: 1, 13]. Designed specifically as a fast, read-only parser, `tomllib.load()` and `tomllib.loads()` provide an incredibly efficient mechanism for tools and scripts to ingest configuration data without enlarging their dependency footprint [cite: 8].

### 5.2 Asynchronous Task Groups (`asyncio.TaskGroup`)
The complexity of managing concurrent asynchronous routines—particularly handling the cancellation of sibling tasks when one fails—has long been a hurdle. Leveraging the new `ExceptionGroup` architecture, Python 3.11 introduces `asyncio.TaskGroup` [cite: 2, 12].

Functioning as an asynchronous context manager, a `TaskGroup` guarantees that if any spawned task within the group encounters an unhandled exception, all other pending tasks in the group are safely and automatically cancelled [cite: 2]. 
```python
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(fetch_data(url1))
    task2 = tg.create_task(fetch_data(url2))
```
Once the block exits, the TaskGroup waits for all tasks to complete or be cancelled. If multiple errors occur, they are bundled into an `ExceptionGroup`, unifying error handling and execution flow into a highly robust, intuitive model [cite: 2].

### 5.3 Enumeration and Quality-of-Life Improvements
*   **`StrEnum`**: A highly requested addition, the `enum` module now includes `StrEnum`, which guarantees that the enum members are strictly strings, streamlining integrations with APIs and JSON serialization [cite: 12].
*   **`contextlib.chdir`**: A new context manager that safely changes the current working directory for the duration of the `with` block, reverting it automatically upon exit [cite: 14].
*   **Negative Zero Formatting**: Mathematical precision formatting has been updated to consistently recognize and display negative zero (`-0.0`), aligning the language more tightly with IEEE 754 floating-point specifications [cite: 2, 11].

## 6. Deprecations, Removals, and Security Hardening

Maintaining the agility of the Python language necessitates the systematic pruning of obsolete functionalities. Python 3.11 undertakes significant "dead battery" removals and establishes firmer security postures [cite: 2].

### 6.1 Legacy Module Deprecations (PEP 594)
PEP 594 identifies numerous legacy modules within the standard library—many of which were designed for the internet protocols of the 1990s—and officially marks them for deprecation [cite: 1]. Modules dealing with obsolete data formats or unmaintained networking protocols will raise `DeprecationWarning` in 3.11 and are scheduled for total removal in Python 3.13 [cite: 1]. 

### 6.2 C API Changes and Unsafe Paths
The `Py_UNICODE` encoder APIs, which have been legacy components for several versions, have been explicitly removed (PEP 624). Furthermore, various C macros have been converted to static inline functions (PEP 670), yielding safer and more predictable compilation behavior for extension modules [cite: 1].

Python 3.11 also introduces the `-P` command-line option and the `PYTHONSAFEPATH` environment variable. When engaged, these features prevent the interpreter from automatically prepending potentially unsafe or unverified paths to `sys.path`, mitigating a common vector for code injection and dependency confusion attacks [cite: 1].

### 6.3 Ongoing Security Maintenance
As Python 3.11 exists in its security-only maintenance phase, recent updates reflect a rigorous commitment to enterprise security. For example, the 3.11.15 release (March 2026) addressed critical use-after-free vulnerabilities within the `ssl` module and list comparisons (`list_richcompare_impl`) during concurrent workloads [cite: 4]. It additionally upgraded the bundled `libexpat` parser to mitigate severe XML injection and memory amplification vulnerabilities (CVE-2026-24515, CVE-2025-59375), and fortified `plistlib` and `http.server` against memory-exhaustion Denial-of-Service (DoS) attacks [cite: 4].

## 7. Conclusion

Python 3.11 is a monumental release that elegantly intertwines raw computational acceleration with sophisticated syntax enhancements. The implementation of the Faster CPython initiative and the Specializing Adaptive Interpreter successfully disrupts the narrative that Python is inherently too slow for high-performance computing tasks [cite: 8, 9]. 

Concurrently, the meticulous refinements to traceback locations [cite: 13, 14], the integration of robust asynchronous Exception Groups [cite: 2, 12], and the expansion of the static typing ecosystem via Variadic Generics [cite: 14] and the `Self` annotation [cite: 3] demonstrate a profound understanding of modern developer needs. Python 3.11 ensures that the language remains not merely relevant, but fundamentally paramount in the evolving landscape of global software engineering.

**Sources:**
1. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHu77VTQXIBP7XtNhcPjFfnNKFvd-yYLfXcbdwsJAOTkFrJpWddqKpxGcLgX0GOo_rAl7Z0n3AZbIvPkIiZkcrpn-fqsPhqByCedf88DmnAqRP1ivzeHLcZMsHjEBlyWNlb)
2. [realpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4Rr_vxeIHX7_w6LuhqODfW4lqopQ78vOprQiRtJYd4jR0E6ZYQ3oepgbxhvXqR_6WLCrVeJVa-G-E23PbXuZ0_Zci5Iqvr3l4a2kywGtmYlUYVuHzTcP4GDn8AyeftzHSE_c=)
3. [datacamp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnlVt0eO59AeD-0eZOOkAcNN1taYnpfexpsGSOQ2lzGED5MfYOjuNUq8etcjeSVcrkgKfKePILpsWdhH7WwCDZEZqrp8_xtpJ1Lrbe37gVYhE6a6nSIqPNd8bTrDzqQbw0LxKjO3ScpuL3_-0duzdKGcXkJThNMBXFqVhilVVB0y58bVhJdcJhGgwfyNA=)
4. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGqIjtXtZEvL8GsMx8mFDWbiHfV3_-7iSoCY-nsTBg0tglGomo3bp_zHg-yzzLWroI3iYs_IvgL6m_VtsGZFpu9eXWp55JuSh2sA-BBKmkX4ikA7QG7vg4ZbWoZ5T7d7YrL-b9PxZ4z3fs-kQ==)
5. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGw9IyhQgPFTxWgSlT8bazsJ1MdlZui2CBrjSsO9dpGJ0YS45hjDs-NDUw4Zfs5ImO729dyeg_aHxjhZ592GypnyWr6cWs8Gg7zOq2gFTgBGZ2yRDYnqA==)
6. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFeD2RWqC6sn1KfkFTS7uoXsrSW6Srg9QQ9x1X6P223ZG9t_3Aje0ff7GythZxy4BiKr0n784nNlexnsDNUVVm9w8jWQcL4enZRiHv9tIumWAzIVEzr33zjlasPehT4xvbSUWE2mP4-cgV1)
7. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXfg1VsWtrB7BSwBYETwcf9rlSCbzQ55YsCA4O63EEfNaqDEAN9CiztZfeSxQC1tNWXYlEtHRQv7S_Vv2pNnMFoErjL9YlYm0Zcrd36572b4BROVfaQgzRKQ==)
8. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEyDIp5UFCDvaOyIsTg2rsMuBGja6WlGmF52yWeSkQHBGdLw3p39Bs2z5JSnDxHlbm-LAhVX5q0MlwvVdklqYJ3GTjnwRtZ-S1NVAT3dnDmIKOnaiF1AdYNAXhC56voWRb1WVQRMmHs764PkiCo2WoEU-U0PedbWBbHXyCm)
9. [andy-pearce.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFA898WkkSxLm6utpxbLfex5nd7i91NpKYsOCfMe2snl6vyPBg_T3k81ruDD2NYCBOCLoLW4DPGx-uTg-IO3LZsh1fbsdS3G1PC6MwA4_1ymggKtCNdZFxUEIkzIPDbDg9YO2zsp13K-rrEvEDz6iGWLI6wWHxbSn9HfZdjefYFSQPmeXYxttLfJQA-HThoMkJZHEItsZY=)
10. [theodo.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsoxrGE6ZH_IPRj1RuTrMIT67Mcfg8RaINbUP4KvsycQXEz1CyOYCsVV2oS2YIC8BgQNKOuNtKqesDVkQUZKi758ut24RO8rfg8d8LMqFLV-G3yT3lKTtX6XYxDFIeSfGh0L4IHe2YO1ug110UsZtrcIS_NBZUIhUw36Y=)
11. [ethans.co.in](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFY4aspWcgM1eOynvB5PGrbZ3EMSYa5zOfELRrYHNKQILk_XOhQ_Ks36RYX099-HNOR94L63oE4EgM18GI8jp6qWGEp1_PNpks2hCV0wBrsk008XYf-vAGLpE9x3mRHaLxggth55fOPGteCKBbakGw84Rr8rwwpoDihTjDwaw==)
12. [flyaps.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmLig38tpWfz8lJoIBak5QE4uaqk2uwM3rfgUe94m_5pPYmSAmF3QKxCShR5qx_kbIiNvr1dLgADZdahiKgIWnugMuI5jWepm3fxiFDz3-3zPYBfRyWmpbB4RCPDHX8k743q8sDvG6kKGxANtSFPa2ylBo)
13. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGn_lxMUeJft6QNy7S_Ucabbj5qZ09uvQJsztHfd4M7GiAyuonunBKw57cEoRVD7tY55eGvzIJLYoT1cRQEb66hNBGNDiCT4lIo56vX-WEe7jHhemfs1JoDJHtLGDa32d2X3kfRJ5gRL1zw4tyK8h7t6t9Se1V5Rzzuo2-aBAMwTBEfVokR5zgP-MDy2l7ArPlfUp8j)
14. [deepsource.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG4bGhOBpK3FpeI1Bo5q3jPnzNGHodBD6-S28xdss4qpd-i-q_x95XFLJefdY20TZIa1qRze4OYjyuAfQ68FXlLFfs4GtL3C1y9kpwdx1oM0RgqjehP0R1FjKURTHI4HuXFh_mqUCQ=)
