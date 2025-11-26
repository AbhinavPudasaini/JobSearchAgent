from prompts import parse_prompt, generate_prompt,aggregator_prompt
import os

import asyncio

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, ToolMessage
from langgraph.types import Send
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, START, END, add_messages
from typing import List, TypedDict, Annotated
import operator
from helperFunction import format_query_list, scrape_web_page,search_web, deduplicate

load_dotenv()

class AgentState(TypedDict):
    queries: List[str]
    messages: Annotated[List[AnyMessage], add_messages]
    docs: Annotated[List[ToolMessage], operator.add]

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

llm = ChatGroq(model="openai/gpt-oss-20b", api_key=api_key)
agent = create_react_agent(model=llm, tools=[])

def parse_intent_node(state: AgentState):
    """Parses the user's initial query."""
    user_message = state["messages"][-1]
    system_message = SystemMessage(content=parse_prompt)
    
    response = agent.invoke({"messages": [system_message, user_message]})
    
    return {"messages": [response["messages"][-1]]}

def generate_queries_node(state: AgentState):
    """Generates search queries based on the parsed intent."""
    system_message = SystemMessage(content=generate_prompt)
    
    response = agent.invoke({"messages": [system_message] + state["messages"]})
    
    queries = format_query_list(response["messages"][-1].content)
    
    return {"messages": [response["messages"][-1]], "queries": queries}

async def search_and_scrape_node(state: AgentState) -> dict:
    """
    Processes all queries: searches for links and scrapes them in parallel.
    """
    queries = state["queries"]
    all_docs = []

    # Create a list of scraping tasks for all links from all queries
    scraping_tasks = []
    for query in queries:
        links = await deduplicate(query)
        for i, link in enumerate(links):
            task = scrape_web_page(link["url"])
            scraping_tasks.append(
                (query, i, task)
            )

    # Run all scraping tasks concurrently
    results = await asyncio.gather(*[task for _, _, task in scraping_tasks])

    # Create ToolMessages from the results
    for (query, i, _), content in zip(scraping_tasks, results):
        tool_message = ToolMessage(
            content=content, tool_call_id=f"search_result_{query}_{i}"
        )
        all_docs.append(tool_message)

    return {"docs": all_docs}

def aggregator_node(state: AgentState):
    """Aggregates all the scraped content into a final answer."""
    user_question = state["messages"][0].content
    scraped_content = "\n\n".join([doc.content for doc in state["docs"]])
    
    prompt = aggregator_prompt.format(
        user_question=user_question, scraped_content=scraped_content
    )
    
    system_message = SystemMessage(content=prompt)
    response = agent.invoke({"messages": [system_message]})
    
    return {"messages": [response["messages"][-1]]}
