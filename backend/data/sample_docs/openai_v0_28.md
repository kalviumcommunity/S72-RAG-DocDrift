# OpenAI Python SDK (Version 0.28.1)

## Overview
Legacy OpenAI Python library using global module configuration and static completion endpoints.

## Authentication
Authentication is configured globally by setting `openai.api_key`:

```python
import openai
openai.api_key = "sk-..."
openai.organization = "org-..."
```

## Chat Completions
Generate responses using `openai.ChatCompletion.create`:

```python
import openai

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello world!"}
    ],
    temperature=0.7,
    max_tokens=150
)

print(response["choices"][0]["message"]["content"])
```

## Error Handling
Catch legacy exceptions from `openai.error`:

```python
import openai

try:
    openai.ChatCompletion.create(model="gpt-4", messages=[])
except openai.error.RateLimitError as e:
    print("Rate limit reached:", e)
except openai.error.AuthenticationError as e:
    print("Invalid API Key:", e)
except openai.error.OpenAIError as e:
    print("General OpenAI Error:", e)
```
