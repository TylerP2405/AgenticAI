from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

def pick_llm(level: str):
    # Pick the appropriate LLM based on the level of the question
    if level.lower() == "low":
        llm = ChatOpenAI(model_name="gpt-6-luna", model_kwargs={
            "reasoning_effor": "none"
        })
    elif level.lower() == "medium":
        llm = ChatOpenAI(model_name="gpt-6.1-terra", model_kwargs={
            "reasoning_effor": "none"
        })
    elif level.lower() == "high":
        llm = ChatOpenAI(model_name="gpt-6-sol", model_kwargs={
            "reasoning_effor": "none"
        })
    else:
        raise ValueError(f"Unsupported level: {level}")
    return llm
