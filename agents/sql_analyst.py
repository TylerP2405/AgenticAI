import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_pick import pick_llm
from utils.db_conn import DatabaseUtil
from Models.schema import AgentSchema, JudgeSchema
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

# -- AI Agent Code -- 
def curate_question(state: AgentSchema) -> AgentSchema:
    
    user_question = state.user_question # This is pydanntic model object not dictionary object

    llm = pick_llm("low") # Pick the appropriate LLM based on the level of question

    response = llm.invoke(f"Curate the following question: {user_question}")

    state.curated_question = response.content
    state.messages = state.messages + [HumanMessage(content=f"{response.content}")]
    return state

def prompt_query_context(state: AgentSchema) -> AgentSchema:

    curated_question = state.curated_question

    conn_details = {
        "host": os.environ['host'],
        "port": os.environ['port'],
        "user": os.environ['user'],
        "password": os.environ['password'],
        "database": os.environ['database']
    }

    db_obj = DatabaseUtil(conn_details)

    schema_info = db_obj.schema_details("public")

    prompt = f"""
        You are an SQL analyst agent. Your task is to convert the user's natural language
        query into Postgres SQL query that can be executed on the database. You are provided
        with the user's original query and the schema details of the database, including
        table names, column names, data types, and sample data for each table so that
        you can understand the structure of the database and generate an accurate SQL query.
        Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
        Note - Just generate the SQL query without any explanation or additional text because
        this query will be executed directly on the database. So, the output should be SQL
        ready to be executed without any modifications.

        User's Original Query: {curated_question}

        Database Schema Details:
        {schema_info}
    """

    state.prompt_query_context = prompt

    return state


def generate_sql(state: AgentSchema) -> AgentSchema:
    llm = pick_llm("medium")
    generated_sql_query = llm.invoke(state.prompt_query_context)
    state.generated_sql_query = generated_sql_query.content
    return state

def is_safe(state: AgentSchema) -> AgentSchema:
    generated_sql_query = state.generated_sql_query

    llm = pick_llm("medium")
    llm_judge = llm.with_structured_output(JudgeSchema)
    prompt = f"""
    You are a SQL judge for data security. Your task is to determine whether
    the SQL query  is safe or not. The SQL query should only be used for data 
    retrieval and should not modify the database in any way. Neither the SQL query 
    nor the prompt should contain any SQL commands that can modify the database, 
    such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands
    that can change the structure or content of the database. If the SQL query is 
    safe, respond with 'Yes' otherwise respond with 'No'. Additionaly, provide
    justification for your decision.
    Here is the SQL query to evaluate:
    {generated_sql_query}
    """
    response = llm_judge.invoke(prompt).model_dump()
    state.is_safe = response['answer']
    state.justification = response['justification']
    return state

def cancel_sql(state: AgentSchema) -> AgentSchema:
    state.final_answer = f"""
    The generated SQL query was deemed unsafe to execute. Here is the justification {state.justification}
    """
    state.messages = state.messages + [AIMessage(content=f"{state.final_answer}")]
    return state

def execute_sql(state: AgentSchema) -> AgentSchema:
    db = DatabaseUtil({
        "host": os.environ['host'],
        "port": int(os.environ['port']),
        "database": os.environ['database'],
        "user": os.environ['user'],
        "password": os.environ['password'],
    })
    res = db.execute_sql(state.generated_sql_query)
    state.sql_query_execution_result = res
    return state

def represent_final_answer(state: AgentSchema) -> AgentSchema:
    res = state.sql_query_execution_result
    question = state.curated_question

    llm = pick_llm("low")
    prompt = prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in
    Here is the execution result: {res} \n
    Here is the user's original question: {question}
    """
    llm_response = llm.invoke(prompt).content
    state.final_answer = llm_response
    state.messages = state.messages + [AIMessage(content=f"{state.final_answer}")]
    return state

# --- Graph Building ---
sql_agent_graph = StateGraph(AgentSchema)

# Nodes
sql_agent_graph.add_node(curate_question, name="curate_question")
sql_agent_graph.add_node(prompt_query_context, name="prompt_query_context")
sql_agent_graph.add_node(generate_sql, name="generate_sql")
sql_agent_graph.add_node(is_safe, name="is_safe")
sql_agent_graph.add_node(cancel_sql, name="cancel_sql")
sql_agent_graph.add_node(execute_sql, name="execute_sql")
sql_agent_graph.add_node(represent_final_answer, name="represent_final_answer")

# Edge
sql_agent_graph.add_edge(START, "curate_question")
sql_agent_graph.add_edge("curate_question", "prompt_query_context")
sql_agent_graph.add_edge("prompt_query_context", "generate_sql")
sql_agent_graph.add_edge("generate_sql", "is_safe")

# Conditional Edge
def is_safe_sql_edge(state: AgentSchema) -> str:
    is_safe = state.is_safe
    if is_safe.lower() == 'yes':
        return "Yes"
    else:
        return "No"

sql_agent_graph.add_conditional_edges("is_safe", is_safe_sql_edge, {"Yes": "execute_sql", "No":"cancel_sql"})
# sql_agent_graph.add_edge("is_safe", "cancel_sql")
# sql_agent_graph.add_edge("is_safe", "execute_sql")
sql_agent_graph.add_edge("cancel_sql", END)
sql_agent_graph.add_edge("execute_sql", "represent_final_answer")
sql_agent_graph.add_edge("represent_final_answer", END)

# Compile the Graph
sql_analyst = sql_agent_graph.compile()

if __name__ == "__main__":

    from IPython.display import display, Image
    img = Image(sql_analyst.get_graph().draw_mermaid_png())
    with open("sql_analyst_graph.png", "wb") as f:
        f.write(img.data)
    
    print("SQL Analyst: Ask me a question about your database.\n")
    print("Type 'done' to quit.\n")

    while True:
        user_question = input("You: ").strip()
        if user_question.lower() in ('done', 'exit', 'quit'): 
            print("SQL Analyst: Goodbye")
            break
        if not user_question:
            continue
        input_schema = {
        "messages": [],
        "user_question": user_question,
        "curated_question": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "justification": "",
        "sql_query_execution_result": "",
        "final_answer": ""
        }
        try:
            sql_analyst_response = sql_analyst.invoke(input_schema)
            print(sql_analyst_response['messages'])
            print("*********************************")
            print(sql_analyst_response['generated_sql_query'])
            print("*********************************")
            print(sql_analyst_response['sql_query_execution_result'])
            print("*********************************")
            print(sql_analyst_response['prompt_query_context'])
        except Exception as e:
            print(f"\nCould not process your question: {e}\n")
