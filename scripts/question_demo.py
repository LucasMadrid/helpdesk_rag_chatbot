from helpdesk_rag_chatbot.adapters.tracing import get_langfuse_client
from helpdesk_rag_chatbot.config import get_settings

client = get_langfuse_client(get_settings())
for name in ("helpdesk-qa-tune", "helpdesk-qa-holdout"):
    dataset = client.get_dataset(name)
    abstain = sum(item.expected_output["should_abstain"] for item in dataset.items)
    print(f"{name}: {len(dataset.items)} items, {abstain} should abstain")
