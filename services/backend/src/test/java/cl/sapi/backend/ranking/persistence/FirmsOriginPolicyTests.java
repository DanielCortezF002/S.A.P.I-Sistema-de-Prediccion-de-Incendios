package cl.sapi.backend.ranking.persistence;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.Test;

/** SAPI F1 (D1/D2/D10, Jira #10134): gate único de procedencia, sin inferirla (IA-P1-01). */
class FirmsOriginPolicyTests {

    @Test
    void allowsOnlyConfiguredValues() {
        FirmsOriginPolicy policy = policyOf("current", "reproducibility");

        assertThat(policy.isAllowed("current")).isTrue();
        assertThat(policy.isAllowed("reproducibility")).isTrue();
        assertThat(policy.isAllowed("baseline")).isFalse();
    }

    @Test
    void absentOriginIsNeverAllowedRegardlessOfConfig() {
        FirmsOriginPolicy policy = policyOf("current", "reproducibility", "baseline");

        assertThat(policy.isAllowed(null)).isFalse();
    }

    @Test
    void doesNotInferFromAnyOtherValue() {
        FirmsOriginPolicy policy = policyOf("current");

        assertThat(policy.isAllowed("Current")).isFalse();
        assertThat(policy.isAllowed(" current")).isFalse();
        assertThat(policy.isAllowed("")).isFalse();
    }

    @Test
    void failsFastOnEmptyConfiguration() {
        FirmsOriginPolicy policy = new FirmsOriginPolicy();
        policy.setAllowedFirmsOrigins(List.of());

        assertThatThrownBy(policy::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("allowed-firms-origins");
    }

    @Test
    void failsFastOnValuesOutsideTheContract() {
        FirmsOriginPolicy policy = new FirmsOriginPolicy();
        policy.setAllowedFirmsOrigins(List.of("current", "produccion"));

        assertThatThrownBy(policy::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("produccion");
    }

    private static FirmsOriginPolicy policyOf(String... values) {
        FirmsOriginPolicy policy = new FirmsOriginPolicy();
        policy.setAllowedFirmsOrigins(List.of(values));
        policy.validate();
        return policy;
    }
}
