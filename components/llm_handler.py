# components/llm_handler.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from config.settings import LLM_MODEL_NAME

class LLMHandler:
    @staticmethod
    def get_conversational_rag_chain(retriever):
        """ Builds and returns a conversational RAG chain. """
        llm = ChatGoogleGenerativeAI(model=LLM_MODEL_NAME, temperature=0.7)
        
        contextualize_q_system_prompt = """Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."""
        contextualize_q_prompt = ChatPromptTemplate.from_messages([("system", contextualize_q_system_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")])
        history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)
        
        qa_system_prompt = """You are an expert assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Be concise and helpful.\n\n{context}"""
        qa_prompt = ChatPromptTemplate.from_messages([("system", qa_system_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")])
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        
        return create_retrieval_chain(history_aware_retriever, question_answer_chain)