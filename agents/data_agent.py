import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_pick import pick_llm
from utils.etl_tools import ETLTools
from Models.schema import RouterSchema, DataAgentSchema
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst

llm = pick_llm("low")
llm_router = llm.with_structured_output(RouterSchema)

# -- Data Agent Graph --
def router_node(state: DataAgentSchema):
    message = state.messages[-1].content

    response_dict = llm_router.invoke(message).model_dump()
    router_res = response_dict["answer"]
    state.router_response = router_res
    return state

def sql_node(state: DataAgentSchema):
    message = state.messages[-1].content

    input_schema = {
        "messages": [],
        "user_question": f"{message}",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    res = sql_analyst.invoke(input_schema)
    return {"messages": [res]}

def etl_node(state: DataAgentSchema):
    message = state.messages[-1].content

    res = etl_analyst.invoke({
        "messages": [HumanMessage(content=f"{message}")]
    })

    return {"messages": [res]}


data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("sql_node", sql_node)
data_agent_graph.add_node("etl_node", etl_node)

data_agent_graph.add_edge(START, "router_node")
def sql_or_etl(state: DataAgentSchema):
    if state.router_response == "ETL":
        return "etl_node"
    elif state.router_response == "SQL":
        return "sql_node"
    else:
        raise ValueError(f"Invalid route resposne: {state.router_response}")


data_agent_graph.add_conditional_edges(
    "router_node",
    sql_or_etl,
    {
        "etl_node": "etl_node",
        "sql_node": "sql_node"
    }
)

data_agent = data_agent_graph.compile()

from IPython.display import display, Image
img = Image(data_agent.get_graph().draw_mermaid_png())
with open("data_agent_graph.png", "wb") as f:
    f.write(img.data)

if __name__ == "__main__":
    response = data_agent.invoke(
        {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")],
         "router_response": ""}
    )

    print(response)