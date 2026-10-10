package cl.sapi.backend.ranking.persistence;

import java.time.OffsetDateTime;

import org.jspecify.annotations.Nullable;

/**
 * Metadatos de una fila de {@code ejecuciones}.
 *
 * @param id identidad generada por la base
 * @param forecastTime instante evaluado por el modelo
 * @param modelVersion versión del modelo (p. ej. {@code prototype_model_d_v1})
 * @param inputsFingerprint sha256 hex de 64 caracteres
 * @param schemaVersion p. ej. {@code sapi-ranking-v0}
 * @param scoreSemantics siempre {@code relative_rank}
 * @param scientificModelValidation siempre {@code false}
 * @param horizonHours horizonte en horas, o null
 * @param createdAt instante en que el sistema persistió la corrida
 */
public record ExecutionRecord(
        long id,
        OffsetDateTime forecastTime,
        String modelVersion,
        String inputsFingerprint,
        String schemaVersion,
        String scoreSemantics,
        boolean scientificModelValidation,
        @Nullable Integer horizonHours,
        OffsetDateTime createdAt) {
}
