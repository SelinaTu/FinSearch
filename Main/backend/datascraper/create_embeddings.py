# create_embeddings.py
from dotenv import load_dotenv
import os
# import openai # OpenAI no longer needed for embeddings here
import pickle
import numpy as np
import faiss
# import json # json was not used
from sentence_transformers import SentenceTransformer # Added

# Load environment variables (still potentially useful for other keys, or if LLM calls were here)
load_dotenv()
# api_key = os.getenv("API_KEY7") # No longer needed for OpenAI embeddings
# openai.api_key = api_key # No longer needed for OpenAI embeddings

# Initialize Sentence Transformer model
# This model produces 384-dimensional embeddings.
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

current_dir = os.path.dirname(os.path.abspath(__file__))
index_file = os.path.join(current_dir, 'faiss_index.idx')
embeddings_file = os.path.join(current_dir, 'embeddings.pkl')

# Helper function to generate embeddings using local model
def embed_file_content(file_content):
    """
    Function to generate embeddings for file content using a local Sentence Transformer model.
    """
    # The model.encode() returns a numpy array.
    # FAISS typically expects float32 numpy arrays.
    # .tolist() is not strictly necessary here if downstream functions handle numpy arrays,
    # but if previous code expected lists, this maintains consistency.
    # For FAISS, numpy array is better.
    embedding_vector = embedding_model.encode(file_content, convert_to_numpy=True)
    return embedding_vector # Return as numpy array

# Helper function to store embeddings (pickling embeddings)
# This function remains largely the same, but will now store Sentence Transformer embeddings
def store_embeddings(chunks_list): # Changed signature to accept chunks_list directly
    """
    Store the generated embeddings (as part of chunks_list) into a pickle file.
    Each item in chunks_list should be a dict with "text", "metadata", and "embedding".
    """
    with open(embeddings_file, 'wb') as f:
        pickle.dump(chunks_list, f)
    print(f"Stored {len(chunks_list)} chunks with embeddings to {embeddings_file}")


# Helper function to create a FAISS index
def create_faiss_index(chunks):
    """
    Create and store a FAISS index from the embeddings in `chunks`.
    Each item in `chunks` is expected to be a dict with key "embedding".
    The embeddings from 'all-MiniLM-L6-v2' are 384-dimensional.
    """
    if not chunks:
        print("No chunks provided to create FAISS index.")
        return

    # Infer dimension from the first embedding. 
    # For 'all-MiniLM-L6-v2', this will be 384.
    dimension = chunks[0]["embedding"].shape[0] # Accessing shape of numpy array
    
    # Using IndexFlatL2 as SentenceTransformer('all-MiniLM-L6-v2') embeddings are normalized 
    # and work well with L2 distance for similarity ranking (equivalent to cosine similarity ranking).
    index = faiss.IndexFlatL2(dimension) 
    print(f"Creating FAISS index with dimension: {dimension}")

    # Extract all embeddings into a NumPy array of type float32
    embeddings_np = np.array(
        [chunk["embedding"] for chunk in chunks], dtype='float32'
    )
    
    # FAISS expects normalized embeddings for IndexFlatL2 if you want it to behave like cosine similarity.
    # SentenceTransformer('all-MiniLM-L6-v2') already produces normalized embeddings (unit length).
    # So, no explicit normalization step is needed here before adding to FAISS.
    # If they weren't normalized, you would do: faiss.normalize_L2(embeddings_np)

    index.add(embeddings_np)
    print(f"FAISS index created. Total embeddings added: {index.ntotal}. Numpy shape of added embeddings: {embeddings_np.shape}")

    faiss.write_index(index, index_file)
    print(f"FAISS index saved to {index_file}")

def upload_folder(data):
    """
    Process incoming files, generate embeddings locally, and store chunk dictionaries.
    Then, create a FAISS index from these embeddings.
    """
    try:
        print("[DEBUG] Starting upload_folder with data keys:", data.keys() if isinstance(data, dict) else "Not a dict")

        chunks_list = []
        files = data.get('filePaths', [])
        print(f"[DEBUG] Found {len(files)} file(s) in data.")

        for file_item in files:
            file_name = file_item.get('name')
            file_content = file_item.get('content')
            if file_name and file_content:
                print(f"[DEBUG] Processing file: {file_name} (content length: {len(file_content)})")
                
                embedding_vector = embed_file_content(file_content)
                
                chunk_dict = {
                    "text": file_content,
                    "metadata": {"file_path": file_name},
                    "embedding": embedding_vector # Storing numpy array
                }
                chunks_list.append(chunk_dict)
            else:
                print(f"[DEBUG] Skipping file item due to missing name or content: {file_item}")

        if not chunks_list:
            print("[DEBUG] No valid file content processed. No embeddings generated.")
            return {"message": "No valid files processed. Nothing to embed."}, 200 # Or 400 for bad request

        # Store the list of chunks (which includes embeddings)
        store_embeddings(chunks_list) 
        print(f"[DEBUG] Saved {len(chunks_list)} chunks with their embeddings to {embeddings_file}")

        # Create a FAISS index from the generated embeddings
        create_faiss_index(chunks_list)
        print("[DEBUG] FAISS index creation process completed.")

        return {"message": "Files processed, local embeddings stored, and FAISS index created."}, 200

    except Exception as e:
        print(f"[ERROR] Unexpected error in upload_folder: {str(e)}")
        # Consider logging the full traceback here for better debugging
        import traceback
        traceback.print_exc()
        return {"error": f"Server error processing files: {str(e)}"}, 500

if __name__ == '__main__':
    # Example usage for testing create_embeddings.py directly
    print("Running create_embeddings.py directly for testing...")
    
    # Mock data similar to what might come from an upload
    mock_file_data = {
        'filePaths': [
            {'name': 'test_doc_1.txt', 'content': 'This is the first test document about financial markets and investments.'},
            {'name': 'test_doc_2.txt', 'content': 'Another document discussing economic policies and their impact on stock prices.'},
            {'name': 'test_doc_3.txt', 'content': 'A short note on cryptocurrency trends in 2024.'}
        ]
    }
    
    print(f"Mock data: {json.dumps(mock_file_data, indent=2)}") # Requires json import if used
    
    response, status_code = upload_folder(mock_file_data)
    
    print(f"\nTest run completed. Status: {status_code}")
    print(f"Response: {response}")

    # Verify files created (optional manual check)
    if os.path.exists(embeddings_file):
        print(f"\n{embeddings_file} created. Size: {os.path.getsize(embeddings_file)} bytes")
        # Optionally load and inspect the pickle file
        with open(embeddings_file, 'rb') as f:
            loaded_chunks = pickle.load(f)
            print(f"Number of items in loaded pickle: {len(loaded_chunks)}")
            if loaded_chunks:
                print(f"First item's embedding shape: {loaded_chunks[0]['embedding'].shape}")
                print(f"First item's metadata: {loaded_chunks[0]['metadata']}")


    if os.path.exists(index_file):
        print(f"{index_file} created. Size: {os.path.getsize(index_file)} bytes")
        # Optionally load and inspect the FAISS index
        loaded_index = faiss.read_index(index_file)
        print(f"FAISS index loaded. Total embeddings: {loaded_index.ntotal}, Dimension: {loaded_index.d}")

    # Clean up test files
    # if os.path.exists(embeddings_file): os.remove(embeddings_file)
    # if os.path.exists(index_file): os.remove(index_file)
    # print("Cleaned up test files.")
