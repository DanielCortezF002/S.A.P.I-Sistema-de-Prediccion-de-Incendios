package cl.sapi.backend.ranking.persistence;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Solo para Surefire (perfil distinto de {@code it}): sin DataSource/JdbcTemplate, suministra un
 * {@link RankingPersistenceService} no-op para que el contexto Spring de SAPI-57 cargue.
 *
 * <p>Con {@code @ActiveProfiles("it")} (failsafe / Testcontainers) esta auto-configuración
 * <strong>no</strong> se registra: el contexto usa DataSource real → JdbcTemplate →
 * {@link RankingRepository} → {@link RankingPersistenceService} de producción. No usar el no-op
 * en ITs (evita CGLIB sobre la clase final y prueba el servicio real).
 */
@AutoConfiguration
@Profile("!it")
@ConditionalOnMissingBean(JdbcTemplate.class)
public class TestRankingPersistenceAutoConfiguration {

    @Bean
    RankingPersistenceService rankingPersistenceService() {
        return RankingPersistenceService.noOp();
    }
}
