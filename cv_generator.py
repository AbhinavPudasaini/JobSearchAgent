

# # given this
# from langgraph.prebuilt import create_react_agent
# from langchain_groq import ChatGroq

# llm = ChatGroq(model="llama-3.1-8b-instant", api_key="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")

# queries = ["1. golden opportunities in today's era  ", '2. tools that can help build a million‑dollar business  ', '3. high potential opportunities for entrepreneurs now  ', '4. best tools for creating a million‑dollar business in 2025  ', '5. current era opportunities with high growth potential']

# # def formatQuery(queryies:list):
# #     query_list = []
# #     for query in queries:
# #         q = query.strip().split(" ",1)[1]
# #         query_list.append(q)
# #     return query_list

# # lists = formatQuery(queries)
# # print(lists)

# agent = create_react_agent(llm, tools=[])
# output = agent.invoke({"messages":"What is the capital city of China. One line answer"})
# print(output)


from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.document_loaders import WebBaseLoader
import asyncio

import asyncio
import json
from typing import List, Dict
from aiohttp import ClientSession, ClientTimeout
from tenacity import retry, stop_after_attempt, wait_exponential

FETCH_SEMAPHORE = asyncio.Semaphore(10)  
SEARCH_SEMAPHORE = asyncio.Semaphore(4)

def safe_parse_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        # try to extract JSON block
        start = s.find('{')
        end = s.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(s[start:end+1])
            except Exception:
                pass
    raise ValueError("Could not parse JSON from model output")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_page(session: ClientSession, url: str, timeout=10) -> str:
    async with FETCH_SEMAPHORE:
        async with session.get(url, timeout=ClientTimeout(total=timeout), headers={"User-Agent":"MyAgent/1.0"}) as resp:
            resp.raise_for_status()
            text = await resp.text()
            # very lightweight cleaning
            return " ".join(text.split())

# ---- do search (wraps your DuckDuckGo search) ----
async def search_web_async(query: str, max_results: int = 5) -> List[str]:
    async with SEARCH_SEMAPHORE:
        web = DuckDuckGoSearchResults(output_format='list', max_results=10)
        results = await web.invoke(query)
        # keep top K unique links
        links = []
        seen = set()
        for r in results:
            link = r.get('link')
            if not link or link in seen:
                continue
            seen.add(link)
            links.append(link)
            if len(links) >= max_results:
                break
        return links

# ---- scrape many links concurrently with limit ----
async def scrape_links(links: List[str]) -> List[Dict]:
    async with ClientSession() as session:
        tasks = [asyncio.create_task(fetch_page(session, url)) for url in links]
        pages = await asyncio.gather(*tasks, return_exceptions=True)
    # return cleaned successful results with URL metadata
    docs = []
    for url, result in zip(links, pages):
        if isinstance(result, Exception):
            # log if you have logging
            continue
        docs.append({"url": url, "text": result})
    return docs

# ---- summarize one doc with your agent (assume agent.invoke async) ----
async def summarize_doc(agent, doc_text: str, url: str) -> Dict:
    prompt = SystemMessage(content="""
    You are a summarizer. Given a long webpage text, produce a short JSON:
    {"summary":"...", "key_points":["...", "..."], "source":"<url>"}
    Output only JSON.
    """)
    human = HumanMessage(content=doc_text[:40000] + f"\n\nSOURCE:{url}")  # truncate safely
    raw = await agent.invoke({"messages":[prompt, human]}, return_only_outputs=True)
    out = raw.get('messages')[-1].content
    parsed = safe_parse_json(out)
    return parsed
 
# ---- top-level pipeline for one user query ----
async def process_user_query(agent, user_message: HumanMessage):
    # 1. Parse intent -> generate queries (assumes agent.invoke async)
    parse_system = SystemMessage(content=parse_prompt)  # ensure prompt requests strict JSON
    parsed_raw = await agent.invoke({"messages":[parse_system, user_message]}, return_only_outputs=True)
    parsed_json = safe_parse_json(parsed_raw['messages'][-1].content)

    gen_system = SystemMessage(content=generate_prompt)
    gen_raw = await agent.invoke({"messages":[gen_system, user_message]}, return_only_outputs=True)
    gen_text = gen_raw['messages'][-1].content
    # convert model numbered list to strings robustly
    queries = []
    for line in gen_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # remove leading "1. " or "1) " if any
        parts = line.split(maxsplit=1)
        if len(parts) == 1:
            q = parts[0]
        else:
            q = parts[1]
        queries.append(q)
    queries = queries[:5]

    # 2. For each query: search -> scrape -> summarize (concurrent per-query)
    async def handle_query(q):
        links = await search_web_async(q, max_results=5)
        docs = await scrape_links(links)
        # summarize docs concurrently but limited by semaphore inside summarize_doc if needed
        summaries = []
        for doc in docs:
            try:
                s = await summarize_doc(agent, doc['text'], doc['url'])
                summaries.append(s)
            except Exception:
                continue
        return {"query": q, "summaries": summaries, "links": links}

    query_tasks = [asyncio.create_task(handle_query(q)) for q in queries]
    query_results = await asyncio.gather(*query_tasks)

    # 3. Aggregate: combine summaries and ask agent to produce final answer with citations
    aggregator_prompt = SystemMessage(content="""
    Given the per-query summaries (JSON array), produce a final answer to the user's original question.
    Include short answer, bullet key ideas, and list of citations (URL and which summary they came from).
    Output only JSON: {"answer":"", "bullets":[...], "citations":[{"url":"", "note":""}]}
    """)
    aggregator_input = HumanMessage(content=json.dumps(query_results))
    agg_raw = await agent.invoke({"messages":[aggregator_prompt, aggregator_input]}, return_only_outputs=True)
    final_json = safe_parse_json(agg_raw['messages'][-1].content)
    return final_json
