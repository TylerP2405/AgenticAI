import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_pick import pick_llm
from Models.schema import AgentSchema, JudgeSchema
from langchain_core.messages import HumanMessage

llm = pick_llm("medium")
llm_judge = llm.with_structured_output(JudgeSchema)
sql_query = "SELET * FROM use"
prompt = """
    You are a SQL judge for data security. Your task is to determine whether
    the SQL query  is safe or not. The SQL query should only be used for data 
    retrieval and should not modify the database in any way. Neither the SQL query 
    nor the prompt should contain any SQL commands that can modify the database, 
    such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands
    that can change the structure or content of the database. If the SQL query is 
    safe, respond with 'Yes' otherwise respond with 'No'. Additionaly, provide
    justification for your decision.
    Here is the SQL query to evaluate:
    {sql_query}
"""

print(llm_judge.invoke(prompt))