-- SAPI F1 (D1/D2/D10, Jira SAPI-43 #10134): procedencia (firms_origin) de
-- cada ejecución persistida. Metadata, no clave: no entra en
-- ejecuciones_clave_natural (un NULL ahí duplicaría la evaluación).
--
-- D10/R2: dos CHECK separados.
--   1) Valores permitidos por contrato (ml-service.v0.yaml): siempre vigente.
--   2) NOT NULL vía CHECK NOT VALID: evita escanear filas anteriores a esta
--      migración (quedan NULL, "legacy") pero se aplica de inmediato a todo
--      INSERT y UPDATE nuevo -- revertir el backend a una versión sin este
--      gate falla cerrado (500) en cada escritura nueva, nunca persiste F1
--      en silencio (ADR-007 §5). Nunca se ejecuta VALIDATE CONSTRAINT.
ALTER TABLE ejecuciones ADD COLUMN firms_origin text;

ALTER TABLE ejecuciones
    ADD CONSTRAINT ejecuciones_firms_origin_valido
    CHECK (firms_origin IN ('baseline', 'current', 'reproducibility'));

ALTER TABLE ejecuciones
    ADD CONSTRAINT ejecuciones_firms_origin_requerido
    CHECK (firms_origin IS NOT NULL) NOT VALID;

COMMENT ON COLUMN ejecuciones.firms_origin IS
    'Procedencia del ranking persistido (baseline/current/reproducibility, ADR-010). '
    'NULL solo en filas anteriores a V004 (legacy); ninguna escritura nueva puede '
    'dejarlo NULL (D10/R2). D2(B): un replay contra una fila legacy NULL se rechaza, '
    'nunca se actualiza ni se infiere desde el fingerprint.';
