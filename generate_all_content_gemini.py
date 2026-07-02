import json
import urllib.request
import ssl
import sys
import os
import datetime
import time
import traceback

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Read API keys from environment variables or fallback to .env
openrouter_key = os.environ.get("OPENROUTER_API_KEY")
gemini_key = os.environ.get("GEMINI_API_KEY")
gemini_model = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
nvidia_key = os.environ.get("NVIDIA_API_KEY")
nvidia_model = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

if not openrouter_key or not gemini_key or not nvidia_key:
    if os.path.exists("./.env"):
        try:
            with open("./.env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        openrouter_key = line.split("=", 1)[1].strip()
                    elif line.startswith("GEMINI_API_KEY="):
                        gemini_key = line.split("=", 1)[1].strip()
                    elif line.startswith("GEMINI_MODEL="):
                        gemini_model = line.split("=", 1)[1].strip()
                    elif line.startswith("NVIDIA_API_KEY="):
                        nvidia_key = line.split("=", 1)[1].strip()
                    elif line.startswith("NVIDIA_MODEL="):
                        nvidia_model = line.split("=", 1)[1].strip()
        except Exception:
            pass

# Determine endpoint and credentials
if nvidia_key:
    print("[LLM Configuration] Using direct NVIDIA NIM API.")
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {nvidia_key}",
        "Content-Type": "application/json"
    }
    llm_model = nvidia_model
elif gemini_key:
    print("[LLM Configuration] Using direct Google Gemini API.")
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {gemini_key}",
        "Content-Type": "application/json"
    }
    llm_model = gemini_model
elif openrouter_key:
    print("[LLM Configuration] Using OpenRouter API.")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json"
    }
    llm_model = "google/gemma-4-31b-it:free"
else:
    print("Error: Neither GEMINI_API_KEY, NVIDIA_API_KEY nor OPENROUTER_API_KEY configured in environment or .env file.")
    exit(1)

def call_gemini(system_prompt, prompt, max_tokens=4000):
    # Try fast small models first, then fall back to larger ones
    models_to_try = [llm_model]
    if nvidia_key:
        for alt in ["meta/llama-3.1-8b-instruct", "meta/llama-3.2-3b-instruct", "nvidia/llama-3.1-nemotron-nano-8b-v1", "meta/llama-3.1-70b-instruct", "nvidia/llama-3.1-nemotron-70b-instruct"]:
            if alt not in models_to_try:
                models_to_try.append(alt)
                
    for m_idx, model_name in enumerate(models_to_try):
        if len(models_to_try) > 1:
            print(f"Trying model: {model_name} (Attempt {m_idx + 1}/{len(models_to_try)})")
            
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        success = False
        text_response = None
        
        # Try up to 3 times per model to keep total run time reasonable
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, context=ctx) as res:
                    resp = json.loads(res.read().decode("utf-8"))
                    if resp and "choices" in resp and len(resp["choices"]) > 0:
                        text_response = resp["choices"][0]["message"]["content"]
                        success = True
                        break
                    else:
                        print(f"API returned unexpected response format: {resp}")
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except:
                    pass
                if e.code in (429, 500, 502, 503, 504):
                    backoff_time = 15 * (attempt + 1) if nvidia_key else 5 * (attempt + 1)
                    print(f"API Error {e.code} ({e.reason}) on model {model_name}. Retrying in {backoff_time}s... Attempt {attempt + 1}/3")
                    time.sleep(backoff_time)
                else:
                    print(f"HTTP Error calling API: {e.code} - {e.reason}. Response: {err_body}")
                    break
            except Exception as e:
                print(f"Error calling API: {e}")
                break
            time.sleep(2)
            
        if success:
            # Post-request delay to avoid RPM rate limits
            if nvidia_key:
                time.sleep(12)
            else:
                time.sleep(2)
            return text_response
            
    return None

# Load context data for references
reddit_posts = []
if os.path.exists("./reddit_data.json"):
    with open("./reddit_data.json") as f:
        reddit_posts = json.load(f)[:15]

ai_news = []
if os.path.exists("./ai_news_data.json"):
    with open("./ai_news_data.json") as f:
        ai_news = json.load(f)[:12]

# Shared writing instructions based on content-doctrine.md and voice-profile.md
writing_rules = """
WRITING RULES:
1. Third-person observer voice, no "I" or "my" or "we" statements. (Except in CTAs: "follow Mohammad Anouf Saani (www.linkedin.com/in/mohammad-anouf-saani) for daily tech breakdowns", "follow for more").
2. Blunt, developer-credible tone. Speak like a senior systems engineer or developer advocate. No corporate press-release language.
3. Technical specificity: Use developer-focused jargon (LLM, SLM, RAG, MCP, API, Docker, vLLM, Ollama, vector databases, etc.) naturally and correctly. Include CLI commands, prompt snippets, or benchmarks where appropriate.
4. No em-dashes anywhere. Use normal commas, semicolons, or periods instead.
5. Do NOT include any headline, title, or header for the posts (like 'Headline: ...' or bold title lines). Start the content of the post directly with its first sentence/hook.
6. Post structure: Hook (1-2 lines) -> Technical bottleneck/pain point -> Actionable solution/code -> Target system state -> Technical engineering question -> CTA.
7. Banned words (NEVER USE ANY): delve, underscore, vibrant, tapestry, interplay, intricate, garner, pivotal, showcase, foster, align with, landscape, key (as adjective), leverages, encompasses, facilitates, utilized, commenced, subsequent to, prior to, in order to, stands as, serves as, is a testament to, plays a vital role, plays a significant role, plays a crucial role, enduring legacy, lasting impact, indelible mark, it's important to note, it's worth noting, no discussion would be complete without, moreover, furthermore, in addition, setting the stage for, marking a shift, evolving landscape, reflects broader trends, game-changer, supercharge, real results, real strategy, real conversations, disruptive, hustle, grind, crush it, synergy, paradigm shift, thought leader, go viral, revolutionary, groundbreaking, unprecedented, cutting-edge, state-of-the-art, next-generation, empower, unlock, journey, ecosystem, world-class, comprehensive, curated, innovative, transformative, passionate, excited to share.
8. Banned LinkedIn patterns:
   - "No X. No Y. Just Z."
   - "It's not just about X. It's about Y."
   - "If you're serious about X, [do this]"
   - "And here's the kicker"
   - "X changed everything"
   - "Enter:"
   - "The best part? [short answer]"
   - Email sign-off language ("To your success")
9. Banned contrast constructions:
   - "This isn't about X, it's about Y"
   - "Not because of X. But because of Y."
   - "Rather than X, do Y"
   - "But rather"
   - "Not just X, but also Y"
   - "Not only X, but Y"
10. Varied sentence lengths. Specific numbers and benchmarks over adjectives. No bullets where flowing prose works better.
"""

# Format fetched RSS feeds for dynamic LLM prompts
news_context = ""
if ai_news:
    news_lines = []
    for idx, item in enumerate(ai_news[:8]):
        title = item.get("title", "").strip()
        desc = item.get("description", "").strip()
        source = item.get("source", "").strip()
        news_lines.append(f"{idx+1}. [{source}] {title} - {desc}")
    news_context = "\n".join(news_lines)
else:
    news_context = "No recent RSS AI news found. Use fallback topic: Model Context Protocol (MCP) release."

reddit_context = ""
if reddit_posts:
    reddit_lines = []
    for idx, item in enumerate(reddit_posts[:8]):
        subreddit = item.get("subreddit", "").strip()
        title = item.get("title", "").strip()
        selftext = item.get("selftext", "").strip()
        selftext = selftext[:200] + "..." if len(selftext) > 200 else selftext
        reddit_lines.append(f"{idx+1}. [{subreddit}] {title} - {selftext}")
    reddit_context = "\n".join(reddit_lines)
else:
    reddit_context = "No recent Reddit posts found. Use fallback topic: Quantized local LLM execution overhead."

system_prompt_main = f"""You are Mohammad Anouf Saani's AI copywriter. Write a single, highly engaging LinkedIn post based on the instructions.
{writing_rules}
"""

posts_to_generate = [
    {
        "id": "1. COLLABORATIVE ARTICLE",
        "prompt": f"""Write a COLLABORATIVE ARTICLE post.
Topic: Memory allocation and overhead when running local LLMs.
Prose: Write about a developer trying to run Llama 3 8B locally on consumer hardware (e.g. RTX 4060 with 8GB VRAM). They experience Out of Memory (OOM) crashes because they didn't configure context window size or KV cache quantization correctly. Explain that KV cache size grows linearly with context. The solution is to use Llama.cpp with Q4_K_M quantization and offload layers to GPU carefully, or configure Ollama system memory constraints to optimize local VRAM.
Write exactly 1500 to 2000 characters of flowing prose. Start directly with the hook. No titles.
"""
    },
    {
        "id": "2. POLL",
        "prompt": f"""Write a POLL post.
Topic: CrewAI vs AutoGen for agentic orchestration.
Setup: Ask developers whether they prefer CrewAI (sequential, role-playing, easy to configure via yaml/python) or AutoGen (event-driven, conversational, highly customizable but harder to debug) when building multi-agent systems for production workflows.
Question: What is your preferred orchestration framework for building production multi-agent systems?
Options:
☐ CrewAI (Role-play/YAML focus)
☐ AutoGen (Conversational/Custom code)
☐ LangGraph (State graph/Precise control)
☐ Vanilla Python (No framework)
Provide the Setup, the Question, the 4 Options, and an Explanation prompt. Do not include any title.
"""
    },
    {
        "id": "3. CAROUSEL",
        "prompt": f"""Write a CAROUSEL post content.
Topic: Pick the most high-signal, interesting, and technical developer/AI news story from the list of latest news below and write a 7-slide breakdown about it:
{news_context}

Instructions:
1. Slide 1 Hook: A bold claim hook (6-8 words max, curiosity gap).
2. Slides 2-6: Step-by-step technical breakdown of how the product/technology works, its architecture, key benefits, or implementation process. Maximum 2 sentences per slide.
3. Slide 7 CTA: "Follow Mohammad Anouf Saani (www.linkedin.com/in/mohammad-anouf-saani) for more posts on developer workflows."
4. Caption: Slide 1 hook, what the carousel covers, engagement question, CTA to save/repost. Max 4 lines.
5. Format: Label each slide clearly (Slide 1, Slide 2, etc.) and end with 'CAROUSEL CAPTION:'. Do not include markdown bold or headers.
"""
    },
    {
        "id": "4. INFOGRAPHIC",
        "prompt": f"""Write an INFOGRAPHIC caption.
Topic: Local LLM VRAM memory footprint by quantization levels.
Caption: Hook, insight beyond the chart (Llama 3 8B requires ~16GB VRAM at FP16, but drops to ~5.7GB at Q4_K_M quantization, making it runnable on consumer GPUs. Highlighting how quantization enables local model execution without cloud hosting bills. Compare FP16, Q8, Q4_K_M, and Q3), engagement question, CTA. Do not include titles.
"""
    },
    {
        "id": "5. POST 1",
        "prompt": f"""Write POST 1 (Tool Spotlight).
Tool: Ollama's new tool call support.
Description: It enables local models like Llama 3 to make structured tool calls natively, allowing developers to build local agentic systems without sending sensitive data to external API providers.
Archetype: Tool Spotlight | Emotion: WOW.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "6. POST 2",
        "prompt": f"""Write POST 2 (Weekly Roundup).
Summarize 4 major technical updates or news stories from the past week based on the latest AI news list:
{news_context}

Archetype: Weekly Roundup | Emotion: OHHH.
Format: Intro hook, numbered list of 4 items (each item max 2 lines summarizing the update and its developer implication), closing, question. No titles.
"""
    },
    {
        "id": "7. POST 3",
        "prompt": f"""Write POST 3 (Plain English Breakdown).
Topic: Model Context Protocol (MCP).
Explain MCP: It's an open standard that lets developers build a single server to expose tools and data resources, which any compatible AI client (Cursor, Claude, etc.) can read natively.
Archetype: Plain English Breakdown | Emotion: OHHH.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "8. POST 4",
        "prompt": f"""Write POST 4 (Unfair Advantage).
Tool: vLLM local serving engine.
Description: Use vLLM to host models locally. It uses PagedAttention to prevent VRAM fragmentation, allowing developers to get up to 2x higher throughput than standard Llama.cpp setups.
Archetype: Unfair Advantage | Emotion: WOW.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "9. POST 5",
        "prompt": f"""Write POST 5 (Career/Income).
Topic: Local LLMs vs cloud API hosting costs.
Description: Running high-volume production tasks on OpenAI or Anthropic APIs can run up thousands in monthly bills. Engineers who learn to quantize and serve local SLMs (using Ollama or vLLM) on local hardware save their teams massive infrastructure debt.
Archetype: Career/Income | Emotion: AHA.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "10. POST 6",
        "prompt": f"""Write POST 6 (Hot Take).
Topic: Monolith vs Microservices for AI agent architecture.
Hot Take: Building complex multi-agent frameworks is overkill for most pipelines. A simple monolith python script with structured outputs is faster, easier to debug, and cheaper to maintain.
Archetype: Hot Take | Emotion: THINK.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "11. POST 7",
        "prompt": f"""Write POST 7 (Steal This).
Topic: Local LLM benchmarking script.
Description: Provide a copy-pasteable bash/CLI script to run local model benchmarks via Ollama to measure tokens/sec throughput and memory usage.
Length: Under 120 words.
Archetype: Steal This | Emotion: WOW.
Start directly with the hook. No titles.
"""
    }
]

generated_posts = {}
all_output_text = ""

print("Generating 11 Main Posts...")
for item in posts_to_generate:
    print(f"Generating {item['id']}...")
    result = call_gemini(system_prompt_main, item["prompt"], max_tokens=4000)
    if not result:
        print(f"Warning: Failed to generate {item['id']}. Using placeholder text.")
        result = f"[Generation failed for {item['id']}. Please re-run the pipeline.]"
        # Don't exit — let the rest of the posts generate
    
    generated_posts[item["id"]] = result
    
    # Format text block
    all_output_text += "==================================================\n"
    all_output_text += f"{item['id']}\n"
    all_output_text += "==================================================\n"
    all_output_text += result.strip() + "\n\n"
    time.sleep(1)

# Write output text files
date_compact = datetime.date.today().isoformat().replace("-", "")
with open("linkedin_posts_today.txt", "w", encoding="utf-8") as f:
    f.write(all_output_text)
with open(f"linkedin_posts_{date_compact}.txt", "w", encoding="utf-8") as f:
    f.write(all_output_text)
print(f"11 Main Posts saved to linkedin_posts_{date_compact}.txt")


# Now generate the Carousel JSON
print("Generating Carousel JSON...")
carousel_post_content = generated_posts.get("3. CAROUSEL", "")
carousel_json_prompt = f"""You are a JSON writer. Read the Carousel post content below and extract the slide data into JSON.

CAROUSEL POST CONTENT:
{carousel_post_content}

Output a single valid JSON object with keys "1" through "7". Each key maps to the slide's fields.
Slide 1 must have: HEADER_LABEL, HOOK_PART_1, HOOK_PART_2, HOOK_EMPHASIS, SUBTITLE
Slides 2 and 4 must have: PILL_LABEL, EYEBROW, HEADLINE_PART_1, HEADLINE_PART_2, HEADLINE_EMPHASIS, SUBHEAD, BODY_TEXT
Slides 3 and 5 must have: HEADER_LABEL, HUGE_STAT, CIRCLE_WORD_1, CIRCLE_WORD_2, HEADLINE_PART_1, HEADLINE_PART_2, HEADLINE_EMPHASIS, BODY_TEXT
Slide 6 must have: HEADER_LABEL, HUGE_STAT, HEADLINE_PART_1, HEADLINE_PART_2, HEADLINE_EMPHASIS, SUBHEAD, BODY_TEXT
Slide 7 must have: HEADLINE_PART_1, HEADLINE_PART_2, HEADLINE_EMPHASIS, SUBHEAD

IMPORTANT RULES:
- Extract ALL content directly from the carousel post above. Do NOT invent content.
- Every field must be a short string (max 10 words each).
- HOOK_EMPHASIS, HEADLINE_EMPHASIS: pick the 1-3 most impactful words from the hook/headline.
- HUGE_STAT: a short number, abbreviation, or 1-2 word stat pulled from the slide content.
- CIRCLE_WORD_1, CIRCLE_WORD_2: two single keywords from the slide topic.
- Slide 7 SUBHEAD must include: "Follow Mohammad Anouf Saani (www.linkedin.com/in/mohammad-anouf-saani) for more breakdowns."
- Output raw JSON only. No markdown. No explanation.
"""

carousel_json_str = call_gemini("You are a JSON writer. Only output raw JSON.", carousel_json_prompt, max_tokens=4000)
if carousel_json_str:
    # Clean up code blocks markdown if LLM wrapped it, and robustly extract JSON block
    text_to_parse = carousel_json_str.strip()
    first_brace = text_to_parse.find('{')
    last_brace = text_to_parse.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text_to_parse = text_to_parse[first_brace:last_brace + 1]
    
    try:
        carousel_data = json.loads(text_to_parse)
        # Use script-relative path to guarantee consistency with generate_carousel_today.py reader
        script_dir = os.path.dirname(os.path.abspath(__file__))
        carousel_json_path = os.path.join(script_dir, "carousel_data.json")
        with open(carousel_json_path, "w", encoding="utf-8") as f:
            json.dump(carousel_data, f, indent=2)
        slide1 = carousel_data.get("1", {})
        topic_hint = slide1.get("HEADER_LABEL") or slide1.get("HOOK_PART_1") or "(unknown)"
        print(f"Saved carousel_data.json successfully! Slide 1 topic: {topic_hint[:80]}")
    except Exception as e:
        print(f"Error parsing Carousel JSON: {e}")
        print("Raw text:", carousel_json_str[:500])

# Now generate the Infographic JSON
print("Generating Infographic JSON...")
infographic_json_prompt = f"""
You are Mohammad Anouf Saani's AI visual content designer.
Based on the generated Infographic post (Post 4) below, you must generate the structured JSON configuration for the Infographic.

Post Content:
{generated_posts.get("4. INFOGRAPHIC", "")}

Format your output as a single valid JSON object. Do NOT wrap it in any markdown code block, and do NOT include any other text before or after the JSON.
Your JSON must strictly follow this structure:
{{
  "title_main": "Local LLM VRAM Memory Footprint",
  "title_span": "VRAM Benchmarks",
  "subtitle": "How quantization levels reduce the memory overhead of running an 8B model locally.",
  "badge": "📊 LOCAL AI INFRA",
  "date_label": "June 2026 Benchmarks",
  "takeaway_num": "5.7 GB",
  "takeaway_text": "is the VRAM required for Llama 3 8B at Q4_K_M quantization, enabling local serving on consumer GPUs.",
  "source": "Source: Llama.cpp Benchmarks | Mohammad Anouf Saani (www.linkedin.com/in/mohammad-anouf-saani)",
  "bars": [
    {{ "label": "Llama 3 8B (FP16/Unquantized) - 16.0 GB", "value": "100%", "color": "#E63946" }},
    {{ "label": "Llama 3 8B (Q8 Quantization) - 8.5 GB", "value": "53%", "color": "#D9785B" }},
    {{ "label": "Llama 3 8B (Q4_K_M Quantization) - 5.7 GB", "value": "36%", "color": "#E8A33D" }},
    {{ "label": "Llama 3 8B (Q3_K_L Quantization) - 4.8 GB", "value": "30%", "color": "#5E6AD2" }}
  ]
}}
Generate a similar JSON for the infographic based on today's VRAM memory dataset.
"""

infographic_json_str = call_gemini("You are a JSON writer. Only output raw JSON.", infographic_json_prompt, max_tokens=4000)
if infographic_json_str:
    # Clean up code blocks markdown if LLM wrapped it, and robustly extract JSON block
    text_to_parse = infographic_json_str.strip()
    first_brace = text_to_parse.find('{')
    last_brace = text_to_parse.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text_to_parse = text_to_parse[first_brace:last_brace + 1]
    
    try:
        infographic_data = json.loads(text_to_parse)
        with open("./infographic_data.json", "w", encoding="utf-8") as f:
            json.dump(infographic_data, f, indent=2)
        print("Saved infographic_data.json successfully!")
    except Exception as e:
        print(f"Error parsing Infographic JSON: {e}")
        print("Raw text:", infographic_json_str)


# Now generate the 5 Performance posts
print("Generating 5 Performance Posts...")
performance_system_prompt = f"""You are the Mohammad Anouf Saani Performance Engine. Write 5 report-driven posts reverse-engineered from actual analytics.
{writing_rules}
"""

perf_posts_list = [
    {
        "id": "1. FOUNDER PSYCHOLOGY CONTRARIAN",
        "prompt": f"""Write the FOUNDER PSYCHOLOGY CONTRARIAN performance post.
Topic: Cloud API hosting vs Local models. Explain that most engineering teams leak budget by calling cloud APIs for simple classification or extraction tasks, convincing themselves they need Claude 3.5 Sonnet or GPT-4o. Real systems engineers deploy optimized local SLMs (like Llama 3 8B or Phi 3) to run high-volume structured data tasks locally, saving 90%+ in API bills.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "2. LOADED POLL",
        "prompt": f"""Write the LOADED POLL performance post.
Topic: "What is your primary vector database for RAG pipelines?"
Question: What is your preferred vector database setup for running production RAG pipelines?
Options:
☐ pgvector (PostgreSQL extension)
☐ Pinecone (Fully managed cloud)
☐ Qdrant (Rust-based local/cloud)
☐ Chroma (Fast python prototyping)
Provide Setup, Question, Options, and Explanation. No titles.
"""
    },
    {
        "id": "3. AI NEWS + IMPLICATIONS",
        "prompt": f"""Write the AI NEWS + IMPLICATIONS performance post.
Topic: pgvector performance scaling benchmarks.
Implication: Teams are shifting away from standalone vector databases to PostgreSQL extensions. This shows that database sprawl is a liability. Keeping vector search close to relational data reduces latency and synchronization overhead.
Start directly with the hook. No titles.
"""
    },
    {
        "id": "4. STORY CAROUSEL",
        "prompt": f"""Write the STORY CAROUSEL performance post content.
Topic: Migrating from a heavy agentic framework to simple python scripts.
Slide 1: "Moving away from heavy agentic frameworks"
Slides 2-6: Case study of how a developer spent weeks debugging state sync, circular loops, and high latency in CrewAI/LangGraph for a simple document ingestion task, then deleted the framework code and wrote a clean 100-line vanilla Python script using structured outputs (Pydantic), reducing execution latency by 80% and debugging time to zero.
Slide 7: "Vanilla scripts beat heavy abstractions."
CAROUSEL CAPTION: [prose caption]
No titles. Format clearly labeled.
"""
    },
    {
        "id": "5. DATA VISUAL + HOOK",
        "prompt": f"""Write the DATA VISUAL + HOOK performance post.
Topic: Ollama quantization throughput comparison.
Caption: Explain that teams blame model sizing for latency, but the real culprit is KV cache offloading and VRAM quantization choices. Q4_K_M remains the sweet spot for balancing intelligence and throughput.
Start directly with the hook. No titles.
"""
    }
]

print("Generating 5 Performance Posts sequentially...")
performance_posts_text = ""
for item in perf_posts_list:
    print(f"Generating {item['id']}...")
    result = call_gemini(performance_system_prompt, item["prompt"], max_tokens=4000)
    if not result:
        print(f"Warning: Failed to generate {item['id']}. Using placeholder.")
        result = f"[Generation failed for {item['id']}. Please re-run the pipeline.]"
        # Don't exit — continue to next post
        
    # Format text block
    performance_posts_text += "==================================================\n"
    performance_posts_text += f"{item['id']}\n"
    performance_posts_text += "==================================================\n"
    performance_posts_text += result.strip() + "\n\n"
    time.sleep(1)

with open(f"performance_posts_{date_compact}.txt", "w", encoding="utf-8") as f:
    f.write(performance_posts_text)
print(f"5 Performance Posts saved to performance_posts_{date_compact}.txt")

print("\n--- Content Generation Completed Successfully ---")
