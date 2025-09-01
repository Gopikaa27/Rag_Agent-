# app.py
import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from config.settings import DEFAULT_CHAT_NAME
from components.vector_store import VectorStoreManager
from components.document_processor import DocumentProcessor
from components.llm_handler import LLMHandler
from components.conversation_manager import ConversationManager
from langchain_core.messages import AIMessage, HumanMessage

class RAGAgentUI:
    def __init__(self):
        load_dotenv()
        self._initialize_session_state()
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)

    def _initialize_session_state(self):
        defaults = {
            "logged_in": False, 
            "username": "", 
            "current_chat": DEFAULT_CHAT_NAME, 
            "messages": [], 
            "prev_chat": "",
            "chat_counter": 1  # Add counter for new chats
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def _render_auth_page(self):
        st.title("🔐 RAG Agent Login")
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email").lower()
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    try:
                        user = self.supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.logged_in = True
                        st.session_state.username = user.user.email # Use full email as unique username
                        st.rerun()
                    except Exception as e:
                        st.error(f"Login failed: {e}")

        with signup_tab:
            with st.form("signup_form"):
                email = st.text_input("Email", key="signup_email").lower()
                password = st.text_input("Password", type="password", key="signup_password")
                if st.form_submit_button("Sign Up"):
                    try:
                        user = self.supabase.auth.sign_up({"email": email, "password": password})
                        st.success("Sign up successful! Please check your email to verify.")
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")

    def _render_sidebar(self, conv_manager: ConversationManager, vs_manager: VectorStoreManager):
        with st.sidebar:
            st.title(f"Welcome, {st.session_state.username.split('@')[0]}!")
            
            st.header("Manage Knowledge Base")
            uploaded_files = st.file_uploader("Upload files", type=["pdf", "txt", "docx"], accept_multiple_files=True)
            if uploaded_files and st.button("Process Files"):
                with st.spinner("Processing documents..."):
                    docs = DocumentProcessor.process_uploaded_files(uploaded_files)
                    vs_manager.add_documents(docs)
                    st.rerun()  # Refresh to show updated document list
            
            # --- Display Existing Documents ---
            st.divider()
            st.header("Knowledge Base Files")
            # Force refresh of document sources
            sources = vs_manager.get_document_sources()
            if sources:
                for source in sources:
                    st.info(f"📄 {source}")
            else:
                st.info("No documents uploaded yet.")

            st.divider()
            st.header("Manage Chats")
            available_chats = conv_manager.get_available_chats()
            
            # --- FIXED NEW CHAT LOGIC ---
            if st.button("➕ New Chat"):
                # Save the current chat before creating a new one, if it has messages
                if st.session_state.messages:
                    conv_manager.save_history(st.session_state.current_chat, st.session_state.messages)

                # Create a truly unique new chat name with timestamp
                import datetime
                timestamp = datetime.datetime.now().strftime("%m-%d_%H-%M-%S")
                new_chat_name = f"New Chat {timestamp}"
                
                # Ensure uniqueness by checking available chats
                counter = 1
                original_name = new_chat_name
                while new_chat_name in available_chats:
                    counter += 1
                    new_chat_name = f"{original_name}_{counter}"
                
                # Actually create the new chat in database
                success = conv_manager.create_new_chat(new_chat_name)
                if success:
                    # Switch to new chat session
                    st.session_state.current_chat = new_chat_name
                    st.session_state.messages = []
                    st.session_state.prev_chat = ""  # Reset to force reload
                    st.success(f"Created new chat: {new_chat_name}")
                    st.rerun()
                else:
                    st.error("Failed to create new chat")

            # Display chat selector
            if available_chats:
                try:
                    # Ensure current chat exists in available chats
                    if st.session_state.current_chat not in available_chats:
                        st.session_state.current_chat = available_chats[0]
                    
                    idx = available_chats.index(st.session_state.current_chat)
                except (ValueError, IndexError):
                    idx = 0
                    st.session_state.current_chat = available_chats[0] if available_chats else DEFAULT_CHAT_NAME
                
                selected_chat = st.selectbox(
                    "Select a Chat", 
                    options=available_chats, 
                    index=idx, 
                    key=f"chat_selector_{len(available_chats)}"  # Dynamic key to force refresh
                )
                
                if selected_chat != st.session_state.current_chat:
                    # Save current chat before switching
                    if st.session_state.messages and st.session_state.current_chat:
                        conv_manager.save_history(st.session_state.current_chat, st.session_state.messages)
                    
                    # Switch to selected chat
                    st.session_state.current_chat = selected_chat
                    st.session_state.prev_chat = ""  # Reset to force reload
                    st.rerun()
            else:
                # No chats available, create default chat
                if not st.session_state.current_chat:
                    st.session_state.current_chat = DEFAULT_CHAT_NAME

            if st.button("Logout"):
                self.supabase.auth.sign_out()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    def _render_chat_interface(self, conv_manager: ConversationManager, vs_manager: VectorStoreManager):
        # Load chat history when switching chats or on first load
        if st.session_state.prev_chat != st.session_state.current_chat:
            # Save current messages before loading new chat (if different chat)
            if st.session_state.prev_chat and st.session_state.messages and st.session_state.prev_chat != st.session_state.current_chat:
                conv_manager.save_history(st.session_state.prev_chat, st.session_state.messages)
            
            # Load new chat history
            st.session_state.messages = conv_manager.load_history(st.session_state.current_chat)
            st.session_state.prev_chat = st.session_state.current_chat

        # Chat renaming and deletion
        col1, col2 = st.columns([5, 1])
        with col1:
            new_name = st.text_input("Chat Name", value=st.session_state.current_chat, key=f"rename_{st.session_state.current_chat}")
            if new_name != st.session_state.current_chat and new_name.strip():
                conv_manager.rename_chat(st.session_state.current_chat, new_name.strip())
                st.session_state.current_chat = new_name.strip()
                st.rerun()
        with col2:
            st.write("\n\n")
            if st.button("🗑️ Delete Chat"):
                conv_manager.delete_chat(st.session_state.current_chat)
                st.session_state.current_chat = DEFAULT_CHAT_NAME
                st.session_state.messages = []
                st.session_state.prev_chat = ""
                st.rerun()

        # Display chat messages
        for msg in st.session_state.messages:
            with st.chat_message(msg.type):
                st.markdown(msg.content)

        # Chat input
        if prompt := st.chat_input("Ask me anything about your documents..."):
            st.session_state.messages.append(HumanMessage(content=prompt))
            with st.chat_message("human"):
                st.markdown(prompt)
            
            with st.chat_message("ai"):
                with st.spinner("Thinking..."):
                    vector_store = vs_manager.get_vector_store()
                    # Fixed: Properly pass filter with username
                    retriever = vector_store.as_retriever(
                        search_kwargs={
                            'filter': {'username': st.session_state.username},
                            'k': 5  # Number of documents to retrieve
                        }
                    )
                    chain = LLMHandler.get_conversational_rag_chain(retriever)
                    response = chain.invoke({
                        "input": prompt, 
                        "chat_history": st.session_state.messages[:-1]
                    })
                    st.markdown(response["answer"])
            
            st.session_state.messages.append(AIMessage(content=response["answer"]))
            # Auto-save after each message
            conv_manager.save_history(st.session_state.current_chat, st.session_state.messages)

    def run(self):
        if not st.session_state.logged_in:
            self._render_auth_page()
        else:
            st.set_page_config(page_title=f"RAG Agent", layout="wide")
            conv_manager = ConversationManager(username=st.session_state.username)
            vs_manager = VectorStoreManager(username=st.session_state.username)
            self._render_sidebar(conv_manager, vs_manager)
            self._render_chat_interface(conv_manager, vs_manager)

if __name__ == "__main__":
    ui = RAGAgentUI()
    ui.run()