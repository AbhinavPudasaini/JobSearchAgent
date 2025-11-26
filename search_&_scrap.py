import re
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_community.document_loaders import PyPDFLoader, SitemapLoader, RecursiveUrlLoader, WebBaseLoader, PlaywrightURLLoader, AsyncHtmlLoader
from langchain_community.tools import DuckDuckGoSearchResults
from urllib.parse import urlparse


queries = [
    "golden opportunities for entrepreneurs in 2025",
    "high‑potential business strategies to build a million‑dollar company",
    "trending industries with the highest ROI in 2025",
    "scalable business models that can generate a million dollars",
    "tools and tactics for creating a million‑dollar business"
]


def get_domain(url):
    return urlparse(url).netloc

def deduplicate(results):
    seen = set()
    unique = []
    for r in results:
        print("before url :", r["url"])
        domain = get_domain(r["url"])
        title = r["title"].strip().lower()
        key = (domain, title)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique

links = []
def search_web(query:str):
    """
    """
    web = DuckDuckGoSearchResults(output_format='list')
    results = web.invoke(query)
    for i in results:
        links.append({"url":i["link"],"title":i["title"]})
 
# def Scrape(query:str):
#     """
#     """
#     search_web(query=query)
#     # print(links)
#     with open("scraps.txt", "w", encoding="utf-8") as f:
#         for i in links:
#             scraper = WebBaseLoader(web_path=i)
#             load = scraper.load()
#             doc = load[0].page_content  
#             clean_text = " ".join(doc.split())
#             f.write(clean_text)
#             f.write("\n" + "="*64 + "\n")

if __name__ == "__main__":
    for i in queries:
        search_web(i)
        print(f"-----------------------Completed {i}----------------")
    results = deduplicate(links)
    print(f"these are results from i : ", results)




