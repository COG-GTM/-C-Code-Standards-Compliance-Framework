package com.example.standards;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * Code Standards Compliance Tests.
 *
 * <p>JUnit 5 port of the original {@code tests/test_compliance.py}. Verifies that
 * the Java static-analysis configuration (Checkstyle, PMD, SpotBugs) and the
 * severity mapping that the framework ships are present, well-formed, and that
 * the Checkstyle configuration actually detects violations.</p>
 *
 * <p>The original C framework checked the clang-format / clang-tidy configs; this
 * suite checks their Java equivalents:</p>
 * <ul>
 *   <li>clang-format &rarr; Checkstyle ({@code checkstyle.xml})</li>
 *   <li>clang-tidy   &rarr; PMD ({@code pmd-ruleset.xml}) + SpotBugs
 *       ({@code spotbugs-exclude.xml})</li>
 *   <li>clangd / compile_commands.json &rarr; Maven ({@code pom.xml})</li>
 * </ul>
 *
 * <p>The suite is self-contained: the detection smoke test generates its own
 * fixture Java files in a temp directory rather than relying on {@code examples/}
 * (which is delivered by a separate migration PR). Environment-dependent steps
 * (the Maven-driven smoke test) skip gracefully via JUnit
 * {@link org.junit.jupiter.api.Assumptions} so CI never flakes.</p>
 *
 * <p>Run with JDK 17 (SpotBugs crashes on newer JDKs):</p>
 * <pre>
 *   JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn -B -ntp test
 * </pre>
 */
class ComplianceTest {

    // -------------------------------------------------------------------------
    // Shared helpers
    // -------------------------------------------------------------------------

    /**
     * Locates the project root (the directory holding {@code pom.xml} and
     * {@code rule-severity-mapping.yaml}). Surefire runs with the module
     * directory as the working directory, but walk upward as a safety net.
     */
    private static Path projectRoot() {
        Path dir = Path.of(System.getProperty("user.dir")).toAbsolutePath();
        for (Path p = dir; p != null; p = p.getParent()) {
            if (Files.exists(p.resolve("pom.xml"))
                    && Files.exists(p.resolve("rule-severity-mapping.yaml"))) {
                return p;
            }
        }
        return dir;
    }

    private static final Path ROOT = projectRoot();

    /** Parses XML without fetching external DTDs/entities (offline-safe). */
    private static Document parseXml(Path file) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(false);
        factory.setValidating(false);
        factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        DocumentBuilder builder = factory.newDocumentBuilder();
        return builder.parse(file.toFile());
    }

    /** Collects the values of {@code attr} across every {@code <tag>} element. */
    private static List<String> attributeValues(Document doc, String tag, String attr) {
        List<String> values = new ArrayList<>();
        NodeList nodes = doc.getElementsByTagName(tag);
        for (int i = 0; i < nodes.getLength(); i++) {
            Node node = nodes.item(i);
            if (node.getAttributes() == null) {
                continue;
            }
            Node attribute = node.getAttributes().getNamedItem(attr);
            if (attribute != null) {
                values.add(attribute.getNodeValue());
            }
        }
        return values;
    }

    /** Reads the text of a single {@code <properties>} child element, or null. */
    private static String pomProperty(Document pom, String name) {
        NodeList props = pom.getElementsByTagName("properties");
        if (props.getLength() == 0) {
            return null;
        }
        NodeList children = props.item(0).getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node child = children.item(i);
            if (name.equals(child.getNodeName())) {
                return child.getTextContent().trim();
            }
        }
        return null;
    }

    private static String readMapping() throws IOException {
        return Files.readString(ROOT.resolve("rule-severity-mapping.yaml"), StandardCharsets.UTF_8);
    }

    // -------------------------------------------------------------------------
    // Configuration file existence
    // -------------------------------------------------------------------------

    @Nested
    @DisplayName("Configuration files exist")
    class ConfigurationFiles {

        @Test
        @DisplayName("pom.xml (clangd / compile_commands.json -> Maven) exists")
        void pomExists() {
            assertTrue(Files.exists(ROOT.resolve("pom.xml")), "Missing pom.xml");
        }

        @Test
        @DisplayName("checkstyle.xml (clang-format -> Checkstyle) exists")
        void checkstyleExists() {
            assertTrue(Files.exists(ROOT.resolve("checkstyle.xml")), "Missing checkstyle.xml");
        }

        @Test
        @DisplayName("pmd-ruleset.xml (clang-tidy -> PMD) exists")
        void pmdExists() {
            assertTrue(Files.exists(ROOT.resolve("pmd-ruleset.xml")), "Missing pmd-ruleset.xml");
        }

        @Test
        @DisplayName("spotbugs-exclude.xml (clang-tidy -> SpotBugs) exists")
        void spotbugsExists() {
            assertTrue(Files.exists(ROOT.resolve("spotbugs-exclude.xml")), "Missing spotbugs-exclude.xml");
        }

        @Test
        @DisplayName("rule-severity-mapping.yaml exists")
        void severityMappingExists() {
            assertTrue(Files.exists(ROOT.resolve("rule-severity-mapping.yaml")),
                    "Missing rule-severity-mapping.yaml");
        }
    }

    // -------------------------------------------------------------------------
    // Configuration files are well-formed and contain the expected wiring
    // -------------------------------------------------------------------------

    @Nested
    @DisplayName("Configuration files are well-formed")
    class ConfigurationContent {

        @Test
        @DisplayName("pom.xml wires the analysis toolchain on Java 17")
        void pomWiresToolchain() throws Exception {
            Document pom = parseXml(ROOT.resolve("pom.xml"));

            List<String> artifactIds = new ArrayList<>();
            NodeList ids = pom.getElementsByTagName("artifactId");
            for (int i = 0; i < ids.getLength(); i++) {
                artifactIds.add(ids.item(i).getTextContent().trim());
            }

            assertTrue(artifactIds.contains("code-standards-compliance"),
                    "pom should declare artifactId code-standards-compliance");
            assertTrue(artifactIds.contains("maven-checkstyle-plugin"),
                    "pom should configure maven-checkstyle-plugin");
            assertTrue(artifactIds.contains("maven-pmd-plugin"),
                    "pom should configure maven-pmd-plugin");
            assertTrue(artifactIds.contains("spotbugs-maven-plugin"),
                    "pom should configure spotbugs-maven-plugin");
            assertTrue(artifactIds.contains("maven-surefire-plugin"),
                    "pom should configure maven-surefire-plugin (JUnit runner)");
            assertTrue(artifactIds.contains("junit-jupiter"),
                    "pom should depend on junit-jupiter (JUnit 5)");

            assertEquals("17", pomProperty(pom, "maven.compiler.release"),
                    "Project should target Java 17");
        }

        @Test
        @DisplayName("checkstyle.xml is valid and enables the MINOR-tier checks")
        void checkstyleHasExpectedModules() throws Exception {
            Document checkstyle = parseXml(ROOT.resolve("checkstyle.xml"));
            List<String> modules = attributeValues(checkstyle, "module", "name");

            assertTrue(modules.contains("Checker"), "checkstyle.xml root should be a Checker");
            // Rule 40 / 41 / 42 / 43 (+ Rule 31 ordering) live in Checkstyle.
            for (String expected : List.of(
                    "MethodName", "MemberName", "LocalVariableName", "ParameterName",
                    "ConstantName", "TypeName", "PackageName",
                    "NeedBraces", "LeftCurly", "RightCurly",
                    "SimplifyBooleanExpression", "SimplifyBooleanReturn",
                    "OverloadMethodsDeclarationOrder")) {
                assertTrue(modules.contains(expected),
                        "checkstyle.xml should enable the " + expected + " check");
            }
        }

        @Test
        @DisplayName("pmd-ruleset.xml is valid and references the expected PMD rules")
        void pmdReferencesExpectedRules() throws Exception {
            Document pmd = parseXml(ROOT.resolve("pmd-ruleset.xml"));
            List<String> refs = attributeValues(pmd, "rule", "ref");

            // Each ref looks like category/java/<cat>.xml/<RuleName>; match by suffix.
            for (String expected : List.of(
                    "CheckResultSet", "BrokenNullCheck", "CloseResource",
                    "MethodReturnsInternalArray", "UnusedAssignment",
                    "UnusedFormalParameter", "ReturnEmptyArrayRatherThanNull")) {
                boolean present = refs.stream().anyMatch(r -> r.endsWith("/" + expected));
                assertTrue(present, "pmd-ruleset.xml should reference PMD rule " + expected);
            }
        }

        @Test
        @DisplayName("spotbugs-exclude.xml is a well-formed FindBugsFilter")
        void spotbugsFilterIsWellFormed() throws Exception {
            Document spotbugs = parseXml(ROOT.resolve("spotbugs-exclude.xml"));
            assertEquals("FindBugsFilter", spotbugs.getDocumentElement().getNodeName(),
                    "spotbugs-exclude.xml root element should be FindBugsFilter");
        }
    }

    // -------------------------------------------------------------------------
    // Severity mapping: tiers, rule IDs, Java tooling
    // -------------------------------------------------------------------------

    @Nested
    @DisplayName("Severity mapping")
    class SeverityMapping {

        @Test
        @DisplayName("defines all three severity tiers")
        void hasAllSeverityLevels() throws IOException {
            String yaml = readMapping();
            assertTrue(yaml.contains("severity_levels:"), "Missing severity_levels block");
            assertTrue(yaml.contains("critical:"), "Missing 'critical' severity level");
            assertTrue(yaml.contains("major:"), "Missing 'major' severity level");
            assertTrue(yaml.contains("minor:"), "Missing 'minor' severity level");
        }

        @Test
        @DisplayName("contains the full Rule 20-46 catalog")
        void hasExpectedRuleIds() throws IOException {
            String yaml = readMapping();
            // CRITICAL 20-26, MAJOR 30-35, MINOR 40-46.
            int[] expected = {20, 21, 22, 23, 24, 25, 26, 30, 31, 32, 33, 34, 35,
                40, 41, 42, 43, 44, 45, 46};
            for (int id : expected) {
                assertTrue(yaml.contains("Rule " + id),
                        "Severity mapping should include Rule " + id);
            }
        }

        @Test
        @DisplayName("references Java check names, not clang tooling")
        void referencesJavaTooling() throws IOException {
            String yaml = readMapping();
            assertTrue(yaml.contains("SpotBugs"), "Mapping should reference SpotBugs");
            assertTrue(yaml.contains("PMD"), "Mapping should reference PMD");
            assertTrue(yaml.contains("Checkstyle"), "Mapping should reference Checkstyle");

            // Active (non-comment) content must enforce via the Java toolchain.
            // Comment lines may still mention "(was clang-tidy)" for migration context.
            String active = yaml.lines()
                    .filter(line -> !line.strip().startsWith("#"))
                    .reduce("", (a, b) -> a + "\n" + b);
            assertFalse(active.contains("clang-tidy"),
                    "No active rule should enforce via clang-tidy");
            assertFalse(active.contains("clang-format"),
                    "No active rule should enforce via clang-format");
        }

        @Test
        @DisplayName("rule IDs are unique across tiers")
        void ruleIdsAreUnique() throws IOException {
            String yaml = readMapping();
            Matcher matcher = Pattern.compile("rule_id:\\s*\"([^\"]+)\"").matcher(yaml);
            List<String> ids = new ArrayList<>();
            while (matcher.find()) {
                ids.add(matcher.group(1));
            }
            assertFalse(ids.isEmpty(), "Expected at least one rule_id entry");
            Set<String> unique = new HashSet<>(ids);
            assertEquals(ids.size(), unique.size(), "Duplicate rule IDs found: " + ids);
        }
    }

    // -------------------------------------------------------------------------
    // Validation script
    // -------------------------------------------------------------------------

    @Nested
    @DisplayName("Validation script")
    class ValidateScript {

        private Path script() {
            return ROOT.resolve("scripts").resolve("validate.sh");
        }

        @Test
        @DisplayName("scripts/validate.sh exists")
        void scriptExists() {
            assertTrue(Files.exists(script()), "Missing scripts/validate.sh");
        }

        @Test
        @DisplayName("scripts/validate.sh is executable")
        void scriptIsExecutable() {
            Assumptions.assumeTrue(Files.exists(script()), "validate.sh not present");
            // POSIX executable bit; on filesystems without POSIX perms this is a no-op skip.
            Assumptions.assumeTrue(script().getFileSystem().supportedFileAttributeViews().contains("posix"),
                    "Filesystem does not expose POSIX permissions");
            assertTrue(Files.isExecutable(script()), "scripts/validate.sh should be executable");
        }

        @Test
        @DisplayName("scripts/validate.sh drives the Java toolchain")
        void scriptUsesJavaTooling() throws IOException {
            Assumptions.assumeTrue(Files.exists(script()), "validate.sh not present");
            String content = Files.readString(script(), StandardCharsets.UTF_8);
            assertTrue(content.startsWith("#!/bin/bash") || content.contains("#!/bin/bash"),
                    "Script should have a bash shebang");
            assertTrue(content.contains("mvn"), "Script should invoke Maven");
            String lower = content.toLowerCase();
            assertTrue(lower.contains("checkstyle"), "Script should run Checkstyle");
            assertTrue(lower.contains("pmd"), "Script should run PMD");
            assertTrue(lower.contains("spotbugs"), "Script should run SpotBugs");
        }
    }

    // -------------------------------------------------------------------------
    // Detection smoke test: prove the Checkstyle config flags real violations
    // -------------------------------------------------------------------------

    @Nested
    @DisplayName("Detection smoke test (Checkstyle via Maven)")
    class DetectionSmokeTest {

        @Test
        @DisplayName("Checkstyle flags a bad fixture and passes a clean one")
        void checkstyleDetectsViolations() throws Exception {
            String mvn = mavenExecutable();
            Assumptions.assumeTrue(mvn != null, "Maven executable not found on PATH");

            Document pom = parseXml(ROOT.resolve("pom.xml"));
            String pluginVersion = pomProperty(pom, "maven-checkstyle-plugin.version");
            String checkstyleVersion = pomProperty(pom, "checkstyle.version");
            Assumptions.assumeTrue(pluginVersion != null && checkstyleVersion != null,
                    "Checkstyle plugin versions not declared in pom");

            Path tmp = Files.createTempDirectory("compliance-smoke");
            try {
                writeSmokeProject(tmp, pluginVersion, checkstyleVersion);

                Path report = tmp.resolve("target").resolve("checkstyle-result.xml");
                int exit = runCheckstyle(mvn, tmp);

                // checkstyle:checkstyle (report goal) succeeds even with violations.
                Assumptions.assumeTrue(Files.exists(report),
                        "Checkstyle report not produced (exit=" + exit
                                + "); skipping environment-dependent smoke test");

                Document result = parseXml(report);
                int badErrors = errorsForFile(result, "Bad.java");
                int cleanErrors = errorsForFile(result, "Clean.java");

                assertTrue(badErrors > 0,
                        "Checkstyle should report violations for the bad fixture");
                assertEquals(0, cleanErrors,
                        "Checkstyle should report no violations for the clean fixture");
            } finally {
                deleteRecursively(tmp);
            }
        }

        /** Writes a throwaway Maven project that runs the repo's checkstyle.xml. */
        private void writeSmokeProject(Path tmp, String pluginVersion, String checkstyleVersion)
                throws IOException {
            Path src = tmp.resolve("src").resolve("main").resolve("java").resolve("smoke");
            Files.createDirectories(src);

            // Bad fixture: bad method name (Rule 41) + missing braces (Rule 42).
            Files.writeString(src.resolve("Bad.java"),
                    "package smoke;\n"
                            + "public class Bad {\n"
                            + "    public int Bad_Method(int value) {\n"
                            + "        if (value > 0) return 1;\n"
                            + "        return value;\n"
                            + "    }\n"
                            + "}\n",
                    StandardCharsets.UTF_8);

            // Clean fixture: idiomatic Java that satisfies the same rules.
            Files.writeString(src.resolve("Clean.java"),
                    "package smoke;\n"
                            + "public class Clean {\n"
                            + "    public int goodMethod(int value) {\n"
                            + "        if (value > 0) {\n"
                            + "            return 1;\n"
                            + "        }\n"
                            + "        return value;\n"
                            + "    }\n"
                            + "}\n",
                    StandardCharsets.UTF_8);

            String checkstyleConfig = ROOT.resolve("checkstyle.xml").toAbsolutePath().toString();
            Files.writeString(tmp.resolve("pom.xml"),
                    "<project xmlns=\"http://maven.apache.org/POM/4.0.0\">\n"
                            + "  <modelVersion>4.0.0</modelVersion>\n"
                            + "  <groupId>smoke</groupId>\n"
                            + "  <artifactId>smoke</artifactId>\n"
                            + "  <version>1.0.0</version>\n"
                            + "  <packaging>jar</packaging>\n"
                            + "  <properties>\n"
                            + "    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>\n"
                            + "  </properties>\n"
                            + "  <build>\n"
                            + "    <plugins>\n"
                            + "      <plugin>\n"
                            + "        <groupId>org.apache.maven.plugins</groupId>\n"
                            + "        <artifactId>maven-checkstyle-plugin</artifactId>\n"
                            + "        <version>" + pluginVersion + "</version>\n"
                            + "        <dependencies>\n"
                            + "          <dependency>\n"
                            + "            <groupId>com.puppycrawl.tools</groupId>\n"
                            + "            <artifactId>checkstyle</artifactId>\n"
                            + "            <version>" + checkstyleVersion + "</version>\n"
                            + "          </dependency>\n"
                            + "        </dependencies>\n"
                            + "        <configuration>\n"
                            + "          <configLocation>" + checkstyleConfig + "</configLocation>\n"
                            + "          <failOnViolation>false</failOnViolation>\n"
                            + "          <outputFile>${project.build.directory}/checkstyle-result.xml</outputFile>\n"
                            + "          <outputFileFormat>xml</outputFileFormat>\n"
                            + "        </configuration>\n"
                            + "      </plugin>\n"
                            + "    </plugins>\n"
                            + "  </build>\n"
                            + "</project>\n",
                    StandardCharsets.UTF_8);
        }

        private int runCheckstyle(String mvn, Path tmp) throws IOException, InterruptedException {
            ProcessBuilder pb = new ProcessBuilder(
                    mvn, "-B", "-ntp", "checkstyle:checkstyle");
            pb.directory(tmp.toFile());
            // The running JVM is our analysis JDK; point the child Maven at it.
            pb.environment().put("JAVA_HOME", System.getProperty("java.home"));
            pb.redirectErrorStream(true);
            pb.redirectOutput(tmp.resolve("mvn.log").toFile());

            Process process = pb.start();
            if (!process.waitFor(240, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                Assumptions.abort("Checkstyle smoke run timed out");
            }
            return process.exitValue();
        }

        private int errorsForFile(Document report, String fileSuffix) {
            NodeList files = report.getElementsByTagName("file");
            for (int i = 0; i < files.getLength(); i++) {
                Node file = files.item(i);
                Node nameAttr = file.getAttributes().getNamedItem("name");
                if (nameAttr == null || !nameAttr.getNodeValue().endsWith(fileSuffix)) {
                    continue;
                }
                int count = 0;
                NodeList children = file.getChildNodes();
                for (int j = 0; j < children.getLength(); j++) {
                    if ("error".equals(children.item(j).getNodeName())) {
                        count++;
                    }
                }
                return count;
            }
            return 0;
        }
    }

    private static String mavenExecutable() {
        String mavenHome = System.getProperty("maven.home");
        if (mavenHome != null) {
            Path candidate = Path.of(mavenHome, "bin", "mvn");
            if (Files.isExecutable(candidate)) {
                return candidate.toString();
            }
        }
        String path = System.getenv("PATH");
        if (path != null) {
            for (String dir : path.split(File.pathSeparator)) {
                Path candidate = Path.of(dir, "mvn");
                if (Files.isExecutable(candidate)) {
                    return candidate.toString();
                }
            }
        }
        return null;
    }

    private static void deleteRecursively(Path root) {
        if (root == null || !Files.exists(root)) {
            return;
        }
        try (var stream = Files.walk(root)) {
            stream.sorted((a, b) -> b.getNameCount() - a.getNameCount())
                    .forEach(p -> {
                        try {
                            Files.deleteIfExists(p);
                        } catch (IOException ignored) {
                            // best-effort cleanup of the temp directory
                        }
                    });
        } catch (IOException ignored) {
            // best-effort cleanup
        }
    }

    @Test
    @DisplayName("sanity: project root resolves to the framework checkout")
    void projectRootResolves() {
        assertTrue(Files.exists(ROOT.resolve("pom.xml")),
                "Could not locate project root; expected pom.xml at " + ROOT);
        if (!Files.exists(ROOT.resolve("rule-severity-mapping.yaml"))) {
            fail("Could not locate rule-severity-mapping.yaml at project root " + ROOT);
        }
    }
}
