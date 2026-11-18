def pytest_configure(config):
    config.addinivalue_line("markers", "slow: real fastembed on seed data (RUN_SLOW=1 to run)")
