"""Small device entry point that logs where Launch startup stops."""

import MatrixOS


def run():
    MatrixOS.Logging.info("Launch", "V2.2.1 boot entry started")
    stage = "import"
    try:
        import main_v2 as application
        stage = "startup"
        application.startup()
    except Exception as error:
        MatrixOS.Logging.info(
            "Launch", "V2.2.1 startup failed at {}: {}".format(
                stage, type(error).__name__))
        raise
    while True:
        application.loop()


run()
