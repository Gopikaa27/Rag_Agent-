# components/vector_store.py
import os
import streamlit as st
from supabase import create_client, Client
from langchain_community.vectorstores import SupabaseVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config.settings import EMBEDDING_MODEL_NAME

class VectorStoreManager:
    """ Manages interactions with the Supabase vector store. """
    def __init__(self, username: str):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        self.supabase_client: Client = create_client(url, key)
        self.username = username
        self.table_name = "documents"

    @staticmethod
    @st.cache_resource(ttl="1h")
    def get_embeddings_model():
        """ Returns the embeddings model, cached for performance. """
        return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME)

    def get_vector_store(self) -> SupabaseVectorStore:
        """ Connects to and returns a handle to the Supabase vector store. """
        embeddings = self.get_embeddings_model()
        return SupabaseVectorStore(
            client=self.supabase_client,
            table_name=self.table_name,
            embedding=embeddings,
            query_name="match_documents"
        )

    def add_documents(self, docs: list):
        """ Processes and adds new documents to the Supabase vector store. """
        if not docs:
            return
        
        st.sidebar.info("Processing and adding documents...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        
        # Ensure all document chunks have username in metadata
        for split in splits:
            if split.metadata is None:
                split.metadata = {}
            split.metadata['username'] = self.username

        vector_store = self.get_vector_store()
        vector_store.add_documents(splits)
        st.sidebar.success("Documents added successfully!")
        
        # Clear any cached document sources to force refresh
        if hasattr(self, '_cached_sources'):
            delattr(self, '_cached_sources')

    def get_document_sources(self) -> list[str]:
        """
        Retrieves a list of unique source document filenames for the current user.
        Forces fresh data from database without caching.
        """
        try:
            # Query documents table with username filter
            response = self.supabase_client.table(self.table_name)\
                .select("metadata")\
                .contains("metadata", {"username": self.username})\
                .execute()
            
            if response.data:
                sources = set()
                for item in response.data:
                    metadata = item.get("metadata", {})
                    # Check if this document belongs to the current user
                    if metadata.get("username") == self.username:
                        source = metadata.get("source")
                        if source:
                            # Extract just the filename
                            sources.add(os.path.basename(source))
                return sorted(list(sources))
            return []
        except Exception as e:
            st.error(f"Error fetching document sources: {e}")
            return []

    def delete_document(self, source_filename: str):
        """
        Deletes all chunks of a document for the current user.
        """
        try:
            # Delete all document chunks that match the source filename and username
            response = self.supabase_client.table(self.table_name)\
                .delete()\
                .contains("metadata", {"username": self.username})\
                .like("metadata->source", f"%{source_filename}%")\
                .execute()
            
            st.sidebar.success(f"Document '{source_filename}' deleted successfully!")
            return True
        except Exception as e:
            st.error(f"Error deleting document: {e}")
            return False