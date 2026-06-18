package com.example.standards;

/**
 * Marker type for the Code Standards Compliance Framework.
 *
 * <p>This project ships static-analysis configuration (Checkstyle, PMD and
 * SpotBugs) rather than runtime application code. This minimal, intentionally
 * clean type exists only to anchor the {@code com.example.standards} package so
 * that the analyzers (and the JUnit compliance suite) always have a compiled
 * module to operate on, even before the reference examples are present.</p>
 *
 * <p>Reference example code — both compliant and deliberately non-compliant —
 * lives under {@code examples/}.</p>
 */
public final class Framework {

    private Framework() {
    }

    /**
     * Returns the framework version, matching the Maven project version.
     *
     * @return the framework version string
     */
    public static String version() {
        return "1.0.0";
    }
}
