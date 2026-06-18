---
trigger: always_on
---

# Java Safety-Critical Code Standards

> Copy this file to `.windsurf/rules/java-safety-critical-rules.md` in your project.

## Overview

When reviewing Java code, enforce these safety-critical rules and classify violations by severity. Report violations with their rule ID for traceability.

The rules are enforced by the Java static-analysis toolchain, orchestrated by Maven:
- **Checkstyle** — formatting, naming, braces
- **PMD + SpotBugs** — bug, security, and static analysis

> **JDK note:** run the analysis on **JDK 17**. SpotBugs crashes on newer JDKs (e.g. JDK 26) with an
> `FBClassReader`/ASM error. Use `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn ...`.

## Severity Levels

| Level | Icon | Action | Description |
|-------|------|--------|-------------|
| **Critical** | 🔴 | Block merge | Safety/security risk - crashes, vulnerabilities, data corruption |
| **Major** | 🟡 | Require review | Quality issue - potential bugs, edge case failures |
| **Minor** | 🟢 | Warn only | Style issue - readability, maintainability |

---

## Critical Rules (Block Merge) 🔴

### Rule 20: Check All Return Values

All return values from methods that report status or produce a new value MUST be checked.

**Commonly ignored:** `File.delete()`, `File.mkdir()`, `InputStream.read(byte[])`, `String.trim()`/`replace()` (return new strings), `BlockingQueue.offer()`.

```java
// ❌ VIOLATION - Critical (Rule 20)
File tmp = new File("data.tmp");
tmp.delete();              // Return value ignored - did it work?
input.trim();              // trim() returns a NEW String; this is a no-op

// ✅ COMPLIANT
File tmp = new File("data.tmp");
if (!tmp.delete()) {
    throw new IOException("Failed to delete " + tmp);
}
String cleaned = input.trim();
```

**Why:** Unchecked return values hide failures, leading to silent data corruption or security issues.

---

### Rule 21: Prevent Injection

Never build SQL, OS commands, or format strings from untrusted input. Use parameterized APIs.

```java
// ❌ VIOLATION - Critical (Rule 21)
String sql = "SELECT * FROM users WHERE name = '" + userName + "'";
stmt.executeQuery(sql);
Runtime.getRuntime().exec("sh -c ping " + host);

// ✅ COMPLIANT
PreparedStatement ps = connection.prepareStatement(
        "SELECT * FROM users WHERE name = ?");
ps.setString(1, userName);
ps.executeQuery();

new ProcessBuilder("ping", "-c", "1", host).start();
```

**Why:** Injection is the most exploited vulnerability class (CWE-89, CWE-78). It replaces the C
framework's "buffer overflow" rule — Java has no raw buffers, but it has injection.

---

### Rule 22: Prevent Null Dereference

Always validate references before dereferencing them.

```java
// ❌ VIOLATION - Critical (Rule 22)
void process(Order order) {
    System.out.println(order.getTotal());  // NPE if order is null
}

// ✅ COMPLIANT
void process(Order order) {
    Objects.requireNonNull(order, "order");
    System.out.println(order.getTotal());
}
```

**Why:** Null dereference throws `NullPointerException`, aborting the operation and enabling DoS.

---

### Rule 23: Close All Resources

Every `AutoCloseable` (streams, readers, JDBC objects, sockets) must be closed on all paths. Use try-with-resources.

```java
// ❌ VIOLATION - Critical (Rule 23) - leak on exception path
InputStream in = Files.newInputStream(path);
parse(in);            // if parse() throws, the stream is never closed
in.close();

// ✅ COMPLIANT - try-with-resources guarantees close()
try (InputStream in = Files.newInputStream(path)) {
    parse(in);
}
```

**Why:** Leaked resources (file handles, connections) degrade and eventually crash long-running systems.
This replaces the C framework's `goto cleanup` / `free()` pattern.

---

### Rule 24: Do Not Leak Internal References

Do not return (or store) references to mutable internal state. Return defensive copies.

```java
// ❌ VIOLATION - Critical (Rule 24)
public class Schedule {
    private final int[] slots;
    public Schedule(int[] slots) { this.slots = slots; }   // stores caller's array
    public int[] getSlots() { return slots; }              // hands out internal array
}

// ✅ COMPLIANT
public class Schedule {
    private final int[] slots;
    public Schedule(int[] slots) { this.slots = slots.clone(); }
    public int[] getSlots() { return slots.clone(); }
}
```

**Why:** Exposing internal state lets callers corrupt invariants behind the object's back. This is
the GC-language analogue of the C framework's "use-after-free" rule.

---

### Rule 25: No Dead Stores or Unwritten Fields

Every value assigned should be read; every field read should be written somewhere.

```java
// ❌ VIOLATION - Critical (Rule 25)
int result = computeExpensive();   // dead store: overwritten before it is read
result = fallback();
return result;

public class RateLimiter {
    private int limit;                 // unwritten field: always 0
    boolean allow(int n) { return n < limit; }  // always false
}

// ✅ COMPLIANT
public class RateLimiter {
    private final int limit;
    public RateLimiter(int limit) { this.limit = limit; }
    boolean allow(int n) { return n < limit; }
}
```

**Why:** A dead store or always-default field almost always signals a logic mistake. This replaces
the C framework's "uninitialized memory" rule (the JVM zero-initializes, so the bug shifts form).

---

### Rule 26: Avoid Insecure APIs

Do not use weak or predictable cryptographic primitives.

| Insecure | Secure Alternative |
|----------|-------------------|
| `new java.util.Random()` | `java.security.SecureRandom` |
| `MessageDigest.getInstance("MD5")` | `"SHA-256"` / `"SHA-512"` |
| `Cipher.getInstance("DES")` | `"AES/GCM/NoPadding"` |
| Hard-coded key/IV | generated `SecretKey` / random IV |

```java
// ❌ VIOLATION - Critical (Rule 26)
String token = Long.toHexString(new Random().nextLong());  // predictable

// ✅ COMPLIANT
byte[] bytes = new byte[32];
SecureRandom.getInstanceStrong().nextBytes(bytes);
String token = HexFormat.of().formatHex(bytes);
```

---

## Major Rules (Requires Review) 🟡

### Rule 30: Avoid Narrowing Conversions

Promote to the wide type *before* arithmetic, or overflow happens before the widening cast.

```java
// ❌ VIOLATION - Major (Rule 30)
long nanos = 1_000_000 * seconds;        // int multiply overflows, THEN widens
double ratio = (double) (hits / total);  // integer divide, THEN widens → always *.0

// ✅ COMPLIANT
long nanos = 1_000_000L * seconds;       // long multiply
double ratio = (double) hits / total;    // floating-point divide
```

---

### Rule 31: Avoid Confusing / Misleading Methods

Group overloads together; avoid names that differ only by case or that look like (but aren't) overrides.

```java
// ❌ VIOLATION - Major (Rule 31)
void compute(int x) { }
void process() { }
void Compute(int x) { }   // confusing vs compute(int)
void compute(long x) { } // overload separated from the first

// ✅ COMPLIANT
void compute(int x) { }
void compute(long x) { }
void process() { }
```

> Replaces the C framework's "consistent parameter names" rule (Java has no separate decl/def).

---

### Rule 32: No Redundant Code

Remove duplicate branches, repeated conditions, and unreachable code.

```java
// ❌ VIOLATION - Major (Rule 32)
if (x > 0) {
    handle(x);
} else if (x > 0) {   // can never be true here; identical branch
    handle(x);
}

// ✅ COMPLIANT
if (x > 0) {
    handle(x);
} else if (x < 0) {
    handleNegative(x);
}
```

---

### Rule 33: Prevent Infinite Loops

Every loop and recursion must have a reachable exit condition.

```java
// ❌ VIOLATION - Major (Rule 33)
int i = 0;
while (i < 10) {
    process(i);       // i is never incremented
}

// ✅ COMPLIANT
for (int i = 0; i < 10; i++) {
    process(i);
}
```

---

### Rule 34: Thread Safety

Access shared mutable state consistently; avoid broken double-checked locking.

```java
// ❌ VIOLATION - Major (Rule 34) - broken double-checked locking
private static Service instance;
static Service get() {
    if (instance == null) {
        synchronized (Service.class) {
            if (instance == null) {
                instance = new Service();   // may publish a partial object
            }
        }
    }
    return instance;
}

// ✅ COMPLIANT - initialization-on-demand holder
private static class Holder {
    static final Service INSTANCE = new Service();
}
static Service get() {
    return Holder.INSTANCE;
}
```

---

### Rule 35: Avoid Performance Issues

Avoid needless allocation; use `StringBuilder` and hoist invariants out of loops.

```java
// ❌ VIOLATION - Major (Rule 35)
String out = "";
for (String row : rows) {
    out += row + "\n";          // O(n^2) string concatenation
}

// ✅ COMPLIANT
StringBuilder out = new StringBuilder();
for (String row : rows) {
    out.append(row).append('\n');
}
```

---

## Minor Rules (Style Warnings) 🟢

### Rule 40: Consistent Brace Style

Use the standard Java end-of-line (K&R) brace style: opening brace at the end of the line.

```java
// ✅ COMPLIANT (Java standard)
if (condition) {
    doSomething();
}

// ❌ VIOLATION - Minor (Rule 40) - Allman / brace on its own line
if (condition)
{
    doSomething();
}
```

> Inverted from the C framework, which mandated Allman braces. Idiomatic Java puts the brace on the same line.

---

### Rule 41: Naming Conventions

- **Methods / variables / parameters:** `lowerCamelCase`
- **Constants (`static final`):** `UPPER_SNAKE_CASE`
- **Types (class/interface/enum):** `UpperCamelCase`
- **Packages:** `lower.case`

```java
// ❌ VIOLATION - Minor (Rule 41)
int Buffer_Size;
void ProcessData() { }
static final int maxSize = 100;

// ✅ COMPLIANT
int bufferSize;
void processData() { }
static final int MAX_SIZE = 100;
```

---

### Rule 42: Always Use Braces

Use braces even for single-statement blocks.

```java
// ❌ VIOLATION - Minor (Rule 42)
if (error)
    return -1;

// ✅ COMPLIANT
if (error) {
    return -1;
}
```

---

### Rule 43: Simplify Boolean Expressions

Avoid redundant boolean comparisons.

```java
// ❌ VIOLATION - Minor (Rule 43)
if (flag == true) { }
if (isReady() == false) { }

// ✅ COMPLIANT
if (flag) { }
if (!isReady()) { }
```

---

### Rule 44: Avoid Else After Return

Remove unnecessary else after return. (Advisory — no direct automated check in this toolchain.)

```java
// ❌ VIOLATION - Minor (Rule 44)
if (error) {
    return -1;
} else {
    process();
}

// ✅ COMPLIANT
if (error) {
    return -1;
}
process();
```

---

### Rule 45: Avoid Returning Null

Return an empty collection/array (or `Optional`) instead of `null`.

```java
// ❌ VIOLATION - Minor (Rule 45)
List<Order> findOrders(String userId) {
    if (!exists(userId)) {
        return null;
    }
    return orders;
}

// ✅ COMPLIANT
List<Order> findOrders(String userId) {
    if (!exists(userId)) {
        return Collections.emptyList();
    }
    return orders;
}
```

> Replaces the C++ "use nullptr instead of NULL" rule, which has no meaning in Java.

---

### Rule 46: Remove Unused Parameters & Members

Remove unused method parameters, private fields, and local variables.

```java
// ❌ VIOLATION - Minor (Rule 46)
int process(int x, int unused) {
    int scratch = compute();   // never read
    return x;
}

// ✅ COMPLIANT
int process(int x) {
    return x;
}
```

---

## Validation Commands

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Style check (Checkstyle)
mvn checkstyle:check

# Static analysis (PMD + SpotBugs)
mvn pmd:check
mvn spotbugs:check

# Run validation script (wraps the Maven goals)
./scripts/validate.sh src/
```

## Suppressing Warnings

```java
// Checkstyle (with SuppressWarningsFilter enabled in checkstyle.xml)
@SuppressWarnings("checkstyle:MethodName")
void Legacy_Name() { }

// PMD
@SuppressWarnings("PMD.UnusedFormalParameter")
int process(int x, int callbackArg) { return x; }
someCall();  // NOPMD - intentional, see TICKET-123

// SpotBugs (from com.github.spotbugs:spotbugs-annotations)
@SuppressFBWarnings(value = "EI_EXPOSE_REP", justification = "array is caller-owned")
public int[] getSlots() { return slots; }
```

**Always add a comment explaining why suppression is necessary.**

---

## References

- [SEI CERT Oracle Coding Standard for Java](https://wiki.sei.cmu.edu/confluence/display/java)
- [CWE - Common Weakness Enumeration](https://cwe.mitre.org/)
- [SpotBugs Bug Descriptions](https://spotbugs.readthedocs.io/en/stable/bugDescriptions.html)
- [PMD Java Rule Reference](https://docs.pmd-code.org/latest/pmd_rules_java.html)
- [Checkstyle Checks](https://checkstyle.org/checks.html)
- [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html)
