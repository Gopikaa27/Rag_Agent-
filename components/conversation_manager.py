# components/conversation_manager.py
import os
from supabase import create_client, Client
from langchain_core.messages import AIMessage, HumanMessage
import datetime

class ConversationManager:
    """ Manages chat histories using Supabase. """
    def __init__(self, username: str):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)
        self.username = username
        self.table_name = "chats"

    def load_history(self, chat_name: str) -> list:
        """ Loads a specific chat history from a Supabase row. """
        try:
            response = self.supabase.table(self.table_name)\
                .select("messages")\
                .eq("username", self.username)\
                .eq("chat_name", chat_name)\
                .execute()
            
            if response.data:
                history_data = response.data[0].get("messages", [])
                return [
                    HumanMessage(content=msg['content']) if msg['type'] == 'human' 
                    else AIMessage(content=msg['content']) 
                    for msg in history_data
                ]
            return []
        except Exception as e:
            print(f"Error loading chat history: {e}")
            return []

    def save_history(self, chat_name: str, history: list):
        """ Saves the current chat history to a Supabase row. """
        try:
            # Convert messages to JSON format
            history_json = [
                {'type': 'human', 'content': msg.content} if isinstance(msg, HumanMessage) 
                else {'type': 'ai', 'content': msg.content} 
                for msg in history
            ]
            
            # Check if updated_at column exists
            try:
                # Try with updated_at column
                self.supabase.table(self.table_name).upsert({
                    "username": self.username, 
                    "chat_name": chat_name, 
                    "messages": history_json,
                    "updated_at": datetime.datetime.now().isoformat()
                }).execute()
            except Exception:
                # Fall back to basic upsert without updated_at
                self.supabase.table(self.table_name).upsert({
                    "username": self.username, 
                    "chat_name": chat_name, 
                    "messages": history_json
                }).execute()
                
        except Exception as e:
            print(f"Error saving chat history: {e}")

    def get_available_chats(self) -> list:
        """ Retrieves a list of all chat names for the current user. """
        try:
            # Try to get chats with updated_at column for ordering
            try:
                response = self.supabase.table(self.table_name)\
                    .select("chat_name, updated_at")\
                    .eq("username", self.username)\
                    .order("updated_at", desc=True)\
                    .execute()
            except Exception:
                # Fall back to basic query without updated_at ordering
                response = self.supabase.table(self.table_name)\
                    .select("chat_name")\
                    .eq("username", self.username)\
                    .execute()
            
            return [item['chat_name'] for item in response.data] if response.data else []
        except Exception as e:
            print(f"Error fetching available chats: {e}")
            return []

    def rename_chat(self, old_name: str, new_name: str):
        """ Renames a chat by updating the 'chat_name' in the row. """
        if not new_name or new_name == old_name:
            return False
        
        try:
            # Check if new name already exists
            existing_response = self.supabase.table(self.table_name)\
                .select("chat_name")\
                .eq("username", self.username)\
                .eq("chat_name", new_name)\
                .execute()
            
            if existing_response.data:
                print(f"Chat name '{new_name}' already exists")
                return False
            
            # Update the chat name
            try:
                # Try with updated_at column
                self.supabase.table(self.table_name)\
                    .update({
                        "chat_name": new_name, 
                        "updated_at": datetime.datetime.now().isoformat()
                    })\
                    .eq("username", self.username)\
                    .eq("chat_name", old_name)\
                    .execute()
            except Exception:
                # Fall back to basic update without updated_at
                self.supabase.table(self.table_name)\
                    .update({"chat_name": new_name})\
                    .eq("username", self.username)\
                    .eq("chat_name", old_name)\
                    .execute()
            
            return True
        except Exception as e:
            print(f"Error renaming chat: {e}")
            return False

    def delete_chat(self, chat_name: str):
        """ Deletes a chat row from the Supabase table. """
        try:
            self.supabase.table(self.table_name)\
                .delete()\
                .eq("username", self.username)\
                .eq("chat_name", chat_name)\
                .execute()
        except Exception as e:
            print(f"Error deleting chat: {e}")

    def create_new_chat(self, chat_name: str) -> bool:
        """ Creates a new empty chat session. """
        try:
            # Check if chat already exists
            existing_response = self.supabase.table(self.table_name)\
                .select("chat_name")\
                .eq("username", self.username)\
                .eq("chat_name", chat_name)\
                .execute()
            
            if existing_response.data:
                print(f"Chat '{chat_name}' already exists")
                return False  # Chat already exists
            
            # Create new chat with empty messages
            try:
                # Try with all timestamp columns
                result = self.supabase.table(self.table_name).insert({
                    "username": self.username,
                    "chat_name": chat_name,
                    "messages": [],
                    "created_at": datetime.datetime.now().isoformat(),
                    "updated_at": datetime.datetime.now().isoformat()
                }).execute()
            except Exception as e:
                print(f"Error with timestamps, trying basic insert: {e}")
                # Fall back to basic insert without timestamp columns
                result = self.supabase.table(self.table_name).insert({
                    "username": self.username,
                    "chat_name": chat_name,
                    "messages": []
                }).execute()
            
            print(f"Successfully created new chat: {chat_name}")
            return True
            
        except Exception as e:
            print(f"Error creating new chat: {e}")
            return False