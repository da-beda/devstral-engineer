def chat(verbose: bool = False, debug: bool = False, no_index: bool = False) -> None:
    """Run the interactive Devstral chat session."""
    import devstral_eng

    import asyncio

    devstral_eng.VERBOSE = verbose
    devstral_eng.DEBUG = debug
    asyncio.run(devstral_eng.main(no_index=no_index))
