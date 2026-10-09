package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
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
 * (SAPI-57.CA3, RN-02, RN-03, RN-04, RN-09).
 */
class RankingResultValidatorTests {

    @Test
    @DisplayName("SAPI-57.CA3 — la respuesta real del ML (con empates) cumple el contrato")
    void realMlResponseIsValid() {
        assertThat(RankingResultValidator.violation(Fixtures.realRanking())).isEmpty();
    }

    @Test
    @DisplayName("SAPI-57.CA3 — el ejemplo sintético del contrato cumple el contrato")
    void contractExampleIsValid() {
        assertThat(RankingResultValidator.violation(Fixtures.contractSyntheticExample())).isEmpty();
    }

    @Test
    @DisplayName("SAPI-57.CA3 — los campos aditivos desconocidos se aceptan (contrato solo aditivo)")
    void unknownFieldsAreAccepted() {
        byte[] body = Fixtures.realRankingWith(root -> {
            root.put("firms_status", "ok");
            ((ObjectNode) root.get("cells").get(0)).put("campo_nuevo", 1);
        });
        assertThat(RankingResultValidator.violation(body)).isEmpty();
    }

    static Stream<Arguments> invalidBodies() {
        return Stream.of(
                change("falta schema_version", root -> root.remove("schema_version")),
                change("schema_version distinto", root -> root.put("schema_version", "sapi-ranking-v1")),
                change("model_version vacío", root -> root.put("model_version", "")),
                change("forecast_time sin zona horaria", root -> root.put("forecast_time", "2026-09-01T00:00:00")),
                change("forecast_time no es fecha", root -> root.put("forecast_time", "ayer")),
                change("fingerprint en mayúsculas", root -> root.put("inputs_fingerprint",
                        root.get("inputs_fingerprint").stringValue().toUpperCase())),
                change("score_semantics distinto", root -> root.put("score_semantics", "probability")),
                change("scientific_model_validation true", root -> root.put("scientific_model_validation", true)),
                change("scientific_model_validation como string", root -> root.put("scientific_model_validation", "false")),
                change("horizon_hours 0", root -> root.put("horizon_hours", 0)),
                change("horizon_hours null", root -> root.putNull("horizon_hours")),
                change("disclaimer no string", root -> root.put("disclaimer", 1)),
                change("49 celdas", root -> cells(root).remove(49)),
                change("51 celdas", root -> cells(root).add(cells(root).get(49).deepCopy())),
                change("cell_id duplicado", root -> cell(root, 1).put("cell_id", cell(root, 0).get("cell_id").stringValue())),
                change("cell_id fuera de la grilla", root -> cell(root, 0).put("cell_id", "VP-051")),
                change("score > 1", root -> cell(root, 0).put("score", 1.5)),
                change("score negativo", root -> cell(root, 49).put("score", -0.1)),
                change("score como string", root -> cell(root, 0).put("score", "0.5")),
                change("rank fuera de orden", root -> {
                    cell(root, 0).put("rank", 2);
                    cell(root, 1).put("rank", 1);
                }),
                change("rank no entero", root -> cell(root, 0).put("rank", 1.0)),
                change("score crece al avanzar el rank", root -> cell(root, 49).put("score", 0.99)),
                change("display_rank incorrecto", root -> cell(root, 0).put("display_rank", 2)),
                change("tie_group_size incorrecto", root -> cell(root, 0).put("tie_group_size", 1)),
                change("celda no es objeto", root -> cells(root).set(3, "VP-004")));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("invalidBodies")
    @DisplayName("SAPI-57.CA3 — un resultado que no cumple el contrato se rechaza (RN-09)")
    void invalidBodiesAreRejected(String name, byte[] body) {
        assertThat(RankingResultValidator.violation(body)).as(name).isPresent();
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("malformedBodies")
    @DisplayName("SAPI-57.CA2 — un cuerpo que no es JSON válido se rechaza")
    void malformedBodiesAreRejected(String name, byte[] body) {
        assertThat(RankingResultValidator.violation(body)).as(name).isPresent();
    }

    static Stream<Arguments> malformedBodies() {
        String real = new String(Fixtures.realRanking(), StandardCharsets.UTF_8);
        return Stream.of(
                Arguments.of("vacío", new byte[0]),
                Arguments.of("HTML", "<html>error</html>".getBytes(StandardCharsets.UTF_8)),
                Arguments.of("arreglo", "[]".getBytes(StandardCharsets.UTF_8)),
                Arguments.of("truncado", real.substring(0, real.length() / 2).getBytes(StandardCharsets.UTF_8)),
                Arguments.of("basura al final", (real + " {}").getBytes(StandardCharsets.UTF_8)),
                Arguments.of("clave duplicada", real.replaceFirst("\\{",
                        "{\"model_version\":\"otro\",").getBytes(StandardCharsets.UTF_8)));
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

    private static Arguments change(String name, Consumer<ObjectNode> change) {
        return Arguments.of(name, Fixtures.realRankingWith(change));
    }

    private static ArrayNode cells(ObjectNode root) {
        return (ArrayNode) root.get("cells");
    }

    private static ObjectNode cell(ObjectNode root, int index) {
        return (ObjectNode) cells(root).get(index);
    }
}
