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
    # Check if keys are set
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    hf_token = os.environ.get("HF_TOKEN")
    
    if not openrouter_key and not gemini_key and not hf_token:
        # Fallback to check .env file if running locally
        env_path = "./.env"
        if os.path.exists(env_path):
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENROUTER_API_KEY="):
                            openrouter_key = line.split("=", 1)[1].strip()
                        elif line.startswith("GEMINI_API_KEY="):
                            gemini_key = line.split("=", 1)[1].strip()
                        elif line.startswith("HF_TOKEN="):
                            hf_token = line.split("=", 1)[1].strip()
            except Exception:
                pass

    generation_success = False
    if gemini_key:
        print("\n[Generator] Using Google Gemini API directly for content generation...")
        try:
            subprocess.run([sys.executable, "generate_all_content_gemini.py"], check=True)
            generation_success = True
        except Exception as e:
            print(f"Error during direct Gemini generation: {e}")
    elif openrouter_key:
        print("\n[Generator] Using OpenRouter (Gemini) for content generation...")
        try:
            subprocess.run([sys.executable, "generate_all_content_gemini.py"], check=True)
            generation_success = True
        except Exception as e:
            print(f"Error during OpenRouter generation: {e}")
    elif hf_token:
        print("\n[Generator] Using Hugging Face Serverless API for content generation...")
        try:
            subprocess.run([sys.executable, "generate_posts_via_huggingface.py"], check=True)
            generation_success = True
        except Exception as e:
            print(f"Error during Hugging Face generation: {e}")

    if not generation_success:
        print("\n[Warning] LLM generation failed or was not configured/available.")
        print("Falling back to generating Mock Post Data via write_today_data.py...")
        subprocess.run([sys.executable, "write_today_data.py"], check=True)

    print("\n=== Pipeline Generation Wrapper Finished successfully ===")

if __name__ == "__main__":
    main()
