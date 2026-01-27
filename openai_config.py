# Alternative: Use OpenAI for better conversations
# Install: pip install openai
# Set environment variable: OPENAI_API_KEY=your_key_here

import os
from openai import AsyncOpenAI

async def openai_chat(messages):
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # Cheaper but still excellent
        messages=messages,
        temperature=0.7,  # More creative and natural
    )
    return response.choices[0].message.content
