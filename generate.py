import os
from typing import List, TypedDict, Annotated
import operator
import asyncio

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AnyMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.prebuilt import create_react_agent

from defineNode import parse_intent_node, aggregator_node, generate_queries_node, search_and_scrape_node, AgentState

load_dotenv()

# --- Agent State Definition ---


# --- Graph Definition ---
builder = StateGraph(AgentState)

builder.add_node("parse_intent", parse_intent_node)
builder.add_node("generate_queries", generate_queries_node)
builder.add_node("search_and_scrape", search_and_scrape_node)
builder.add_node("aggregator", aggregator_node)

# --- Graph Edges ---
builder.add_edge(START, "parse_intent")
builder.add_edge("parse_intent", "generate_queries")
builder.add_edge("generate_queries", END)
# builder.add_edge("search_and_scrape", "aggregator")
# builder.add_edge("aggregator", END)

# Compile the graph
graph = builder.compile()

# --- Visualization ---
# try:
#     png_data = graph.get_graph().draw_mermaid_png()
#     img = PILImage.open(BytesIO(png_data))
#     img.show()
#     print("Graph visualization displayed.")
# except Exception as e:
#     print(f"Could not generate graph visualization: {e}")

async def main():
    """Main function to run the agent asynchronously."""
    user_input = "What are the gold in todays era and what are the potential shovel, that can make you million dollar in business"
    
    print("Running the agent with your input...")
    result = await graph.ainvoke({"messages": [HumanMessage(content=user_input)]})
    
    print("\n--- Agent Finished ---")
    print("Final Answer:")
    print(result['messages'][-1].content)

if __name__ == "__main__":
    print("Graph compiled. Starting agent execution...")
    asyncio.run(main())
