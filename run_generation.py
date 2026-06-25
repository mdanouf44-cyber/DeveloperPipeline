import os
import subprocess
import sys

def main():
    print("=== Pipeline Generation Wrapper Started ===")
    
    # 1. Fetch data
    print("\n[Fetcher] Fetching fresh Reddit posts from RSS...")
    try:
        subprocess.run([sys.executable, "fetch_reddit_rss.py"], check=True)
    except Exception as e:
        print(f"Warning: Reddit fetch failed: {e}. Moving on...")

    print("\n[Fetcher] Fetching fresh AI news from RSS...")
    try:
        subprocess.run([sys.executable, "fetch_ai_news_rss.py"], check=True)
    except Exception as e:
        print(f"Warning: AI news fetch failed: {e}. Moving on...")

    # 2. Generate content
    # Check if OpenRouter key is set
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    hf_token = os.environ.get("HF_TOKEN")
    
    if not openrouter_key and not hf_token:
        # Fallback to check .env file if running locally
        env_path = "./.env"
        if os.path.exists(env_path):
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENROUTER_API_KEY="):
                            openrouter_key = line.split("=", 1)[1].strip()
                        elif line.startswith("HF_TOKEN="):
                            hf_token = line.split("=", 1)[1].strip()
            except Exception:
                pass

    if openrouter_key:
        print("\n[Generator] Using OpenRouter (Gemini) for content generation...")
        subprocess.run([sys.executable, "generate_all_content_gemini.py"], check=True)
    elif hf_token:
        print("\n[Generator] Using Hugging Face Serverless API (GLM-5.2) for content generation...")
        subprocess.run([sys.executable, "generate_posts_via_huggingface.py"], check=True)
    else:
        print("\n[Warning] No LLM API key found (neither OPENROUTER_API_KEY nor HF_TOKEN configured).")
        print("Falling back to generating Mock Post Data via write_today_data.py...")
        subprocess.run([sys.executable, "write_today_data.py"], check=True)

    print("\n=== Pipeline Generation Wrapper Finished successfully ===")

if __name__ == "__main__":
    main()
