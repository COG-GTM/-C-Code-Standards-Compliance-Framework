# Rule Reference

Complete reference documentation for all code standards rules.

## Overview

Rules are organized by severity:
- **Critical (Rule 20-29):** Safety/security issues that must be fixed
- **Major (Rule 30-39):** Quality issues that should be reviewed
- **Minor (Rule 40-49):** Style issues that improve maintainability

---

## Critical Rules (Block Merge)

### Rule 20: Check All Return Values

**Severity:** 🔴 Critical  
**clang-tidy checks:** `bugprone-unused-return-value`, `cert-err33-c`

#### Description
All return values from functions that can fail must be checked. Ignoring return values hides errors and leads to undefined behavior.

#### Affected Functions
- Memory: `malloc`, `calloc`, `realloc`, `aligned_alloc`
- File I/O: `fopen`, `fclose`, `fread`, `fwrite`, `fseek`, `ftell`
- POSIX I/O: `open`, `close`, `read`, `write`, `lseek`
- Network: `socket`, `bind`, `listen`, `accept`, `connect`, `send`, `recv`
- Threading: `pthread_create`, `pthread_join`, `pthread_mutex_lock`

#### Examples

```c
// ❌ BAD - Return values ignored
FILE *f = fopen("data.txt", "r");
fread(buffer, 1, 100, f);
fclose(f);

// ✅ GOOD - All return values checked
FILE *f = fopen("data.txt", "r");
if (f == NULL) {
    perror("fopen");
    return -1;
}

size_t n = fread(buffer, 1, 100, f);
if (n != 100 && ferror(f)) {
    perror("fread");
    fclose(f);
    return -1;
}

if (fclose(f) != 0) {
    perror("fclose");
}
```

---

### Rule 21: Prevent Buffer Overflows

**Severity:** 🔴 Critical  
**clang-tidy checks:** `bugprone-not-null-terminated-result`, `clang-analyzer-security.insecureAPI.strcpy`

#### Description
Never use unbounded string functions. Always use functions that accept a size parameter.

#### Banned vs Safe Functions

| Banned | Safe Alternative |
|--------|------------------|
| `strcpy` | `strncpy`, `strlcpy` |
| `strcat` | `strncat`, `strlcat` |
| `sprintf` | `snprintf` |
| `gets` | `fgets` |
| `scanf("%s")` | `scanf("%Ns")` where N is buffer size - 1 |

#### Examples

```c
// ❌ BAD - No bounds checking
char dest[10];
strcpy(dest, src);  // Buffer overflow if src > 9 chars

// ✅ GOOD - Bounded copy
char dest[10];
strncpy(dest, src, sizeof(dest) - 1);
dest[sizeof(dest) - 1] = '\0';

// ✅ BETTER - snprintf handles size automatically
char dest[10];
snprintf(dest, sizeof(dest), "%s", src);
```

---

### Rule 22: Prevent Null Pointer Dereference

**Severity:** 🔴 Critical  
**clang-tidy checks:** `clang-analyzer-core.NullDereference`

#### Description
Always validate pointers before dereferencing. Null dereference causes crashes (SIGSEGV).

#### Examples

```c
// ❌ BAD - No null check
void process(Data *data) {
    printf("%d\n", data->value);  // Crash if data is NULL
}

// ✅ GOOD - Validate before use
void process(Data *data) {
    if (data == NULL) {
        fprintf(stderr, "Error: NULL data\n");
        return;
    }
    printf("%d\n", data->value);
}
```

---

### Rule 23: Prevent Resource Leaks

**Severity:** 🔴 Critical  
**clang-tidy checks:** `clang-analyzer-unix.Malloc`

#### Description
Every allocation must have a corresponding deallocation on all code paths, including error paths.

#### Examples

```c
// ❌ BAD - Leak on error path
void process(void) {
    char *buf = malloc(100);
    FILE *f = fopen("file.txt", "r");
    
    if (f == NULL) {
        return;  // LEAK: buf not freed
    }
    
    free(buf);
    fclose(f);
}

// ✅ GOOD - Cleanup pattern
void process(void) {
    char *buf = NULL;
    FILE *f = NULL;
    
    buf = malloc(100);
    if (buf == NULL) goto cleanup;
    
    f = fopen("file.txt", "r");
    if (f == NULL) goto cleanup;
    
    // ... work ...
    
cleanup:
    free(buf);
    if (f) fclose(f);
}
```

---

### Rule 24: Prevent Use-After-Free

**Severity:** 🔴 Critical  
**clang-tidy checks:** `bugprone-use-after-move`, `bugprone-double-free`

#### Description
Never access memory after it has been freed. Set pointers to NULL after free.

#### Examples

```c
// ❌ BAD - Use after free
char *data = malloc(100);
free(data);
printf("%s\n", data);  // UNDEFINED BEHAVIOR

// ✅ GOOD - NULL after free
char *data = malloc(100);
// ... use data ...
free(data);
data = NULL;  // Prevents accidental use
```

---

### Rule 25: Initialize All Variables

**Severity:** 🔴 Critical  
**clang-tidy checks:** `clang-analyzer-core.uninitialized.*`

#### Description
All variables must be initialized before use. Uninitialized memory contains garbage.

#### Examples

```c
// ❌ BAD - Uninitialized variable
int result;
if (condition) {
    result = 42;
}
return result;  // Garbage if condition is false

// ✅ GOOD - Initialize with default
int result = 0;
if (condition) {
    result = 42;
}
return result;
```

---

### Rule 26: Avoid Insecure APIs

**Severity:** 🔴 Critical  
**clang-tidy checks:** `clang-analyzer-security.insecureAPI.rand`, `cert-msc30-c`

#### Description
Do not use insecure or deprecated functions, especially for security-sensitive operations.

#### Insecure vs Secure APIs

| Insecure | Secure | Notes |
|----------|--------|-------|
| `rand()` | `getrandom()`, `arc4random()` | Predictable PRNG |
| `srand()` | N/A | Use secure RNG |
| `getpw()` | `getpwuid_r()` | Not thread-safe |
| `tmpnam()` | `mkstemp()` | Race condition |

---

## Major Rules (Requires Review)

### Rule 30: Avoid Narrowing Conversions

**Severity:** 🟡 Major  
**clang-tidy checks:** `bugprone-narrowing-conversions`

#### Description
Check for overflow before casting to a smaller type.

#### Examples

```c
// ❌ BAD - Silent truncation
long big = LONG_MAX;
int small = big;  // Truncated!

// ✅ GOOD - Check before cast
long big = LONG_MAX;
if (big > INT_MAX || big < INT_MIN) {
    return ERROR_OVERFLOW;
}
int small = (int)big;
```

---

### Rule 31: Consistent Parameter Names

**Severity:** 🟡 Major  
**clang-tidy checks:** `readability-inconsistent-declaration-parameter-name`

#### Description
Function declaration and definition must use the same parameter names.

---

### Rule 32: No Redundant Code

**Severity:** 🟡 Major  
**clang-tidy checks:** `bugprone-branch-clone`, `misc-redundant-expression`

#### Description
Remove duplicate, unreachable, or redundant code.

---

### Rule 33: Prevent Infinite Loops

**Severity:** 🟡 Major  
**clang-tidy checks:** `bugprone-infinite-loop`

#### Description
Ensure all loops have a reachable exit condition.

---

### Rule 34: Thread Safety

**Severity:** 🟡 Major  
**clang-tidy checks:** `concurrency-mt-unsafe`

#### Description
Use thread-safe functions in multi-threaded code.

---

### Rule 35: Performance Issues

**Severity:** 🟡 Major  
**clang-tidy checks:** `performance-*`

#### Description
Avoid unnecessary copies and allocations.

---

## Minor Rules (Style)

### Rule 40: Consistent Formatting

**Severity:** 🟢 Minor  
**Enforced by:** `.clang-format`

#### Description
Use consistent code formatting. This project uses Allman brace style with 4-space indentation.

```c
// ✅ Correct (Allman style)
if (condition)
{
    do_something();
}

// ❌ Incorrect (K&R style)
if (condition) {
    do_something();
}
```

---

### Rule 41: Naming Conventions

**Severity:** 🟢 Minor  
**clang-tidy checks:** `readability-identifier-naming`

| Type | Convention | Example |
|------|------------|---------|
| Functions | `lower_case` | `process_data()` |
| Variables | `lower_case` | `buffer_size` |
| Constants | `UPPER_CASE` | `MAX_SIZE` |
| Macros | `UPPER_CASE` | `DEBUG_LOG()` |
| Types | `CamelCase` | `DataBuffer` |

---

### Rule 42: Always Use Braces

**Severity:** 🟢 Minor  
**clang-tidy checks:** `readability-braces-around-statements`

#### Description
Use braces even for single-statement blocks to prevent bugs when adding code.

```c
// ✅ GOOD
if (error)
{
    return -1;
}

// ❌ BAD
if (error)
    return -1;
```

---

### Rule 43: Simplify Boolean Expressions

**Severity:** 🟢 Minor  
**clang-tidy checks:** `readability-simplify-boolean-expr`

```c
// ❌ Redundant
if (flag == true)
if (ptr != NULL)

// ✅ Simplified  
if (flag)
if (ptr)
```

---

### Rule 44: Avoid Else After Return

**Severity:** 🟢 Minor  
**clang-tidy checks:** `readability-else-after-return`

```c
// ❌ Unnecessary else
if (error) {
    return -1;
} else {
    process();
}

// ✅ Cleaner
if (error) {
    return -1;
}
process();
```

---

### Rule 45: Use nullptr (C++)

**Severity:** 🟢 Minor  
**clang-tidy checks:** `modernize-use-nullptr`

```cpp
// ❌ C-style
char *p = NULL;

// ✅ C++ style
char *p = nullptr;
```

---

### Rule 46: Remove Unused Parameters

**Severity:** 🟢 Minor  
**clang-tidy checks:** `misc-unused-parameters`

#### Description
Remove or annotate unused function parameters.

```c
// ❌ Unused parameter
int process(int x, int unused) {
    return x;
}

// ✅ Removed
int process(int x) {
    return x;
}

// ✅ Or annotated (C++)
int process(int x, int /*unused*/) {
    return x;
}
```

---

## Suppression Guide

### Suppress Single Line
```c
risky_call();  // NOLINT(check-name)
```

### Suppress Block
```c
// NOLINTBEGIN(check-name)
legacy_code();
more_legacy();
// NOLINTEND(check-name)
```

### Suppress File
clang-tidy has no whole-file suppression comment. Wrap the file in `NOLINTBEGIN`/`NOLINTEND` (above), or leave the file out of the clang-tidy run.

**Always document why suppression is needed.**

---

## References

- [CERT C Coding Standard](https://wiki.sei.cmu.edu/confluence/display/c)
- [CWE Common Weakness Enumeration](https://cwe.mitre.org/)
- [clang-tidy Checks List](https://clang.llvm.org/extra/clang-tidy/checks/list.html)
- [MISRA C Guidelines](https://www.misra.org.uk/)
