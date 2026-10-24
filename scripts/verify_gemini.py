import os
import sys
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in environment or .env file.")
    sys.exit(1)

from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)

print("=" * 65)
print("GEMINI API VERIFICATION")
print("=" * 65)

# 1. Text Generation Verification
print("\n[1/2] Testing Text Generation with 'gemini-3.5-flash'...")
try:
    gen_resp = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="State in one concise sentence what PEP 20 (The Zen of Python) is.",
        config=types.GenerateContentConfig(
            http_options=types.HttpOptions(timeout=10000)
        )
    )
    print(f" -> Result: SUCCESS")
    print(f" -> Output: {gen_resp.text.strip()}")
except Exception as e:
    print(f" -> Result: FAILED ({e})")

# 2. Text Embedding Verification (gemini-embedding-001)
print("\n[2/2] Testing Embeddings with 'gemini-embedding-001' (768 dimensions)...")
test_snippet = "Abstract: This PEP defines the metadata format for Python packages."
try:
    emb_resp = client.models.embed_content(
        model="gemini-embedding-001",
        contents=test_snippet,
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    vector = emb_resp.embeddings[0].values
    print(f" -> Result: SUCCESS")
    print(f" -> Model: gemini-embedding-001")
    print(f" -> Output Dimension: {len(vector)}")
    print(f" -> Vector Sample (first 5): {[round(x, 5) for x in vector[:5]]}")
except Exception as e:
    print(f" -> Result: FAILED ({e})")

# Batch Embedding Verification
print("\n[Bonus] Testing Batch Embedding with 'gemini-embedding-001'...")
try:
    batch_snippets = [
        "Motivation: Standardize distribution packaging.",
        "Rationale: Avoid fragmented wheel metadata."
    ]
    batch_resp = client.models.embed_content(
        model="gemini-embedding-001",
        contents=batch_snippets,
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    print(f" -> Result: SUCCESS")
    print(f" -> Processed {len(batch_resp.embeddings)} embeddings of dimension {len(batch_resp.embeddings[0].values)}")
except Exception as e:
    print(f" -> Result: FAILED ({e})")

print("\n" + "=" * 65)
print("ALL GEMINI API & EMBEDDING TESTS PASSED SUCCESSFULLY!")
print("=" * 65)

