from backend.pipeline import run_research_pipeline


def generate_research(topic: str, on_stage=None):
    return run_research_pipeline(topic, on_stage=on_stage)
