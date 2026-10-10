package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigInteger;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.function.Consumer;
import java.util.stream.Stream;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * Invariantes de {@code RankingResult} que el backend verifica antes de reenviar el cuerpo del ML
 * (SAPI-57.CA3, RN-02, RN-03, RN-04, RN-09). Cada caso inválido exige el motivo exacto, para que una
 * verificación no quede cubierta por otra.
 */
class RankingResultValidatorTests {

    /** Celdas del grupo superior (empate de 7), del medio (41) y del inferior (2) en el fixture real. */
    private static final int[] TOP_GROUP = {0, 7};
    private static final int[] BOTTOM_GROUP = {48, 50};

    @Test
    @DisplayName("SAPI-57.CA3 — la respuesta real del ML (con empates) cumple el contrato")
    void realMlResponseIsValid() {
        RankingResultValidator.Validation validation = RankingResultValidator.validate(Fixtures.realRanking());
        assertThat(validation.violation()).isEmpty();
        assertThat(validation.ranking().get("cells")).hasSize(50);
    }

    @Test
    @DisplayName("SAPI-57.CA3 — el ejemplo sintético del contrato cumple el contrato")
    void contractExampleIsValid() {
        assertThat(RankingResultValidator.violation(Fixtures.contractSyntheticExample())).isEmpty();
    }

    @Test
    @DisplayName("SAPI-57.CA3 — los campos aditivos desconocidos y un horizon_hours grande se aceptan")
    void additiveFieldsAndLargeHorizonAreAccepted() {
        byte[] body = Fixtures.realRankingWith(root -> {
            root.put("firms_status", "ok");
            root.put("horizon_hours", new BigInteger("1099511627776"));
            ((ObjectNode) root.get("cells").get(0)).put("campo_nuevo", 1);
        });
        assertThat(RankingResultValidator.violation(body)).isEmpty();
    }

    static Stream<Arguments> invalidBodies() {
        return Stream.of(
                change("falta schema_version", "schema_version", root -> root.remove("schema_version")),
                change("schema_version distinto", "schema_version", root -> root.put("schema_version", "sapi-ranking-v1")),
                change("model_version vacío", "model_version", root -> root.put("model_version", "")),
                change("forecast_time sin zona horaria", "forecast_time", root -> root.put("forecast_time", "2026-09-01T00:00:00")),
                change("forecast_time no es fecha", "forecast_time", root -> root.put("forecast_time", "ayer")),
                change("forecast_time sin segundos", "forecast_time", root -> root.put("forecast_time", "2026-09-01T00:00Z")),
                change("forecast_time con offset +03", "forecast_time", root -> root.put("forecast_time", "2026-09-01T00:00:00+03")),
                change("forecast_time con offset con segundos", "forecast_time",
                        root -> root.put("forecast_time", "2026-09-01T00:00:00+03:00:30")),
                change("forecast_time con año de 5 dígitos", "forecast_time",
                        root -> root.put("forecast_time", "+12026-09-01T00:00:00Z")),
                change("forecast_time con -00:00", "forecast_time", root -> root.put("forecast_time", "2026-09-01T00:00:00-00:00")),
                change("forecast_time con salto de línea final", "forecast_time",
                        root -> root.put("forecast_time", "2026-09-01T00:00:00Z\n")),
                change("fingerprint en mayúsculas", "inputs_fingerprint", root -> root.put("inputs_fingerprint",
                        root.get("inputs_fingerprint").stringValue().toUpperCase())),
                change("score_semantics distinto", "score_semantics", root -> root.put("score_semantics", "probability")),
                change("scientific_model_validation true", "scientific_model_validation",
                        root -> root.put("scientific_model_validation", true)),
                change("scientific_model_validation como string", "scientific_model_validation",
                        root -> root.put("scientific_model_validation", "false")),
                change("horizon_hours 0", "horizon_hours", root -> root.put("horizon_hours", 0)),
                change("horizon_hours null", "horizon_hours", root -> root.putNull("horizon_hours")),
                change("horizon_hours decimal", "horizon_hours", root -> root.put("horizon_hours", 6.0)),
                change("disclaimer no string", "disclaimer", root -> root.put("disclaimer", 1)),
                change("49 celdas", "exactamente 50 celdas", root -> cells(root).remove(49)),
                change("51 celdas", "exactamente 50 celdas", root -> cells(root).add(cells(root).get(49).deepCopy())),
                change("cell_id duplicado", "VP-001..VP-050",
                        root -> cell(root, 1).put("cell_id", cell(root, 0).get("cell_id").stringValue())),
                change("cell_id fuera de la grilla", "VP-001..VP-050", root -> cell(root, 0).put("cell_id", "VP-051")),
                change("score > 1 en todo el grupo superior", "score no es un número en [0, 1]",
                        root -> setGroupScore(root, TOP_GROUP, 1.5)),
                change("score negativo en todo el grupo inferior", "score no es un número en [0, 1]",
                        root -> setGroupScore(root, BOTTOM_GROUP, -0.1)),
                change("score como string", "score no es un número", root -> cell(root, 0).put("score", "0.5")),
                change("score crece al avanzar el rank (empates coherentes)", "score crece al avanzar el rank", root -> {
                    double top = cell(root, 0).get("score").doubleValue();
                    cell(root, 0).put("score", cell(root, 49).get("score").doubleValue());
                    cell(root, 49).put("score", top);
                    recomputeTies(root);
                }),
                change("rank fuera de orden", "rank no sigue el orden", root -> {
                    cell(root, 0).put("rank", 2);
                    cell(root, 1).put("rank", 1);
                }),
                change("rank no entero", "rank no es un entero", root -> cell(root, 0).put("rank", 1.0)),
                change("display_rank incorrecto", "display_rank", root -> cell(root, 0).put("display_rank", 2)),
                change("tie_group_size incorrecto", "tie_group_size", root -> cell(root, 0).put("tie_group_size", 1)),
                change("celda no es objeto", "no es un objeto",
                        root -> cells(root).set(3, root.stringNode("VP-004"))));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("invalidBodies")
    @DisplayName("SAPI-57.CA3 — un resultado que no cumple el contrato se rechaza con su motivo (RN-09)")
    void invalidBodiesAreRejected(String name, byte[] body, String expectedReason) {
        assertThat(RankingResultValidator.violation(body)).as(name)
                .hasValueSatisfying(violation -> assertThat(violation).contains(expectedReason));
    }

    static Stream<Arguments> malformedBodies() {
        String real = new String(Fixtures.realRanking(), StandardCharsets.UTF_8);
        byte[] bom = {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF};
        byte[] withBom = new byte[bom.length + Fixtures.realRanking().length];
        System.arraycopy(bom, 0, withBom, 0, bom.length);
        System.arraycopy(Fixtures.realRanking(), 0, withBom, bom.length, Fixtures.realRanking().length);
        return Stream.of(
                Arguments.of("vacío", new byte[0]),
                Arguments.of("HTML", "<html>error</html>".getBytes(StandardCharsets.UTF_8)),
                Arguments.of("arreglo", "[]".getBytes(StandardCharsets.UTF_8)),
                Arguments.of("truncado", real.substring(0, real.length() / 2).getBytes(StandardCharsets.UTF_8)),
                Arguments.of("basura al final", (real + " {}").getBytes(StandardCharsets.UTF_8)),
                Arguments.of("clave duplicada", real.replaceFirst("\\{",
                        "{\"model_version\":\"otro\",").getBytes(StandardCharsets.UTF_8)),
                Arguments.of("UTF-8 con BOM", withBom),
                Arguments.of("UTF-16LE sin BOM", real.getBytes(StandardCharsets.UTF_16LE)),
                Arguments.of("UTF-16BE sin BOM", real.getBytes(StandardCharsets.UTF_16BE)),
                Arguments.of("UTF-32LE sin BOM", real.getBytes(Charset.forName("UTF-32LE"))));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("malformedBodies")
    @DisplayName("SAPI-57.CA2 — un cuerpo que no es un objeto JSON en UTF-8 se rechaza")
    void malformedBodiesAreRejected(String name, byte[] body) {
        assertThat(RankingResultValidator.violation(body)).as(name)
                .hasValueSatisfying(violation -> assertThat(violation).contains("objeto JSON en UTF-8"));
    }

    @Test
    @DisplayName("SAPI-57.CA2 — la regla RFC 3339 del backend nunca acepta algo que el contrato rechace")
    void forecastTimeRuleIsNoLooserThanTheContract() {
        List<String> candidates = List.of("2026-09-01T00:00:00Z", "2026-09-01t00:00:00z",
                "2026-09-01T00:00:00.123456789+05:30", "2026-10-01T18:00:00-03:00", "2026-10-01T21:00:00.5+00:00",
                "2026-09-01T00:00:00+18:00", "2026-09-01T00:00:00+19:00", "2026-02-29T00:00:00Z",
                "2026-09-01T23:59:60Z", "2026-09-01T00:00:00-00:00", "2026-09-01T00:00Z", "2026-09-01 00:00:00Z",
                "2026-09-01T00:00:00.1234567890Z", "2026-09-01T24:00:00Z");
        for (String candidate : candidates) {
            if (ForecastTime.isValid(candidate)) {
                assertThat(BackendContract.isDateTime(candidate)).as(candidate).isTrue();
            }
        }
        assertThat(ForecastTime.isValid("2026-09-01T00:00:00Z")).isTrue();
        assertThat(ForecastTime.isValid("2026-10-01T18:00:00-03:00")).isTrue();
        assertThat(ForecastTime.isValid("2026-02-29T00:00:00Z")).isFalse();
    }

    @Test
    @DisplayName("SAPI-57.CA2 — se reconoce el error_type de un cuerpo Error del ML")
    void errorTypeIsReadFromErrorBody() {
        assertThat(RankingResultValidator.errorType(Fixtures.mlError("prototype_unavailable")))
                .contains("prototype_unavailable");
        assertThat(RankingResultValidator.errorType("{\"error_type\":\"x\"}".getBytes(StandardCharsets.UTF_8)))
                .isEmpty();
        assertThat(RankingResultValidator.errorType("no es json".getBytes(StandardCharsets.UTF_8))).isEmpty();
    }

    private static Arguments change(String name, String expectedReason, Consumer<ObjectNode> change) {
        return Arguments.of(name, Fixtures.realRankingWith(change), expectedReason);
    }

    private static ArrayNode cells(ObjectNode root) {
        return (ArrayNode) root.get("cells");
    }

    private static ObjectNode cell(ObjectNode root, int index) {
        return (ObjectNode) cells(root).get(index);
    }

    /** Cambia el score de un grupo de empate completo: display_rank y tie_group_size siguen coherentes. */
    private static void setGroupScore(ObjectNode root, int[] range, double score) {
        for (int i = range[0]; i < range[1]; i++) {
            cell(root, i).put("score", score);
        }
    }

    /** Recalcula display_rank y tie_group_size desde los scores, para que solo falle la regla probada. */
    private static void recomputeTies(ObjectNode root) {
        for (int i = 0; i < 50; i++) {
            double score = cell(root, i).get("score").doubleValue();
            int higher = 0;
            int tied = 0;
            for (int j = 0; j < 50; j++) {
                double other = cell(root, j).get("score").doubleValue();
                if (other > score) {
                    higher++;
                }
                else if (other == score) {
                    tied++;
                }
            }
            cell(root, i).put("display_rank", higher + 1);
            cell(root, i).put("tie_group_size", tied);
        }
    }
}
