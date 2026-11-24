/**
 * @file violations.c
 * @brief Examples of code violations for testing clang-tidy detection.
 *
 * WARNING: This file intentionally contains violations!
 * DO NOT use this code in production!
 *
 * Run: clang-tidy violations.c -- to see the detected warnings.
 *
 * Each function demonstrates a specific rule violation.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ==========================================================================
 * CRITICAL VIOLATIONS (Rule 20-26)
 * These should block merges in CI/CD
 * ========================================================================== */

/**
 * Rule 20 VIOLATION: Unchecked return values
 *
 * Expected clang-tidy warnings:
 * - bugprone-unused-return-value
 * - cert-err33-c
 */
void rule_20_violation_unchecked_return(void)
{
    FILE *f = fopen("data.txt", "r");  /* Return not checked! */
    char buffer[100];

    fread(buffer, 1, 100, f);          /* Return not checked! */
    fclose(f);                         /* f might be NULL! */
}

/**
 * Rule 21 VIOLATION: Buffer overflow risk
 *
 * Expected clang-tidy warnings:
 * - clang-analyzer-security.insecureAPI.strcpy
 */
void rule_21_violation_buffer_overflow(const char *user_input)
{
    char dest[10];
    strcpy(dest, user_input);  /* No bounds check! Could overflow! */
    printf("%s\n", dest);
}

/**
 * Rule 22 VIOLATION: Null pointer dereference
 *
 * Expected clang-tidy warnings:
 * - clang-analyzer-core.NullDereference
 */
int rule_22_violation_null_deref(int *ptr)
{
    return *ptr + 1;  /* ptr might be NULL! */
}

/**
 * Rule 23 VIOLATION: Resource leak
 *
 * Expected clang-tidy warnings:
 * - clang-analyzer-unix.Malloc
 */
void rule_23_violation_resource_leak(const char *path)
{
    FILE *f = fopen(path, "r");
    if (f == NULL)
    {
        return;
    }

    char *buffer = malloc(1024);
    if (buffer == NULL)
    {
        return;  /* LEAK: f not closed! */
    }

    /* Simulate some condition */
    if (path[0] == '/')
    {
        return;  /* LEAK: f and buffer not freed! */
    }

    free(buffer);
    fclose(f);
}

/**
 * Rule 24 VIOLATION: Use after free
 *
 * Expected clang-tidy warnings:
 * - clang-analyzer-unix.Malloc (use-after-free)
 */
void rule_24_violation_use_after_free(void)
{
    char *data = malloc(100);
    if (data != NULL)
    {
        strcpy(data, "Hello");
        free(data);
        printf("%s\n", data);  /* USE AFTER FREE! */
    }
}

/**
 * Rule 24 VIOLATION: Returning the address of a stack buffer
 *
 * Expected clang-tidy warnings:
 * - clang-analyzer-core.StackAddressEscape
 */
char *rule_24_violation_stack_address_escape(void)
{
    char buffer[16] = "dangling";
    return buffer;  /* Stack memory is gone once the function returns! */
}

/**
 * Rule 25 VIOLATION: Uninitialized variable
 *
 * Expected clang-tidy warnings:
 * - clang-analyzer-core.uninitialized.Branch
 */
int rule_25_violation_uninitialized(int condition)
{
    int result;  /* Not initialized! */
    if (condition)
    {
        result = 42;
    }
    return result;  /* Uninitialized if condition is false! */
}

/**
 * Rule 26 VIOLATION: Insecure random
 *
 * Expected clang-tidy warnings:
 * - cert-msc30-c
 * - clang-analyzer-security.insecureAPI.rand
 */
int rule_26_violation_insecure_random(void)
{
    return rand();  /* Predictable! Not cryptographically secure! */
}

/* ==========================================================================
 * MAJOR VIOLATIONS (Rule 30-35)
 * These should require review but may not block merges
 * ========================================================================== */

/**
 * Rule 30 VIOLATION: Narrowing conversion without check
 *
 * Expected clang-tidy warnings:
 * - bugprone-narrowing-conversions
 */
int rule_30_violation_narrowing(long long big_value)
{
    int small_value = big_value;  /* Silent truncation possible! */
    return small_value;
}

/**
 * Rule 32 VIOLATION: Redundant code
 *
 * Expected clang-tidy warnings:
 * - bugprone-branch-clone
 * - misc-redundant-expression
 */
int rule_32_violation_redundant(int x)
{
    if (x > 0)
    {
        return 1;
    }
    else if (x > 0)  /* Redundant! Same condition as above! */
    {
        return 2;    /* Dead code - can never reach here */
    }
    return 0;
}

/* ==========================================================================
 * MINOR VIOLATIONS (Rule 40-46)
 * Style issues - warnings only
 * ========================================================================== */

/**
 * Rule 40 VIOLATION: Wrong brace style (K&R instead of Allman)
 *
 * This is a clang-format issue, not clang-tidy.
 */
void rule_40_violation_brace_style(int x) {
    if (x > 0) {  /* Should be on new line */
        printf("positive\n");
    }
}

/**
 * Rule 41 VIOLATION: Inconsistent naming
 *
 * Expected clang-tidy warnings:
 * - readability-identifier-naming
 */
int MyBadlyNamedFunction(int BadParameter)  /* Should be lower_case */
{
    int BadVariable = BadParameter;         /* Should be lower_case */
    return BadVariable;
}

/**
 * Rule 42 VIOLATION: Missing braces
 *
 * Expected clang-tidy warnings:
 * - readability-braces-around-statements
 */
int rule_42_violation_no_braces(int error)
{
    if (error)
        return -1;  /* Should have braces */

    return 0;
}

/**
 * Rule 43 VIOLATION: Redundant boolean comparison
 *
 * Expected clang-tidy warnings:
 * - readability-simplify-boolean-expr
 */
int rule_43_violation_bool_compare(int flag)
{
    if (flag == 1)  /* Should be: if (flag) */
    {
        return 1;
    }
    return 0;
}

/**
 * Rule 44 VIOLATION: Else after return
 *
 * Expected clang-tidy warnings:
 * - readability-else-after-return
 */
int rule_44_violation_else_after_return(int error)
{
    if (error)
    {
        return -1;
    }
    else  /* Unnecessary else after return */
    {
        return 0;
    }
}

/**
 * Rule 46 VIOLATION: Unused parameter
 *
 * Expected clang-tidy warnings:
 * - misc-unused-parameters
 */
int rule_46_violation_unused_param(int used, int unused)
{
    return used;  /* 'unused' parameter is never used */
}

/* ==========================================================================
 * HELPER FOR COMPILATION
 * ========================================================================== */

/**
 * Main function - demonstrates that violations can be detected.
 *
 * This is for testing purposes only.
 */
int main(void)
{
    printf("=== VIOLATIONS TEST FILE ===\n");
    printf("This file contains intentional violations.\n");
    printf("Run: clang-tidy violations.c -- to see detected issues.\n\n");

    printf("Expected violations:\n");
    printf("- Rule 20: Unchecked return values\n");
    printf("- Rule 21: Buffer overflow (strcpy)\n");
    printf("- Rule 22: Null pointer dereference\n");
    printf("- Rule 23: Resource leaks\n");
    printf("- Rule 24: Use after free, stack address escape\n");
    printf("- Rule 25: Uninitialized variables\n");
    printf("- Rule 26: Insecure random\n");
    printf("- Rule 30: Narrowing conversions\n");
    printf("- Rule 32: Redundant code\n");
    printf("- Rule 42: Missing braces\n");
    printf("- Rule 43: Redundant boolean\n");
    printf("- Rule 44: Else after return\n");
    printf("- Rule 46: Unused parameters\n");

    return 0;
}
