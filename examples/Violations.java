package com.example.standards;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Examples of code violations for testing Checkstyle / PMD / SpotBugs detection.
 *
 * <p>WARNING: This file intentionally contains violations. DO NOT use these
 * patterns in production. Each method demonstrates a specific rule violation,
 * keyed to the Rule 20-46 catalog. The C originals used clang-tidy; this Java
 * port maps each rule to the equivalent Checkstyle / PMD / SpotBugs finding.</p>
 *
 * <p>Run the analyzers (see README / scripts/validate.sh) to see the detected
 * warnings. The code compiles cleanly with javac: violations are bad
 * <em>patterns</em>, not syntax errors.</p>
 */
public class Violations {

    /* Fields used by the rule examples below. */
    private int[] data;
    private String neverWritten;
    private int unusedField = 7;
    private int BadField = 5;
    private Helper helper;
    private static Violations instance;

    /* ======================================================================
     * CRITICAL VIOLATIONS (Rule 20-26) - these should block merges in CI/CD
     * ====================================================================== */

    /**
     * Rule 20 VIOLATION - Critical: return values ignored.
     *
     * <p>Maps to SpotBugs RV_RETURN_VALUE_IGNORED_NO_SIDE_EFFECT (trim) and
     * RV_RETURN_VALUE_IGNORED_BAD_PRACTICE (File.delete).</p>
     */
    void rule20IgnoredReturnValue(String input) {
        // VIOLATION - Critical (Rule 20): result of a side-effect-free call discarded
        input.trim();
        // VIOLATION - Critical (Rule 20): boolean status of delete() ignored
        new File("scratch.txt").delete();
    }

    /**
     * Rule 20 VIOLATION - Critical: ResultSet navigation result not checked.
     *
     * <p>Maps to PMD CheckResultSet.</p>
     */
    void rule20UncheckedResultSet(Connection conn) throws SQLException {
        Statement stmt = conn.createStatement();
        ResultSet rs = stmt.executeQuery("SELECT name FROM users");
        // VIOLATION - Critical (Rule 20): return value of next() ignored
        rs.next();
        System.out.println(rs.getString(1));
    }

    /**
     * Rule 21 VIOLATION - Critical: SQL injection via string concatenation.
     *
     * <p>Was C buffer overflow; the Java analogue is injection. Maps to SpotBugs
     * SQL_NONCONSTANT_STRING_PASSED_TO_EXECUTE.</p>
     */
    ResultSet rule21SqlInjection(Connection conn, String userInput) throws SQLException {
        Statement stmt = conn.createStatement();
        // VIOLATION - Critical (Rule 21): untrusted input concatenated into SQL
        return stmt.executeQuery("SELECT * FROM users WHERE name = '" + userInput + "'");
    }

    /**
     * Rule 22 VIOLATION - Critical: null pointer dereference.
     *
     * <p>Maps to SpotBugs NP_ALWAYS_NULL.</p>
     */
    int rule22NullDereference() {
        String value = null;
        // VIOLATION - Critical (Rule 22): dereference of a value that is always null
        return value.length();
    }

    /**
     * Rule 22 VIOLATION - Critical: broken null check.
     *
     * <p>Maps to PMD BrokenNullCheck.</p>
     */
    boolean rule22BrokenNullCheck(String text) {
        // VIOLATION - Critical (Rule 22): dereferences text on the branch where it is null
        if (text == null && text.length() > 0) {
            return true;
        }
        return false;
    }

    /**
     * Rule 23 VIOLATION - Critical: resource leak (stream never closed).
     *
     * <p>Maps to PMD CloseResource and SpotBugs OS_OPEN_STREAM.</p>
     */
    void rule23ResourceLeak(String path) throws IOException {
        // VIOLATION - Critical (Rule 23): FileInputStream is opened but never closed
        FileInputStream in = new FileInputStream(path);
        int first = in.read();
        System.out.println(first);
    }

    /**
     * Rule 24 VIOLATION - Critical: stores an external array reference directly.
     *
     * <p>Was C use-after-free; the Java analogue is leaking internal references.
     * Maps to PMD ArrayIsStoredDirectly and SpotBugs EI_EXPOSE_REP2.</p>
     */
    void rule24StoreArrayReference(int[] input) {
        // VIOLATION - Critical (Rule 24): caller keeps a live handle to internal state
        this.data = input;
    }

    /**
     * Rule 24 VIOLATION - Critical: returns the internal array reference.
     *
     * <p>Maps to PMD MethodReturnsInternalArray and SpotBugs EI_EXPOSE_REP.</p>
     */
    int[] rule24ExposeArrayReference() {
        // VIOLATION - Critical (Rule 24): exposes mutable internal array to callers
        return this.data;
    }

    /**
     * Rule 25 VIOLATION - Critical: dead local store.
     *
     * <p>Was C uninitialized memory; the Java analogue is a dead/overwritten
     * store. Maps to SpotBugs DLS_DEAD_LOCAL_STORE and PMD UnusedAssignment.</p>
     */
    int rule25DeadStore(int input) {
        // VIOLATION - Critical (Rule 25): this assignment is overwritten before use
        int result = input * 2;
        result = input * 3;
        return result;
    }

    /**
     * Rule 25 VIOLATION - Critical: unwritten field read as always-null.
     *
     * <p>Maps to SpotBugs UWF_UNWRITTEN_FIELD / NP_UNWRITTEN_FIELD.</p>
     */
    String rule25UnwrittenField() {
        // VIOLATION - Critical (Rule 25): field is never assigned, so this is always null
        return neverWritten;
    }

    /**
     * Rule 26 VIOLATION - Critical: insecure crypto (hard-coded key + static IV).
     *
     * <p>Maps to PMD HardCodedCryptoKey and InsecureCryptoIv.</p>
     */
    void rule26InsecureCrypto() throws GeneralSecurityException {
        // VIOLATION - Critical (Rule 26): hard-coded encryption key
        byte[] keyBytes = "1234567890123456".getBytes(StandardCharsets.UTF_8);
        SecretKeySpec key = new SecretKeySpec(keyBytes, "AES");
        // VIOLATION - Critical (Rule 26): hard-coded / static initialization vector
        IvParameterSpec iv = new IvParameterSpec(
                new byte[] {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15});
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(Cipher.ENCRYPT_MODE, key, iv);
    }

    /**
     * Rule 26 VIOLATION - Critical: predictable RNG used where security matters.
     *
     * <p>Educational analogue of C's insecure rand(); SecureRandom should be
     * used instead of java.util.Random for tokens.</p>
     */
    int rule26PredictableRandom() {
        // VIOLATION - Critical (Rule 26): java.util.Random is predictable, not secure
        Random rng = new Random();
        return rng.nextInt();
    }

    /* ======================================================================
     * MAJOR VIOLATIONS (Rule 30-35) - require review, may not block merges
     * ====================================================================== */

    /**
     * Rule 30 VIOLATION - Major: integer multiplication widened to long.
     *
     * <p>Maps to SpotBugs ICAST_INTEGER_MULTIPLY_CAST_TO_LONG.</p>
     */
    long rule30NarrowingMultiply(int days) {
        // VIOLATION - Major (Rule 30): multiply happens in int (overflow) then widened
        long millis = days * 24 * 60 * 60 * 1000;
        return millis;
    }

    /**
     * Rule 30 VIOLATION - Major: use of the short type.
     *
     * <p>Maps to PMD AvoidUsingShortType.</p>
     */
    short rule30ShortType(short value) {
        // VIOLATION - Major (Rule 30): short offers no real benefit and invites narrowing bugs
        return value;
    }

    /**
     * Rule 31 VIOLATION - Major: overloaded methods not declared together.
     *
     * <p>Maps to Checkstyle OverloadMethodsDeclarationOrder: the two
     * {@code process} overloads are separated by an unrelated method.</p>
     */
    void process(int value) {
        System.out.println(value);
    }

    void unrelatedMethodBetweenOverloads() {
        System.out.println("separator");
    }

    // VIOLATION - Major (Rule 31): this overload is split from process(int) above
    void process(String value) {
        System.out.println(value);
    }

    /**
     * Rule 32 VIOLATION - Major: useless parentheses.
     *
     * <p>Maps to PMD UselessParentheses.</p>
     */
    int rule32UselessParentheses(int x) {
        // VIOLATION - Major (Rule 32): redundant parentheses around the expression
        return ((x + 1));
    }

    /**
     * Rule 32 VIOLATION - Major: unnecessary return statement.
     *
     * <p>Maps to PMD UnnecessaryReturn.</p>
     */
    void rule32UnnecessaryReturn() {
        System.out.println("done");
        // VIOLATION - Major (Rule 32): redundant return at the end of a void method
        return;
    }

    /**
     * Rule 32 VIOLATION - Major: empty control statement.
     *
     * <p>Maps to PMD EmptyControlStatement.</p>
     */
    void rule32EmptyControl(int x) {
        // VIOLATION - Major (Rule 32): empty if block does nothing
        if (x > 0) {
        }
    }

    /**
     * Rule 32 VIOLATION - Major: duplicated if/else branches.
     *
     * <p>Maps to SpotBugs DB_DUPLICATE_BRANCHES.</p>
     */
    int rule32DuplicateBranches(boolean flag, int a) {
        // VIOLATION - Major (Rule 32): both branches are identical
        if (flag) {
            return a + 1;
        } else {
            return a + 1;
        }
    }

    /**
     * Rule 33 VIOLATION - Major: infinite recursion.
     *
     * <p>Maps to SpotBugs IL_INFINITE_RECURSIVE_LOOP.</p>
     */
    int rule33InfiniteRecursion(int n) {
        // VIOLATION - Major (Rule 33): always recurses with the same argument
        return rule33InfiniteRecursion(n);
    }

    /**
     * Rule 33 VIOLATION - Major: loop that can never terminate.
     *
     * <p>Maps to SpotBugs IL_INFINITE_LOOP.</p>
     */
    void rule33InfiniteLoop() {
        int i = 0;
        // VIOLATION - Major (Rule 33): loop variable is never advanced
        while (i < 10) {
            System.out.println(i);
        }
    }

    /**
     * Rule 34 VIOLATION - Major: double-checked locking.
     *
     * <p>Maps to PMD DoubleCheckedLocking and SpotBugs DC_DOUBLECHECK.</p>
     */
    Helper rule34DoubleCheckedLocking() {
        // VIOLATION - Major (Rule 34): non-volatile double-checked locking is broken
        if (helper == null) {
            synchronized (this) {
                if (helper == null) {
                    helper = new Helper();
                }
            }
        }
        return helper;
    }

    /**
     * Rule 34 VIOLATION - Major: non-thread-safe lazy singleton.
     *
     * <p>Maps to PMD NonThreadSafeSingleton.</p>
     */
    static Violations rule34NonThreadSafeSingleton() {
        // VIOLATION - Major (Rule 34): unsynchronized lazy init races across threads
        if (instance == null) {
            instance = new Violations();
        }
        return instance;
    }

    /**
     * Rule 35 VIOLATION - Major: String concatenation inside a loop.
     *
     * <p>Maps to PMD UseStringBufferForStringAppends and SpotBugs
     * SBSC_USE_STRINGBUFFER_CONCATENATION.</p>
     */
    String rule35StringConcatInLoop(String[] items) {
        String result = "";
        // VIOLATION - Major (Rule 35): builds a throwaway String every iteration
        for (String item : items) {
            result = result + item;
        }
        return result;
    }

    /**
     * Rule 35 VIOLATION - Major: object instantiation inside a loop.
     *
     * <p>Maps to PMD AvoidInstantiatingObjectsInLoops.</p>
     */
    List<String> rule35NewObjectsInLoop(int count) {
        List<String> out = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            // VIOLATION - Major (Rule 35): allocates a new object on every iteration
            String s = new String("x");
            out.add(s);
        }
        return out;
    }

    /* ======================================================================
     * MINOR VIOLATIONS (Rule 40-46) - style issues, warnings only
     * ====================================================================== */

    /**
     * Rule 40 VIOLATION - Minor: Allman brace style instead of Java standard.
     *
     * <p>Maps to Checkstyle LeftCurly (option eol): the opening brace must be at
     * the end of the line, not on its own line.</p>
     */
    // VIOLATION - Minor (Rule 40): opening brace placed on its own line (Allman)
    void rule40BraceStyle(int x)
    {
        if (x > 0) {
            System.out.println(x);
        }
    }

    /**
     * Rule 41 VIOLATION - Minor: identifier naming violations.
     *
     * <p>Maps to Checkstyle MethodName, ParameterName, LocalVariableName. The
     * field {@code BadField} also violates MemberName.</p>
     */
    // VIOLATION - Minor (Rule 41): method name should be lowerCamelCase
    int BadlyNamedMethod(int BadParameter) {
        // VIOLATION - Minor (Rule 41): local variable should be lowerCamelCase
        int Bad_Variable = BadParameter + BadField;
        return Bad_Variable;
    }

    /**
     * Rule 42 VIOLATION - Minor: missing braces on a conditional.
     *
     * <p>Maps to Checkstyle NeedBraces.</p>
     */
    int rule42NoBraces(boolean error) {
        // VIOLATION - Minor (Rule 42): single statement without braces
        if (error)
            return -1;
        return 0;
    }

    /**
     * Rule 43 VIOLATION - Minor: redundant boolean comparison + returns.
     *
     * <p>Maps to Checkstyle SimplifyBooleanExpression and SimplifyBooleanReturn.</p>
     */
    boolean rule43BooleanCompare(boolean flag) {
        // VIOLATION - Minor (Rule 43): compare-to-true and can-be-simplified return
        if (flag == true) {
            return true;
        }
        return false;
    }

    /**
     * Rule 44 VIOLATION - Minor: else after return.
     *
     * <p>Advisory only: there is no PMD/Checkstyle rule for this in the
     * framework's Java ruleset, so it is documented rather than enforced.</p>
     */
    int rule44ElseAfterReturn(boolean error) {
        if (error) {
            return -1;
        } else {
            // VIOLATION - Minor (Rule 44): unnecessary else after a return
            return 0;
        }
    }

    /**
     * Rule 45 VIOLATION - Minor: returns null instead of an empty array.
     *
     * <p>Was C++ returning nullptr; maps to PMD ReturnEmptyArrayRatherThanNull
     * and SpotBugs PZLA_PREFER_ZERO_LENGTH_ARRAYS.</p>
     */
    int[] rule45ReturnNullArray(boolean empty) {
        if (!empty) {
            return new int[] {1, 2, 3};
        }
        // VIOLATION - Minor (Rule 45): callers must null-check; prefer new int[0]
        return null;
    }

    /**
     * Rule 46 VIOLATION - Minor: unused parameter.
     *
     * <p>Maps to PMD UnusedFormalParameter (checkAll). The {@code unusedField}
     * above maps to UnusedPrivateField.</p>
     */
    int rule46UnusedParameter(int used, int unused) {
        // VIOLATION - Minor (Rule 46): 'unused' is never referenced
        return used;
    }

    /**
     * Rule 46 VIOLATION - Minor: unused local variable.
     *
     * <p>Maps to PMD UnusedLocalVariable.</p>
     */
    void rule46UnusedLocal() {
        // VIOLATION - Minor (Rule 46): declared but never used
        int neverUsed = 42;
    }

    /** Simple collaborator used by the double-checked locking example. */
    static final class Helper {
    }
}
