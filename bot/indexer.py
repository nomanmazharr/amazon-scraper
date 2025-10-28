import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import faiss
from sentence_transformers import SentenceTransformer

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("Please set the GROQ_API_KEY environment variable.")
llm = ChatGroq(model="openai/gpt-oss-120b", api_key=groq_api_key)

# Load and prepare data
def load_data():
    data_dir = 'data'
    input_file = os.path.join(data_dir, 'feature_matrix.csv')
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"{input_file} not found. Please run the comparison script first.")
    df = pd.read_csv(input_file)
    return df

def create_documents(df):
    documents = []
    for _, row in df.iterrows():
        asin = row.get("asin", "")
        title = str(row.get("title", "")).strip()
        brand = str(row.get("brand", "")).strip() or "Unknown brand"
        price = row.get("price")
        price_str = f"${price:.2f}" if pd.notna(price) else "Price not listed"
        rating = row.get("rating")
        rating_str = f"rated {rating} out of 5 stars" if pd.notna(rating) else "no rating available"
        reviews = row.get("review_count")
        reviews_str = f"based on {int(reviews)} customer reviews" if pd.notna(reviews) else "with no review data"

        # A universal product summary
        summary = (
            f"Product '{title}' (ASIN {asin}) by {brand} is listed on Amazon. "
            f"It is {rating_str} {reviews_str} and priced at {price_str}. "
            f"This product may belong to categories like electronics, home, fitness, or books depending on the keyword."
        )

        documents.append(summary)
    return documents

# Build and save FAISS index
def build_index(documents):
    # Use a pre-trained SentenceTransformer for embeddings
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(documents, convert_to_numpy=True)

    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings))

    # Save index and documents
    faiss.write_index(index, 'index.faiss')
    with open('documents.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(documents))
    print("Index and documents saved locally.")

def index_data():
    df = load_data()
    documents = create_documents(df)
    build_index(documents)

if __name__ == '__main__':
    index_data()