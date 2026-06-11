from temporalio import activity


@activity.defn
def hello_activity(name: str) -> str:
    """Phase A walking skeleton activity. Sync — uses ThreadPoolExecutor."""
    return f"Hello, {name}!"
