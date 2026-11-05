import os

# This pack's tests run on this pack, whatever the default or .env selects.
os.environ["RAG_PACK"] = "cybersecurity"
