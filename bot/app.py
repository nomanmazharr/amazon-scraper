import os
import subprocess
import re
import logging
import time
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
import faiss
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field
from typing import List

# loading key
load_dotenv()

#logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Create a rotating file handler (max 5MB per file, keep 3 backups)
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "app.log"), maxBytes=5_000_000, backupCount=3, encoding="utf-8"
)
stream_handler = logging.StreamHandler()

# Logging format
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, stream_handler],
)

logger = logging.getLogger("ChaiVisionApp")


app = FastAPI()

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("Please set the GROQ_API_KEY environment variable.")
# initializing model
llm = ChatGroq(model="openai/gpt-oss-120b", api_key=groq_api_key)

# embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# loading index
def load_index_and_docs():
    if not os.path.exists("index.faiss") or not os.path.exists("documents.txt"):
        raise FileNotFoundError("FAISS index or documents.txt not found. Please run /index first.")
    index = faiss.read_index("index.faiss")
    with open("documents.txt", "r", encoding="utf-8") as f:
        documents = f.read().splitlines()
    return index, documents

index, documents = load_index_and_docs()

# retrieving data
def get_relevant_sources(question, k=10):
    """Retrieve semantically similar documents using FAISS embeddings."""
    query_emb = model.encode([question], convert_to_numpy=True)
    distances, indices = index.search(np.array(query_emb), k)

    sources = []
    for idx in indices[0]:
        if idx < len(documents):
            doc = documents[idx]
            asin_match = re.search(r"ASIN (\w+)", doc)
            asin = asin_match.group(1) if asin_match else f"ITEM-{idx}"
            sources.append({
                "asin": asin,
                "snippet": doc
            })
    return sources

# Defining output and input schemas
class ScrapeRequest(BaseModel):
    q: str
    n: int = 10

class QuestionRequest(BaseModel):
    question: str

class Source(BaseModel):
    asin: str = Field(..., description="The ASIN of the product")
    snippet: str = Field(..., description="Descriptive snippet used as context")

class ModelAnswer(BaseModel):
    """Defines the structure of the model's final output."""
    answer: str = Field(..., description="A natural language sentence answering the user question.")

class AnswerResponse(BaseModel):
    answer: str
    sources: List[Source]


@app.post("/scrape")
async def trigger_scrape(request: ScrapeRequest):
    """Run scraper and comparison scripts sequentially."""
    logger.info(f"Scrape request received: query='{request.q}', n={request.n}")
    start_time = time.time()

    try:
        # Run scraping
        logger.info("Starting scraper script: scrape/scrape.py ...")
        subprocess.run(
            ['python', 'scrape/scrape.py', '--q', request.q, '--n', str(request.n)],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Scraper completed successfully.")

        # Run comparison
        logger.info("Starting comparison script: analysis/compare.py ...")
        subprocess.run(
            ['python', 'analysis/compare.py'],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Comparison completed successfully.")

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"Scraping + comparison completed in {elapsed}s.")
        return {"message": f"Scraping and comparison completed successfully in {elapsed}s."}

    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess failed (returncode={e.returncode}): {e.stderr or e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

    except Exception as e:
        logger.exception("Unexpected error during scraping process.")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index")
async def rebuild_index():
    """Rebuild FAISS index from updated feature_matrix.csv."""
    logger.info("Index rebuild request received.")
    start_time = time.time()

    try:
        # Remove existing index files
        for file in ["index.faiss", "documents.txt"]:
            if os.path.exists(file):
                os.remove(file)
                logger.info(f"Removed existing file: {file}")

        # Run indexer
        logger.info("Starting index rebuild via bot.indexer...")
        import bot.indexer
        bot.indexer.index_data()
        logger.info("Indexing process completed successfully.")

        # Reload globals
        global index, documents
        index, documents = load_index_and_docs()
        logger.info("Index and documents reloaded into memory.")

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"Index rebuild finished in {elapsed}s.")
        return {"message": f"Index rebuilt and reloaded successfully in {elapsed}s."}

    except FileNotFoundError as fnf:
        logger.error(f"Required file not found: {fnf}")
        raise HTTPException(status_code=404, detail=str(fnf))

    except Exception as e:
        logger.exception("Unexpected error during index rebuild.")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """Answer questions grounded in retrieved Amazon product data."""
    question = request.question
    logger.info(f"Received question: {question}")

    # Retrieve relevant documents
    sources = get_relevant_sources(question)
    logger.info(f"Retrieved {len(sources)} relevant sources.")
    context = "\n".join([src["snippet"] for src in sources]) if sources else "\n".join(documents[:5])

    # Parser and prompt
    parser = PydanticOutputParser(pydantic_object=ModelAnswer)
    prompt_template = PromptTemplate(
        input_variables=["question", "context"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
        template="""
        You are an expert in analyzing Amazon product listings and comparing their details.
        Use ONLY the data provided in the context below to answer the question accurately.

        Follow these strict output rules:
        - Output ONLY valid JSON as described below.
        - Do NOT include code fences, markdown, or any extra text.
        - The JSON must match this schema:
          {format_instructions}
        - The "answer" value must be a clean, natural sentence.
        - Mention the product's title, ASIN, rating, and price if available.
        - If multiple products qualify, summarize the best one briefly.
        - If the data is insufficient, set the answer exactly to:
          "I'm sorry, but I can only provide information related to Amazon products and their details. Please refer to the listed sources to learn more about the products"

        ---
        Question: {question}

        Context:
        {context}
        """
    )

    # Use the Pydantic parser directly, not StrOutputParser
    chain = prompt_template | llm | parser

    try:
        parsed_output = chain.invoke({"question": question, "context": context})
        answer = parsed_output.answer.strip()
        logger.info("Successfully parsed structured response from LLM.")
    except Exception as e:
        # Falling back to simple string
        logger.warning(f"Pydantic parsing failed: {e}. Falling back to plain string output.")
        raw_output = (prompt_template | llm | StrOutputParser()).invoke(
            {"question": question, "context": context}
        )
        answer = raw_output.strip()

    # Map sources
    mapped_sources = [Source(asin=src["asin"], snippet=src["snippet"]) for src in sources]

    response = AnswerResponse(answer=answer, sources=mapped_sources)
    return JSONResponse(response.model_dump())