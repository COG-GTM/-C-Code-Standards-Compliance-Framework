# Rule Reference

Complete reference documentation for all code standards rules.

## Overview

Rules are organized by severity:
- **Critical (Rule 20-29):** Safety/security issues that must be fixed
- **Major (Rule 30-39):** Quality issues that should be reviewed
- **Minor (Rule 40-49):** Style issues that improve maintainability

Each rule maps to one or more checks from the Java static-analysis toolchain:

| Tool | Role | Config File |
|------|------|-------------|
| **Checkstyle** | Formatting, naming, braces | `checkstyle.xml` |
| **PMD** | Bug patterns, dead code, design | `pmd-ruleset.xml` |
| **SpotBugs** | Bug, security & bytecode analysis | `spotbugs-exclude.xml` |

> **Toolchain note:** All analysis runs through Apache Maven (`pom.xml` is the project model).
> SpotBugs must run on **JDK 17** — it crashes on newer JDKs (e.g. JDK 26) with an
> `FBClassReader`/ASM error. Run Maven with `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn ...`.

---

## Critical Rules (Block Merge)

### Rule 20: Check All Return Values

**Severity:** 🔴 Critical
**Checks:** SpotBugs `RV_RETURN_VALUE_IGNORED_BAD_PRACTICE`, `RV_RETURN_VALUE_IGNORED_NO_SIDE_EFFECT`; PMD `CheckResultSet`

#### Description
All return values from methods that report status or produce a new value must be checked.
Ignoring a return value hides failures and produces silent, hard-to-trace bugs.

#### Commonly Ignored Return Values
- File status: `File.delete()`, `File.mkdir()`, `File.renameTo()`
- I/O: `InputStream.read(byte[])`, `InputStream.skip(long)`
- Immutable results: `String.trim()`, `String.replace()`, `BigDecimal.add()`
- Concurrency: `BlockingQueue.offer()`, `Condition.await(long, TimeUnit)`

#### Examples

```java
// ❌ BAD - Return values ignored
File tmp = new File("data.tmp");
tmp.delete();                 // Did it actually delete? We never know.
in.read(buffer);              // Bytes actually read is ignored.
input.trim();                 // trim() returns a NEW String; this is a no-op.

// ✅ GOOD - All return values checked
File tmp = new File("data.tmp");
if (!tmp.delete()) {
    throw new IOException("Failed to delete " + tmp);
}

int read = in.read(buffer);
if (read != buffer.length) {
    throw new IOException("Short read: expected " + buffer.length + ", got " + read);
}

String cleaned = input.trim();   // Use the returned value.
```

---

### Rule 21: Prevent Injection

**Severity:** 🔴 Critical
**Checks:** SpotBugs `SQL_INJECTION_JDBC`, `SQL_NONCONSTANT_STRING_PASSED_TO_EXECUTE`, `COMMAND_INJECTION`, `FORMAT_STRING_MANIPULATION`

> The C framework used Rule 21 for **buffer overflows**. Java has no raw buffers or `strcpy`,
> so the equivalent class of vulnerability is **injection** — building SQL, OS commands, or
> format strings from untrusted input.

#### Description
Never build SQL, shell commands, or format strings by concatenating untrusted input.
Use parameterized APIs so the data can never be interpreted as code.

#### Examples

```java
// ❌ BAD - SQL injection via string concatenation
String sql = "SELECT * FROM users WHERE name = '" + userName + "'";
Statement stmt = connection.createStatement();
ResultSet rs = stmt.executeQuery(sql);

// ✅ GOOD - Parameterized query
String sql = "SELECT * FROM users WHERE name = ?";
PreparedStatement ps = connection.prepareStatement(sql);
ps.setString(1, userName);
ResultSet rs = ps.executeQuery();
```

```java
// ❌ BAD - OS command injection
Runtime.getRuntime().exec("sh -c ping " + host);

// ✅ GOOD - No shell, arguments passed as an array
new ProcessBuilder("ping", "-c", "1", host).start();
```

**Why:** Injection is the most exploited vulnerability class in web software (CWE-89, CWE-78).

---

### Rule 22: Prevent Null Dereference

**Severity:** 🔴 Critical
**Checks:** SpotBugs `NP_NULL_ON_SOME_PATH`, `NP_NULL_PARAM_DEREF`, `NP_ALWAYS_NULL`; PMD `BrokenNullCheck`

#### Description
Always validate references before dereferencing them. A null dereference throws
`NullPointerException` and aborts the operation.

#### Examples

```java
// ❌ BAD - No null check
void process(Order order) {
    System.out.println(order.getTotal());  // NPE if order is null
}

// ✅ GOOD - Validate before use
void process(Order order) {
    if (order == null) {
        throw new IllegalArgumentException("order must not be null");
    }
    System.out.println(order.getTotal());
}

// ✅ BETTER - Make intent explicit with Objects.requireNonNull / Optional
void process(Order order) {
    Objects.requireNonNull(order, "order");
    System.out.println(order.getTotal());
}
```

---

### Rule 23: Prevent Resource Leaks

**Severity:** 🔴 Critical
**Checks:** PMD `CloseResource`; SpotBugs `OBL_UNSATISFIED_OBLIGATION`, `OS_OPEN_STREAM`

#### Description
Every `Closeable`/`AutoCloseable` (streams, readers, JDBC objects, sockets) must be closed
on **all** code paths, including exceptions. Use try-with-resources.

#### Examples

```java
// ❌ BAD - Leak on exception path
void readFile(Path path) throws IOException {
    InputStream in = Files.newInputStream(path);
    parse(in);          // If parse() throws, the stream is never closed.
    in.close();
}

// ✅ GOOD - try-with-resources guarantees close()
void readFile(Path path) throws IOException {
    try (InputStream in = Files.newInputStream(path)) {
        parse(in);      // Stream is closed automatically, even on exception.
    }
}
```

> **C → Java:** The C version used a `goto cleanup` block with `free()`/`fclose()`.
> Java's `try-with-resources` is the idiomatic equivalent and never forgets a path.

---

### Rule 24: Do Not Leak Internal References

**Severity:** 🔴 Critical
**Checks:** SpotBugs `EI_EXPOSE_REP`, `EI_EXPOSE_REP2`; PMD `MethodReturnsInternalArray`, `ArrayIsStoredDirectly`

> The C framework used Rule 24 for **use-after-free**. Java is garbage-collected, so the
> analogous correctness hazard is **exposing mutable internal state** — handing out a
> reference to an internal array/collection so callers can mutate the object behind its back.

#### Description
Do not return references to (or store references directly from) mutable internal state.
Return defensive copies (or immutable views) so callers cannot corrupt the object's invariants.

#### Examples

```java
// ❌ BAD - Exposes the internal array; callers can mutate it
public class Schedule {
    private final int[] slots;
    public Schedule(int[] slots) {
        this.slots = slots;             // Stores caller's array directly
    }
    public int[] getSlots() {
        return slots;                   // Hands out the internal array
    }
}

// ✅ GOOD - Defensive copies on the way in and out
public class Schedule {
    private final int[] slots;
    public Schedule(int[] slots) {
        this.slots = slots.clone();     // Copy in
    }
    public int[] getSlots() {
        return slots.clone();           // Copy out
    }
}
```

---

### Rule 25: No Dead Stores or Unwritten Fields

**Severity:** 🔴 Critical
**Checks:** SpotBugs `DLS_DEAD_LOCAL_STORE`, `UWF_UNWRITTEN_FIELD`, `NP_UNWRITTEN_FIELD`; PMD `UnusedAssignment`

> The C framework used Rule 25 for **uninitialized memory**. The JVM zero-initializes fields,
> so the corresponding bug is a **dead store** (a value computed then immediately overwritten or
> never read) or an **unwritten field** (read but never assigned, so always its default).

#### Description
Every value you assign should be read; every field you read should be written somewhere.
A dead store or an always-default field almost always signals a logic mistake.

#### Examples

```java
// ❌ BAD - Dead store: the first assignment is never used
int result = computeExpensive();   // Overwritten before it is ever read
result = fallback();
return result;

// ❌ BAD - Unwritten field: 'limit' is read but never assigned (always 0)
public class RateLimiter {
    private int limit;                  // Never set anywhere
    boolean allow(int count) {
        return count < limit;           // Always false
    }
}

// ✅ GOOD - Only meaningful assignments; field is written
public class RateLimiter {
    private final int limit;
    public RateLimiter(int limit) {
        this.limit = limit;
    }
    boolean allow(int count) {
        return count < limit;
    }
}
```

---

### Rule 26: Avoid Insecure APIs

**Severity:** 🔴 Critical
**Checks:** SpotBugs `PREDICTABLE_RANDOM`, `WEAK_MESSAGE_DIGEST_MD5`, `DES_USAGE`; PMD `InsecureCryptoIv`, `HardCodedCryptoKey`

#### Description
Do not use weak or predictable cryptographic primitives for security-sensitive operations.

#### Insecure vs Secure APIs

| Insecure | Secure | Notes |
|----------|--------|-------|
| `new java.util.Random()` | `java.security.SecureRandom` | Predictable PRNG |
| `MessageDigest.getInstance("MD5")` | `"SHA-256"` / `"SHA-512"` | MD5 is broken |
| `Cipher.getInstance("DES")` | `"AES/GCM/NoPadding"` | DES key is too short |
| Hard-coded key/IV | Generated `SecretKey` / random IV | Never embed secrets |

#### Examples

```java
// ❌ BAD - Predictable random used for a token
String token = Long.toHexString(new Random().nextLong());

// ✅ GOOD - Cryptographically strong randomness
byte[] bytes = new byte[32];
SecureRandom.getInstanceStrong().nextBytes(bytes);
String token = HexFormat.of().formatHex(bytes);
```

```java
// ❌ BAD - MD5 for integrity
MessageDigest md = MessageDigest.getInstance("MD5");

// ✅ GOOD - SHA-256
MessageDigest md = MessageDigest.getInstance("SHA-256");
```

---

## Major Rules (Requires Review)

### Rule 30: Avoid Narrowing Conversions

**Severity:** 🟡 Major
**Checks:** SpotBugs `ICAST_INTEGER_MULTIPLY_CAST_TO_LONG`, `ICAST_IDIV_CAST_TO_DOUBLE`; PMD `AvoidUsingShortType` (loose)

#### Description
Watch for arithmetic performed in a narrow type and then widened — the overflow/truncation
happens *before* the widening cast, so the result is wrong.

#### Examples

```java
// ❌ BAD - Multiplication overflows in int, THEN widens to long
long nanos = 1_000_000 * seconds;        // overflow when seconds is large
double ratio = (double) (hits / total);  // integer division, then widen → always *.0

// ✅ GOOD - Promote to the wide type before the operation
long nanos = 1_000_000L * seconds;       // long multiplication
double ratio = (double) hits / total;    // floating-point division
```

---

### Rule 31: Avoid Confusing / Misleading Methods

**Severity:** 🟡 Major
**Checks:** Checkstyle `OverloadMethodsDeclarationOrder`; SpotBugs `NM_METHOD_NAMING_CONVENTION`, `NM_CONFUSING`, `NM_VERY_CONFUSING`

> The C framework used Rule 31 for **inconsistent parameter names** between declaration and
> definition. Java has no separate declaration/definition, so the analogue is **confusing or
> inconsistent method naming/overloads** that mislead callers.

#### Description
Keep overloaded methods grouped together and avoid names that differ from another method only
by case, or that look like (but are not) an override.

#### Examples

```java
// ❌ BAD - 'compute' overloads split apart; confusing pair differing only by case
void compute(int x) { ... }
void process() { ... }
void Compute(int x) { ... }   // NM_CONFUSING vs compute(int)
void compute(long x) { ... }  // overload separated from the first

// ✅ GOOD - Overloads grouped, names distinct
void compute(int x) { ... }
void compute(long x) { ... }
void process() { ... }
```

---

### Rule 32: No Redundant Code

**Severity:** 🟡 Major
**Checks:** PMD `UnnecessaryReturn`, `EmptyControlStatement`, `UselessParentheses`; SpotBugs `RpC_REPEATED_CONDITIONAL_TEST`, `DB_DUPLICATE_BRANCHES`

#### Description
Remove duplicate, unreachable, or redundant code. Branches that are identical, conditions
tested twice, or empty statements usually indicate a logic error.

#### Examples

```java
// ❌ BAD - Duplicate branches and a repeated test
if (x > 0) {
    handle(x);
} else if (x > 0) {     // Can never be true here (RpC_REPEATED_CONDITIONAL_TEST)
    handle(x);          // ...and the branch is identical (DB_DUPLICATE_BRANCHES)
}

// ✅ GOOD
if (x > 0) {
    handle(x);
} else if (x < 0) {
    handleNegative(x);
}
```

---

### Rule 33: Prevent Infinite Loops

**Severity:** 🟡 Major
**Checks:** SpotBugs `IL_INFINITE_LOOP`, `IL_INFINITE_RECURSIVE_LOOP`

#### Description
Every loop and recursion must have a reachable exit condition.

#### Examples

```java
// ❌ BAD - Loop variable never changes; loop never exits
int i = 0;
while (i < 10) {
    process(i);          // i is never incremented
}

// ❌ BAD - Unconditional self-recursion
int size() {
    return size();       // IL_INFINITE_RECURSIVE_LOOP
}

// ✅ GOOD
for (int i = 0; i < 10; i++) {
    process(i);
}
```

---

### Rule 34: Thread Safety

**Severity:** 🟡 Major
**Checks:** SpotBugs `IS2_INCONSISTENT_SYNC`, `DC_DOUBLECHECK`; PMD `DoubleCheckedLocking`, `NonThreadSafeSingleton`

#### Description
Access shared mutable state consistently. Either synchronize every access to a field or none,
and never use the broken double-checked-locking idiom without a `volatile` field.

#### Examples

```java
// ❌ BAD - Broken double-checked locking (instance may be seen partially constructed)
private static Service instance;
static Service get() {
    if (instance == null) {
        synchronized (Service.class) {
            if (instance == null) {
                instance = new Service();   // DC_DOUBLECHECK
            }
        }
    }
    return instance;
}

// ✅ GOOD - Initialization-on-demand holder idiom (thread-safe, lazy)
private static class Holder {
    static final Service INSTANCE = new Service();
}
static Service get() {
    return Holder.INSTANCE;
}
```

---

### Rule 35: Performance Issues

**Severity:** 🟡 Major
**Checks:** PMD `AvoidInstantiatingObjectsInLoops`, `UseStringBufferForStringAppends`; SpotBugs `SBSC_USE_STRINGBUFFER_CONCATENATION`

#### Description
Avoid needless allocation. Do not build strings with `+=` in a loop, and hoist objects that do
not change out of loops.

#### Examples

```java
// ❌ BAD - Quadratic string building; new formatter every iteration
String out = "";
for (String row : rows) {
    SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd");  // re-created each loop
    out += fmt.format(now) + row + "\n";                       // O(n^2) concatenation
}

// ✅ GOOD - One StringBuilder, hoisted formatter
DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd");
StringBuilder out = new StringBuilder();
for (String row : rows) {
    out.append(fmt.format(today)).append(row).append('\n');
}
```

---

## Minor Rules (Style)

### Rule 40: Consistent Formatting & Braces

**Severity:** 🟢 Minor
**Checks:** Checkstyle `LeftCurly` (option `eol`), `RightCurly`

#### Description
This project uses the **standard Java (K&R / "end-of-line") brace style**: the opening brace
sits at the end of the line that starts the block.

```java
// ✅ Correct (Java standard, LeftCurly option=eol)
if (condition) {
    doSomething();
}

// ❌ Incorrect (Allman / brace on its own line)
if (condition)
{
    doSomething();
}
```

> **C → Java:** The C version mandated **Allman** braces. Idiomatic Java (and the Google Java
> Style Guide) puts the opening brace at the end of the line, so this rule is inverted for Java.

---

### Rule 41: Naming Conventions

**Severity:** 🟢 Minor
**Checks:** Checkstyle `MethodName`, `MemberName`, `LocalVariableName`, `ConstantName`, `TypeName`, `ParameterName`, `PackageName`

| Element | Convention | Example |
|---------|------------|---------|
| Methods | `lowerCamelCase` | `processData()` |
| Fields / variables / parameters | `lowerCamelCase` | `bufferSize` |
| Constants (`static final`) | `UPPER_SNAKE_CASE` | `MAX_SIZE` |
| Types (class/interface/enum) | `UpperCamelCase` | `DataBuffer` |
| Packages | `lower.case` | `com.example.standards` |

```java
// ❌ BAD
int Buffer_Size;
void ProcessData() { }
static final int maxSize = 100;

// ✅ GOOD
int bufferSize;
void processData() { }
static final int MAX_SIZE = 100;
```

---

### Rule 42: Always Use Braces

**Severity:** 🟢 Minor
**Checks:** Checkstyle `NeedBraces`

#### Description
Use braces even for single-statement blocks to prevent bugs when code is later added.

```java
// ✅ GOOD
if (error) {
    return -1;
}

// ❌ BAD
if (error)
    return -1;
```

---

### Rule 43: Simplify Boolean Expressions

**Severity:** 🟢 Minor
**Checks:** Checkstyle `SimplifyBooleanExpression`, `SimplifyBooleanReturn`

```java
// ❌ Redundant
if (flag == true) { ... }
if (isReady() == false) { ... }

boolean ok;
if (x > 0) {
    ok = true;
} else {
    ok = false;
}

// ✅ Simplified
if (flag) { ... }
if (!isReady()) { ... }

boolean ok = x > 0;
```

---

### Rule 44: Avoid Else After Return

**Severity:** 🟢 Minor
**Checks:** *Advisory — no direct automated check in this toolchain.* Enforce in code review.

> Neither PMD 6.55, Checkstyle 10.12.7, nor SpotBugs 4.8.3 ships a rule that exactly matches
> "else after return," so this rule is **documented as advisory** rather than tool-enforced.

```java
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

### Rule 45: Avoid Returning Null

**Severity:** 🟢 Minor
**Checks:** SpotBugs `PZLA_PREFER_ZERO_LENGTH_ARRAYS`; PMD `ReturnEmptyCollectionRatherThanNull`

> The C++ rule "use `nullptr` instead of `NULL`" has no meaning in Java. The Java analogue is to
> **avoid returning `null`** for arrays/collections — return an empty array/collection (or
> `Optional`) so callers never need a null check.

#### Description
Returning `null` instead of an empty array or collection forces every caller to null-check and
invites `NullPointerException`.

```java
// ❌ BAD - Forces null checks on every caller
List<Order> findOrders(String userId) {
    if (!exists(userId)) {
        return null;
    }
    return orders;
}

// ✅ GOOD - Empty collection communicates "none"
List<Order> findOrders(String userId) {
    if (!exists(userId)) {
        return Collections.emptyList();
    }
    return orders;
}

// ✅ GOOD - Zero-length array instead of null
String[] tags() {
    return (tags == null) ? new String[0] : tags.clone();
}
```

---

### Rule 46: Remove Unused Parameters & Members

**Severity:** 🟢 Minor
**Checks:** PMD `UnusedFormalParameter` (set `checkAll=true`), `UnusedPrivateField`, `UnusedLocalVariable`

#### Description
Remove unused method parameters, private fields, and local variables. Dead members confuse
readers and often hint at incomplete implementations.

```java
// ❌ BAD - Unused parameter and unused local
int process(int x, int unused) {
    int scratch = compute();   // never read
    return x;
}

// ✅ GOOD
int process(int x) {
    return x;
}
```

---

## Suppression Guide

Use a suppression only when a finding is a verified false positive, and **always add a comment
explaining why**.

### Checkstyle
```java
// CHECKSTYLE:OFF
legacyGeneratedCode();
// CHECKSTYLE:ON

// Or, with SuppressWarningsFilter enabled in checkstyle.xml:
@SuppressWarnings("checkstyle:MethodName")
void Legacy_Name() { }
```

### PMD
```java
@SuppressWarnings("PMD.UnusedFormalParameter")
int process(int x, int callbackArg) { return x; }

someCall();  // NOPMD - intentional, see TICKET-123
```

### SpotBugs
```java
import edu.umd.cs.findbugs.annotations.SuppressFBWarnings;

@SuppressFBWarnings(value = "EI_EXPOSE_REP",
                    justification = "Returned array is documented as caller-owned")
public int[] getSlots() {
    return slots;
}
```
(The `@SuppressFBWarnings` annotation comes from `com.github.spotbugs:spotbugs-annotations`.)

**Always document why a suppression is needed; prefer fixing the issue over suppressing it.**

---

## References

- [SEI CERT Oracle Coding Standard for Java](https://wiki.sei.cmu.edu/confluence/display/java)
- [CWE - Common Weakness Enumeration](https://cwe.mitre.org/)
- [SpotBugs Bug Descriptions](https://spotbugs.readthedocs.io/en/stable/bugDescriptions.html)
- [PMD Java Rule Reference](https://docs.pmd-code.org/latest/pmd_rules_java.html)
- [Checkstyle Checks](https://checkstyle.org/checks.html)
- [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html)
