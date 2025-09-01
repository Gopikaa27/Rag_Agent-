# components/document_processor.py
import os
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from streamlit.runtime.uploaded_file_manager import UploadedFile

class DocumentProcessor:
    @staticmethod
    def process_uploaded_files(uploaded_files: list[UploadedFile]) -> list:
        """ Loads content from uploaded files based on their extension. """
        docs = []
        for file in uploaded_files:
            temp_filepath = Path(f"./temp_{file.name}")
            with open(temp_filepath, "wb") as f:
                f.write(file.getbuffer())

            file_extension = temp_filepath.suffix.lower()
            loader = None
            if file_extension == ".pdf":
                loader = PyPDFLoader(str(temp_filepath))
            elif file_extension == ".txt":
                loader = TextLoader(str(temp_filepath))
            elif file_extension == ".docx":
                loader = Docx2txtLoader(str(temp_filepath))
            else:
                print(f"Unsupported file type: {file_extension}")
                os.remove(temp_filepath)
                continue

            docs.extend(loader.load())
            os.remove(temp_filepath)
        return docs