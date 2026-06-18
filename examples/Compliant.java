package com.example.standards;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;

/**
 * Examples of code that passes all safety-critical checks.
 *
 * <p>This file is the mirror image of {@link Violations}: every method shows the
 * <em>correct</em> Java pattern for a rule in the Rule 20-46 catalog. It must
 * stay clean under the framework's full toolchain — zero Checkstyle, zero PMD
 * and zero SpotBugs findings.</p>
 *
 * <p>The C original demonstrated the same rules with fopen/malloc/goto-cleanup;
 * the Java port uses try-with-resources, defensive copies, SecureRandom and the
 * other idioms the analyzers expect.</p>
 */
public class Compliant {

    /** Default token length used by the SecureRandom example (Rule 41: UPPER_SNAKE). */
    private static final int DEFAULT_TOKEN_LENGTH = 16;

    /** A single shared, reused SecureRandom (Rule 26). */
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    /** Internal state guarded by defensive copies (Rule 24). */
    private final int[] data;

    /** Mutable state mutated only under synchronization (Rule 34). */
    private int counter;

    /**
     * Creates an instance, defensively copying the supplied array.
     *
     * <p>Rule 24 compliant: stores a copy, never the caller's reference.</p>
     *
     * @param values seed values; a null argument is treated as empty
     */
    public Compliant(int[] values) {
        this.data = (values == null) ? new int[0] : values.clone();
    }

    /* ======================================================================
     * CRITICAL (Rule 20-26)
     * ====================================================================== */

    /**
     * Rule 20 compliant: the return value is captured and acted upon.
     *
     * @param file file to create
     * @return true if a new file was created
     * @throws IOException if the file cannot be created
     */
    public boolean rule20CheckReturnValue(File file) throws IOException {
        boolean created = file.createNewFile();
        if (!created) {
            System.out.println("file already existed: " + file.getName());
        }
        return created;
    }

    /**
     * Rule 22 compliant: validate before dereferencing.
     *
     * @param value possibly-null input
     * @return the length, or 0 when the input is null
     */
    public int rule22NullSafe(String value) {
        if (value == null) {
            return 0;
        }
        return value.length();
    }

    /**
     * Rule 23 compliant: try-with-resources guarantees the stream is closed.
     *
     * @param path file to read one byte from
     * @return the first byte, or -1 at end of stream
     * @throws IOException if reading fails
     */
    public int rule23CloseResource(String path) throws IOException {
        try (FileInputStream in = new FileInputStream(path)) {
            return in.read();
        }
    }

    /**
     * Rule 24 compliant: returns a defensive copy, never the internal array.
     *
     * @return a copy of the internal data
     */
    public int[] rule24SafeArrayCopy() {
        return data.clone();
    }

    /**
     * Rule 25 compliant: every local is written once and then read.
     *
     * @param input seed value
     * @return the computed result
     */
    public int rule25NoDeadStore(int input) {
        int result = input * 2;
        return result;
    }

    /**
     * Rule 26 compliant: SecureRandom for unpredictable token bytes.
     *
     * @return a freshly generated random token
     */
    public byte[] rule26SecureRandomToken() {
        byte[] token = new byte[DEFAULT_TOKEN_LENGTH];
        SECURE_RANDOM.nextBytes(token);
        return token;
    }

    /* ======================================================================
     * MAJOR (Rule 30-35)
     * ====================================================================== */

    /**
     * Rule 30 compliant: range-check before narrowing long to int.
     *
     * @param value value to narrow
     * @return the value as an int
     */
    public int rule30SafeNarrowing(long value) {
        if (value > Integer.MAX_VALUE || value < Integer.MIN_VALUE) {
            throw new IllegalArgumentException("value out of int range: " + value);
        }
        return (int) value;
    }

    /**
     * Rule 31 compliant: overloaded methods are declared adjacently.
     *
     * @param value int input
     * @return a description
     */
    public String describe(int value) {
        return "int:" + value;
    }

    /**
     * Rule 31 compliant: second overload kept next to the first.
     *
     * @param value String input
     * @return a description
     */
    public String describe(String value) {
        return "string:" + value;
    }

    /**
     * Rule 32 compliant: no redundant returns, parentheses or dead branches.
     *
     * @param x input
     * @return x incremented
     */
    public int rule32CleanCode(int x) {
        return x + 1;
    }

    /**
     * Rule 33 compliant: the loop has a clear termination condition.
     *
     * @param count number of iterations
     * @return the sum 0..count-1
     */
    public int rule33TerminatingLoop(int count) {
        int sum = 0;
        for (int i = 0; i < count; i++) {
            sum += i;
        }
        return sum;
    }

    /**
     * Rule 34 compliant: shared state mutated only under synchronization.
     *
     * @return the incremented counter value
     */
    public synchronized int rule34ThreadSafeIncrement() {
        counter++;
        return counter;
    }

    /**
     * Rule 35 compliant: StringBuilder, with no allocation inside the loop.
     *
     * @param items strings to join
     * @return the concatenation of all items
     */
    public String rule35EfficientConcat(String[] items) {
        StringBuilder builder = new StringBuilder();
        for (String item : items) {
            builder.append(item);
        }
        return builder.toString();
    }

    /* ======================================================================
     * MINOR (Rule 40-46)
     *
     * Rule 40 (eol braces), Rule 41 (naming) and Rule 42 (always braces) are
     * demonstrated implicitly by the style of every method above.
     * ====================================================================== */

    /**
     * Rule 43 compliant: the boolean expression is already in its simplest form.
     *
     * @param value input
     * @return whether the value is positive
     */
    public boolean rule43SimpleBoolean(int value) {
        return value > 0;
    }

    /**
     * Rule 44 compliant: no else after a return.
     *
     * @param error whether an error occurred
     * @return -1 on error, otherwise 0
     */
    public int rule44NoElseAfterReturn(boolean error) {
        if (error) {
            return -1;
        }
        return 0;
    }

    /**
     * Rule 45 compliant: returns an empty array instead of null.
     *
     * @param empty whether to return the empty case
     * @return an array that is never null
     */
    public int[] rule45ReturnEmptyArray(boolean empty) {
        if (empty) {
            return new int[0];
        }
        return new int[] {1, 2, 3};
    }

    /**
     * Rule 46 compliant: every parameter is used.
     *
     * @param items items to collect
     * @param limit maximum number of items to keep
     * @return a bounded copy of the items
     */
    public List<String> rule46AllParametersUsed(List<String> items, int limit) {
        List<String> result = new ArrayList<>();
        for (String item : items) {
            if (result.size() >= limit) {
                break;
            }
            result.add(item);
        }
        return result;
    }
}
