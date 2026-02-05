import os
import google.genai as genai
from google.genai import types

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

client = genai.Client(api_key=api_key)

async def gemini_chat(messages):
    # Convert messages to Gemini format
    contents = []
    
    for msg in messages:
        if msg["role"] == "system":
            # Add system message as the first user message with instruction
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=f"System instruction: {msg['content']}")]
            ))
        elif msg["role"] == "user":
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=msg["content"])]
            ))
        elif msg["role"] == "assistant":
            contents.append(types.Content(
                role="model",
                parts=[types.Part(text=msg["content"])]
            ))
    
    # Generate content
    response = await client.aio.models.generate_content(
        model="models/gemma-3-27b-it",
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=1000,
        )
    )
    
    return response.text
