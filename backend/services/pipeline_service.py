from backend.pipeline import run_research_pipeline


def generate_research(topic: str):
    return run_research_pipeline(topic)
