"""Register the retained component-test marker without weakening checks."""
def pytest_configure(config):
    config.addinivalue_line('markers', 'e2e: explicitly opted-in external-stack component checks')
