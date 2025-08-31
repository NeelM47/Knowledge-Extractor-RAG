---
title: Knowledge Extractor RAG
emoji: 🧠
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: true
---

# Knowledge Extractor RAG: An End-to-End RAG System with a Conversational AI Agent

This project implements a complete, full-stack, and production-ready system for performing Retrieval-Augmented Generation (RAG) on user-uploaded PDF documents. It features an asynchronous ingestion pipeline, a sophisticated hybrid retrieval strategy using a graph database, and a conversational AI agent capable of multi-tool use.

The application is fully containerized with Docker and Docker Compose, allowing any developer to set up and run the entire multi-service environment with a single command.

## 🌟 Key Features

-   **Asynchronous PDF Ingestion:** Upload any PDF through the web UI. The ingestion is handled by a **Django-Q** background worker using a **Redis** message broker, providing a non-blocking, professional user experience.
-   **Knowledge Graph Construction:** Employs an LLM during ingestion to perform Named Entity Recognition, automatically building a knowledge graph of concepts within the documents.
-   **Advanced Hybrid Retrieval:** Employs a state-of-the-art, two-stage retrieval process:
    1.  **Graph & Vector Search:** Leverages **Neo4j** as a multi-model database, performing both semantic vector similarity search and graph-based entity retrieval to find the most relevant document chunks.
    2.  **Re-ranking:** Uses a powerful **Cross-Encoder** model to re-rank the initial candidates for maximum relevance before sending them to the LLM.
-   **Conversational AI Agent:** Built with **LangChain**, the AI agent can reason, form multi-step plans, and use a suite of custom tools to answer complex queries, including comparing and contrasting information across multiple documents.
-   **Full-Stack & Containerized:** The entire multi-service application (Django, Neo4j, Redis, Django-Q Worker) is managed by **Docker Compose** for easy, one-command local setup.

## 🏛️ Project Architecture

The application is architected with a clear separation of concerns, featuring an asynchronous ingestion pipeline and a powerful agentic query pipeline.

### Ingestion Pipeline (Asynchronous)
```mermaid
graph TD;
    A[User Uploads PDF] --> B{1. Django Web App};
    B --> C((2. Redis Queue));
    D[3. Django-Q Worker] --> C;
    D --> E[4. Docling: Parse & Chunk];
    E --> F[5. LLM: Extract Entities];
    F --> G[6. Sentence Transformers: Create Embeddings];
    G --> H((7. Neo4j: Store Graph & Vectors));
```

### Agentic Query Pipeline
```mermaid
graph TD;
    subgraph User Interaction;
        A[User sends message] --> B{1. Django Web App};
    end;

    subgraph Agent Core;
        B --> C{2. LangChain Agent Executor};
        C -- Thought --> D[3. LLM (Gemini)];
        D -- Plan --> C;
        C -- Tool Call --> E[4. Custom Tools];
    end;

    subgraph RAG Backend;
        E -- (query_document) --> F{5. Hybrid Retrieval};
        F -- Graph & Vector Search --> G((Neo4j));
        G --> F;
        F -- Re-ranking --> H[6. Cross-Encoder];
        H --> I[7. Final Context];
        I --> J[8. LLM (Gemini)];
        J --> E;
    end;
    
    E --> C;
    C -- Final Answer --> B;
```

## 🛠️ Tech Stack

-   **Backend:** Django
-   **Asynchronous Tasks:** Django-Q with a Redis Broker
-   **Database:** Neo4j (Graph & Vector Database)
-   **PDF Parsing:** Docling
-   **Embedding Model:** `sentence-transformers` (Bi-Encoder)
-   **Re-ranking Model:** `cross-encoder`
-   **LLM:** Google Gemini Pro
-   **Agent Framework:** LangChain
-   **Containerization:** Docker & Docker Compose

---

## 🚀 How to Run Locally (Using Docker Compose)

This project is designed to be run locally with a single command using **Docker Compose**. This will automatically build and start all the necessary services: the Neo4j database, a Redis message broker, the Django web server, and the Django-Q background worker.

### Prerequisites
-   **Docker Desktop:** Ensure Docker Desktop is installed and running on your machine.
-   **Git:** For cloning the repository.

### Step 1: Clone the Repository
```bash
git clone https://github.com/YourUsername/Knowledge-Extractor-RAG.git
cd Knowledge-Extractor-RAG
```

### Step 2: Configure Environment Secrets
The application requires API keys and database credentials. This is a **critical step**.

1.  Navigate into the `rag_webapp` directory:
    ```bash
    cd rag_webapp
    ```
2.  Create a `.env` file. A template is provided for convenience.
    ```bash
    cp .env.example .env
    ```
3.  Open the newly created `.env` file with a text editor and add your credentials. The values for `NEO4J_URI` and `CELERY_BROKER_URL` are specifically for this Docker Compose setup and **should not be changed**.

    ```.env
    # rag_webapp/.env

    # --- Neo4j Credentials for Docker Compose ---
    NEO4J_URI="neo4j://neo4j:7687"
    NEO4J_USER="neo4j"
    # This password MUST match the one you set in docker-compose.yml
    NEO4J_PASSWORD="your-strong-local-password"

    # --- Google Gemini API Key ---
    GEMINI_API_KEY="Your-Google-AI-Studio-API-Key"

    # --- Django-Q (Redis) Broker URL for Docker Compose ---
    CELERY_BROKER_URL="redis://redis:6379/0"
    ```
4.  Navigate back to the project root directory:
    ```bash
    cd ..
    ```

### Step 3: Synchronize the Neo4j Password
You must ensure the password in your `.env` file matches the one used by the Neo4j container.

1.  Open the `docker-compose.yml` file in the project root.
2.  Find the `neo4j` service definition.
3.  Update the password in the `NEO4J_AUTH` environment variable to **exactly match** the `NEO4J_PASSWORD` you set in your `.env` file.

    ```yaml
    # docker-compose.yml
    services:
      neo4j:
        # ...
        environment:
          - NEO4J_AUTH=neo4j/your-strong-local-password # <-- THIS MUST MATCH .env
    ```

### Step 4: Run Database Migrations
This one-time command sets up the necessary tables for Django and Django-Q in a persistent volume.

```bash
docker compose run --rm app python manage.py migrate
```

### Step 5: Build and Run the Application Stack
With Docker running, execute the following command from the **project root directory**. This single command will build your Django image and start all four services in the background.

```bash
docker compose up --build -d
```
-   `--build`: Forces a rebuild of your application image if you've made code changes.
-   `-d`: Runs the containers in "detached" mode.

### Step 6: Access and Test the Application
Once the services are running, your application is ready to use:

-   **🧠 Main Web Application:** Open your browser and go to **`http://localhost:8000`**
-   **🐘 Neo4j Database Browser:** To inspect the graph data, go to **`http://localhost:7474`**
    -   **Connect URI:** `bolt://localhost:7687`
    -   **Username:** `neo4j`
    -   **Password:** The password you set in the configuration files.

To view the combined, real-time logs from all running services (the web server and the worker), run:
```bash
docker compose logs -f
```

### Step 7: Stop the Application
To gracefully stop all running services and remove the containers, run:
```bash
docker compose down
```

---

## 📈 Future Scope
-   **Real-time Agent Feedback:** Implement WebSockets to stream the agent's "chain of thought" to the user interface in real-time.
-   **User Authentication:** Add user accounts to allow for private document collections.
-   **Enhanced Citations:** Use the bounding box data from Docling to visually highlight the source of an answer directly on a rendered PDF page.

## License

This project is licensed under the MIT License.

---

## Contact

**Neel Shirish More** – [LinkedIn](https://www.linkedin.com/in/neel-more-267217219/) – [neelmore007@gmail.com](mailto:neelmore007@gmail.com)
