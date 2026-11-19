import ollama

response = ollama.chat(
    # Replace with the exact tag you pulled (e.g., deepseek-r1:1.5b)
    model='deepseek-r1:8b',
    messages=[
        {
            'role': 'system',
            'content': 'You are a helpful AI assistant. Always respond strictly in English.'
        },
        {
            'role': 'user',
            'content': 'Explain how to trace bugs in Python.'
        }
    ]
)

print(response['message']['content'])
