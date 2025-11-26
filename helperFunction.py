from typing import List
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.document_loaders import WebBaseLoader
from urllib.parse import urlparse

def get_domain(url):
    return urlparse(url).netloc

def format_query_list(queries_str: str) -> List[str]:
    """Cleans and formats the raw output from the query generator."""
    lines = queries_str.strip().split("\n")
    query_list = []
    for line in lines:
        q = line.strip().split(" ", 1)[-1]
        query_list.append(q)
    return query_list

async def scrape_web_page(url: str) -> str:
    """Asynchronously scrapes content from a single URL."""
    try:
        scraper = WebBaseLoader(web_path=[url])
        docs = await scraper.aload()
        if docs:
            clean_text = " ".join(docs[0].page_content.split())
            return clean_text
        return f"Failed to load content from {url}"
    except Exception as e:
        return f"Error scraping {url}: {repr(e)}"

async def search_web(query: str) -> List[str]:
    """Performs a web search and returns a list of links."""
    links = []
    web_search = DuckDuckGoSearchResults(max_results=3)
    results = await web_search.ainvoke(query)
    for i in results:
        links.append({"link":i["link"],"title":i["title"]})
    # return [r["link"] for r in links if "link" in r]
    return links

async def deduplicate(query:str):
    results = await search_web(query)
    seen = set()
    unique = []
    for r in results:
        print("before url :", r["link"])
        domain = get_domain(r["link"])
        title = r["title"].strip().lower()
        key = (domain, title)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique