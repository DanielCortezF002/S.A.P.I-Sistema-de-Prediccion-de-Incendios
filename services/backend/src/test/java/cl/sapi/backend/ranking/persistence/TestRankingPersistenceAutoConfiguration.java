package cl.sapi.backend.ranking.persistence;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * En surefire, sin {@link JdbcTemplate}, suministra un {@link RankingPersistenceService} no-op
 * para que el contexto Spring de SAPI-57 siga cargando. Los *IT* con Testcontainers registran
 * DataSource/JdbcTemplate y el bean real de producción; esta auto-configuración no interviene.
 */
@AutoConfiguration
@ConditionalOnMissingBean(JdbcTemplate.class)
public class TestRankingPersistenceAutoConfiguration {

    @Bean
    RankingPersistenceService rankingPersistenceService() {
        return RankingPersistenceService.noOp();
    }
}
