package cl.sapi.backend.ranking.persistence;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import cl.sapi.backend.ranking.RankingResultValidator;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * Persistencia sin Docker: Mockito sobre {@link RankingRepository} (CA1/CA4 a nivel de servicio).
 * Los *IT* con Testcontainers cubren PostGIS real (failsafe / Omen).
 */
@ExtendWith(MockitoExtension.class)
class RankingPersistenceServiceTests {

    @Mock
    private RankingRepository repository;

    private RankingPersistenceService service;
    private JsonNode ranking;

    @BeforeEach
    void setUp() {
        service = new RankingPersistenceService(repository);
        RankingResultValidator.Validation validation = RankingResultValidator.validate(realRankingBytes());
        assertThat(validation.violation()).isEmpty();
        ranking = validation.ranking();
    }

    private static byte[] realRankingBytes() {
        try (InputStream in = RankingPersistenceServiceTests.class.getResourceAsStream(
                "/ml/predict-reproducible-2026-09-01.json")) {
            return in.readAllBytes();
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
    }

    @Test
    @DisplayName("SAPI-59.CA1 — primera corrida inserta ejecución y exactamente 50 predicciones")
    void firstPersistInsertsExecutionAndFiftyCells() {
        when(repository.insertExecution(any(), anyString(), anyString(), anyString(), anyString(), anyBoolean(), any()))
                .thenReturn(Optional.of(7L));
        when(repository.countPredictions(7L)).thenReturn(0);

        long id = service.persist(ranking);

        assertThat(id).isEqualTo(7L);
        verify(repository).insertPredictions(eq(7L), any(OffsetDateTime.class), anyList());
        verify(repository, never()).findExecutionById(anyLong());
    }

    @Test
    @DisplayName("SAPI-59.CA4.A — misma corrida dos veces: no duplica predicciones")
    void sameRunTwiceIsIdempotent() {
        when(repository.insertExecution(any(), anyString(), anyString(), anyString(), anyString(), anyBoolean(), any()))
                .thenReturn(Optional.of(3L))
                .thenReturn(Optional.empty());
        when(repository.findExecutionId(any(), anyString(), anyString())).thenReturn(Optional.of(3L));
        when(repository.findExecutionById(3L)).thenReturn(Optional.of(matchingExecution(3L)));
        when(repository.countPredictions(3L)).thenReturn(0).thenReturn(50);
        when(repository.findPredictionsByExecutionId(3L)).thenReturn(cellsFrom(ranking));

        long first = service.persist(ranking);
        long second = service.persist(ranking);

        assertThat(first).isEqualTo(3L);
        assertThat(second).isEqualTo(3L);
        verify(repository, times(1)).insertPredictions(eq(3L), any(), anyList());
        verify(repository).findExecutionById(3L);
    }

    @Test
    @DisplayName("SAPI-59 — replay con metadata divergente falla sin sobrescribir")
    void divergentMetadataOnReplayIsRejected() {
        when(repository.insertExecution(any(), anyString(), anyString(), anyString(), anyString(), anyBoolean(), any()))
                .thenReturn(Optional.empty());
        when(repository.findExecutionId(any(), anyString(), anyString())).thenReturn(Optional.of(3L));
        ExecutionRecord divergent = new ExecutionRecord(
                3L,
                OffsetDateTime.parse(ranking.get("forecast_time").stringValue()),
                ranking.get("model_version").stringValue(),
                ranking.get("inputs_fingerprint").stringValue(),
                ranking.get("schema_version").stringValue(),
                ranking.get("score_semantics").stringValue(),
                false,
                5,
                OffsetDateTime.parse("2026-09-01T01:00:00Z"));
        when(repository.findExecutionById(3L)).thenReturn(Optional.of(divergent));

        assertThatThrownBy(() -> service.persist(ranking))
                .isInstanceOf(RankingPersistenceException.class)
                .hasMessageContaining("metadata");
        verify(repository, never()).insertPredictions(anyLong(), any(), anyList());
        verify(repository, never()).countPredictions(anyLong());
    }

    @Test
    @DisplayName("SAPI-59 — horizon_hours fuera del rango int no se trunca silenciosamente")
    void horizonHoursOutsideIntRangeIsRejected() {
        ObjectNode bad = (ObjectNode) ranking.deepCopy();
        bad.put("horizon_hours", 2_147_483_648L);

        assertThatThrownBy(() -> service.persist(bad))
                .isInstanceOf(RankingPersistenceException.class)
                .hasMessageContaining("horizon_hours");
        verify(repository, never()).insertExecution(any(), anyString(), anyString(), anyString(), anyString(),
                anyBoolean(), any());
    }

    @Test
    @DisplayName("SAPI-59.CA4.C — mismo forecast/model con fingerprint distinto → nueva ejecución")
    void differentFingerprintCreatesNewExecution() {
        when(repository.insertExecution(any(), anyString(), anyString(), anyString(), anyString(), anyBoolean(), any()))
                .thenReturn(Optional.of(10L))
                .thenReturn(Optional.of(11L));
        when(repository.countPredictions(10L)).thenReturn(0);
        when(repository.countPredictions(11L)).thenReturn(0);

        long first = service.persist(ranking);
        ObjectNode other = (ObjectNode) ranking.deepCopy();
        other.put("inputs_fingerprint", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
        long second = service.persist(other);

        assertThat(first).isEqualTo(10L);
        assertThat(second).isEqualTo(11L);
        verify(repository, times(2)).insertPredictions(anyLong(), any(), anyList());
    }

    @Test
    @DisplayName("SAPI-59.CA3 — latest usa findLatestExecution (created_at DESC, id DESC en el SQL)")
    void findLatestReadsViaCreatedAtOrder() {
        OffsetDateTime created = OffsetDateTime.parse("2026-09-01T01:00:00Z");
        ExecutionRecord execution = new ExecutionRecord(
                9L, OffsetDateTime.parse("2026-09-01T00:00:00Z"), "prototype_model_d_v1",
                ranking.get("inputs_fingerprint").stringValue(), "sapi-ranking-v0",
                "relative_rank", false, 6, created);
        when(repository.findLatestExecution()).thenReturn(Optional.of(execution));
        when(repository.findPredictionsByExecutionId(9L)).thenReturn(cellsFrom(ranking));

        Optional<PersistedRanking> latest = service.findLatestRanking();

        assertThat(latest).isPresent();
        assertThat(latest.get().execution().id()).isEqualTo(9L);
        assertThat(latest.get().cells()).hasSize(50);
        verify(repository).findLatestExecution();
        verify(repository, never()).findExecutionId(any(), anyString(), anyString());
    }

    @Test
    @DisplayName("SAPI-59 — ejecución parcial (n≠0 y n≠50) falla sin sobrescribir")
    void partialExecutionIsRejected() {
        when(repository.insertExecution(any(), anyString(), anyString(), anyString(), anyString(), anyBoolean(), any()))
                .thenReturn(Optional.empty());
        when(repository.findExecutionId(any(), anyString(), anyString())).thenReturn(Optional.of(5L));
        when(repository.findExecutionById(5L)).thenReturn(Optional.of(matchingExecution(5L)));
        when(repository.countPredictions(5L)).thenReturn(12);

        assertThatThrownBy(() -> service.persist(ranking))
                .isInstanceOf(RankingPersistenceException.class)
                .hasMessageContaining("12");
        verify(repository, never()).insertPredictions(anyLong(), any(), anyList());
    }

    private ExecutionRecord matchingExecution(long id) {
        return new ExecutionRecord(
                id,
                OffsetDateTime.parse(ranking.get("forecast_time").stringValue()),
                ranking.get("model_version").stringValue(),
                ranking.get("inputs_fingerprint").stringValue(),
                ranking.get("schema_version").stringValue(),
                ranking.get("score_semantics").stringValue(),
                ranking.get("scientific_model_validation").booleanValue(),
                ranking.get("horizon_hours").intValue(),
                OffsetDateTime.parse("2026-09-01T01:00:00Z"));
    }

    private static List<CellPredictionRow> cellsFrom(JsonNode ranking) {
        JsonNode cells = ranking.get("cells");
        List<CellPredictionRow> rows = new ArrayList<>(50);
        for (int i = 0; i < cells.size(); i++) {
            JsonNode cell = cells.get(i);
            rows.add(new CellPredictionRow(
                    cell.get("cell_id").stringValue(),
                    cell.get("score").doubleValue(),
                    cell.get("rank").intValue(),
                    cell.get("display_rank").intValue(),
                    cell.get("tie_group_size").intValue()));
        }
        return rows;
    }
}
