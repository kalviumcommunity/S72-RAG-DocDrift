# OpenAI Python SDK (Version 1.0.0+)

## Overview
Modern rewritten OpenAI Python client library featuring explicit client instantiation, typed response models, and async support.

## Authentication & Client Setup
Instantiate the `OpenAI` client explicitly:

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...", # Defaults to os.environ.get("OPENAI_API_KEY")
    organization="org-..."
)
```

## Chat Completions
Generate responses using `client.chat.completions.create`. Response fields are accessed as attributes:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello world!"}
    ],
    temperature=0.7,
    max_tokens=150
)

# Attribute access instead of dict subscript
print(response.choices[0].message.content)
```

## Streaming Responses
Stream tokens in real-time using context iteration:

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Tell a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## Error Handling & Migration Notes
New error hierarchy under `openai`:
- Catch `openai.APIError`, `openai.RateLimitError`, `openai.AuthenticationError`.
- `openai.ChatCompletion.create()` raises `openai.OpenAIError: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable`.
