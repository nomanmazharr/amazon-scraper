
---

## How It Works

### 1. **Scraping** (`/scrape`)
- Accepts a search keyword and number of results (`n`)
- Fetches Amazon search pages
- Extracts: **ASIN, title, price, rating, review count, image URL, product URL**
- Saves to `data/products.csv` & `data/products.jsonl`
- Runs `analysis/compare.py` to generate `data/feature_matrix.csv`

### 2. **Indexing** (`/index`)
- Reads `data/feature_matrix.csv`
- Converts each product into a structured text document
- Builds **FAISS vector index** using `all-MiniLM-L6-v2` embeddings from sentence-transformer
- Saves index to `index.faiss` and documents to `documents.txt`

### 3. **Q&A** (`/ask`)
- Accepts a natural language question
- Retrieves **top-k semantically similar products** using FAISS
- Sends context + question to **Groq(openai/oss-20b)** via LangChain
- Returns a **structured JSON answer** with sources

---

## API Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/scrape` | `{ "q": "massage gun", "n": 10 }` | Run scraper + comparison |
| `POST` | `/index`  | `{}` | Rebuild FAISS index |
| `POST` | `/ask`    | `{ "question": "best under $50?" }` | Ask about products |

---

## Setup & Run

```bash

# 1. Clone & install
git clone https://github.com/nomanmazharr/amazon-scraper.git
cd amazon-scraper
pip install -r requirements.txt

# 2. Add your Groq API key in the given variable in .env file
GROQ_API_KEY = ""

To get your API key, visit [groq_console](https://console.groq.com/keys)

# 3. Run scraper
python scrape/scrape.py --q "walking pad" --n 10

# 4. Start API
uvicorn bot.app:app --port 8003

# 5. Ask a question
curl -X POST http://127.0.0.1:8003/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"best massage gun under $50"}'