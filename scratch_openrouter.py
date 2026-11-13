import os
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv() 
client = OpenAI(base_url=os.environ["LLM_BASE_URL"],
                api_key=os.environ["OPENROUTER_API_KEY"])
print("Free models available now:")
for m in client.models.list():
    if m.id.endswith(":free"):
        print(" ", m.id)
reply = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    messages=[{"role": "user", "content": "Reply with exactly: key works"}],
)
print("Reply:", reply.choices[0].message.content)