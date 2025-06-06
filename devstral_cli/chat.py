def chat(verbose: bool = False, debug: bool = False) -> None:
    """Run the interactive Devstral chat session."""
    import devstral_eng

    devstral_eng.VERBOSE = verbose
    devstral_eng.DEBUG = debug
    devstral_eng.main()
