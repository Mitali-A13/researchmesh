import os

# The AI fact-check makes a real model call, so tests keep it off.
# (test_verify.py switches it on and uses a fake model instead.)
os.environ["VERIFY_WITH_LLM"] = "false"
