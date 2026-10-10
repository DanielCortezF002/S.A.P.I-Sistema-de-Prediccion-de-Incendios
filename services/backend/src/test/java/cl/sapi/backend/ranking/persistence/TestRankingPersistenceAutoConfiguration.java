package cl.sapi.backend.ranking.persistence;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Profile;

/**
 * Solo Surefire: cuando {@code sapi.persistence.enabled=false} (y no perfil {@code it}),
 * registra un {@link RankingPersistenceService} no-op para que el contexto Spring cargue
 * sin DataSource.
 *
 * <p>Producción y failsafe ({@code it} + {@code sapi.persistence.enabled=true}) usan los
 * beans reales; esta auto-configuración no interviene.
 */
@AutoConfiguration
@Profile("!it")
@ConditionalOnProperty(prefix = "sapi.persistence", name = "enabled", havingValue = "false")
@ConditionalOnMissingBean(RankingPersistenceService.class)
public class TestRankingPersistenceAutoConfiguration {

    @Bean
    RankingPersistenceService rankingPersistenceService() {
        return RankingPersistenceService.noOp();
    }
}
