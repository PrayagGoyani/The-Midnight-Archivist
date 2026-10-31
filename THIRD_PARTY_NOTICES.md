# Third-Party Notices & Licensing

> This document details the licenses and attributions for third-party models, software libraries, and runtimes used by or integrated with **The Midnight Archivist**.
> 
> The application source code of The Midnight Archivist is licensed under the [MIT License](./LICENSE). The application license applies **strictly to the original application code** and does not extend to, modify, or supersede the licenses of any third-party models, runtimes, or libraries listed below.

---

## 1. Local Machine Intelligence & Model Weights

The Midnight Archivist operates entirely offline by interfacing with local neural models via Ollama. These models are not bundled within the application repository; they are downloaded and executed locally by the user.

### Meta Llama 3.2 3B (`llama3.2:3b`)
- **Author / Provider:** Meta Platforms, Inc.
- **Model Card / Upstream:** [Meta Llama 3.2 on Hugging Face](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) / [Meta Llama Models Repository](https://github.com/meta-llama/llama-models)
- **License:** **Meta Llama 3.2 Community License Agreement** (Release Date: September 25, 2024)
- **License Text & Terms:** [https://llama.meta.com/llama3/license/](https://llama.meta.com/llama3/license/)
- **Nature of License:**
  - Llama 3.2 is an **open-weight model**, **not** an unrestricted OSI-approved open-source license.
  - Permissive for research, development, and commercial use for entities with fewer than 700 million monthly active users across all services in the preceding calendar month.
  - Governed by the [Meta Llama Acceptable Use Policy](https://llama.meta.com/use-policy/).
  - **Mandatory Attribution:** Any product or service distributed using Llama 3.2 must prominently display the phrase:  
    `"Built with Llama"`
  - Redistribution of model weights or fine-tuned derivatives requires retaining Meta's license agreement and notice files.

### Nomic Embed Text (`nomic-embed-text`)
- **Author / Provider:** Nomic AI
- **Model Card / Upstream:** [Nomic Embed Text v1.5 on Hugging Face](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) / [Nomic AI Contrastors](https://github.com/nomic-ai/contrastors)
- **License:** **Apache License 2.0**
- **License Text & Terms:** [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)
- **Nature of License:**
  - Fully open-source permissive license.
  - Grants perpetual, worldwide, non-exclusive copyright and patent licenses.
  - Requires preservation of copyright and license notices when redistributed.

### Ollama Inference Runtime
- **Author / Provider:** Jeffrey Morgan & Ollama Contributors
- **Repository:** [https://github.com/ollama/ollama](https://github.com/ollama/ollama)
- **License:** **MIT License**
- **License Text & Terms:** [https://github.com/ollama/ollama/blob/main/LICENSE](https://github.com/ollama/ollama/blob/main/LICENSE)
- **Nature of License:** Permissive open-source license permitting free use, distribution, and modification.

---

## 2. Backend Dependencies (Python)

The following open-source packages are used in the FastAPI backend runtime:

| Package | Upstream Project | License | Copyright Holder / Author |
|---|---|---|---|
| **FastAPI** | [fastapi/fastapi](https://github.com/fastapi/fastapi) | **MIT** | Sebastián Ramírez |
| **Uvicorn** | [encode/uvicorn](https://github.com/encode/uvicorn) | **BSD-3-Clause** | Encode OSS Ltd / Tom Christie |
| **SQLAlchemy** | [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) | **MIT** | Michael Bayer & SQLAlchemy Contributors |
| **Pydantic** | [pydantic/pydantic](https://github.com/pydantic/pydantic) | **MIT** | Samuel Colvin & Pydantic Contributors |
| **Pydantic-Settings** | [pydantic/pydantic-settings](https://github.com/pydantic/pydantic-settings) | **MIT** | Samuel Colvin & Pydantic Contributors |
| **Python-Multipart** | [Kludex/python-multipart](https://github.com/Kludex/python-multipart) | **Apache-2.0** | Andrew Dunham & Marcelo Trylesinski |
| **HTTPX** | [encode/httpx](https://github.com/encode/httpx) | **BSD-3-Clause** | Encode OSS Ltd / Tom Christie |
| **pypdf** | [py-pdf/pypdf](https://github.com/py-pdf/pypdf) | **BSD-3-Clause** | Mathieu Fenniak & pypdf Contributors |
| **NumPy** | [numpy/numpy](https://github.com/numpy/numpy) | **BSD-3-Clause** | NumPy Developers |
| **pytest** | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | **MIT** | Holger Krekel & pytest Contributors |
| **pytest-asyncio** | [pytest-dev/pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | **Apache-2.0** | Tin Tvrtković & pytest-asyncio Contributors |

---

## 3. Frontend Dependencies (TypeScript / React)

The following open-source packages are used in the React frontend interface:

| Package | Upstream Project | License | Copyright Holder / Author |
|---|---|---|---|
| **React** | [facebook/react](https://github.com/facebook/react) | **MIT** | Meta Platforms, Inc. |
| **React DOM** | [facebook/react](https://github.com/facebook/react) | **MIT** | Meta Platforms, Inc. |
| **React Router (DOM)** | [remix-run/react-router](https://github.com/remix-run/react-router) | **MIT** | Remix Software Inc. & React Router Contributors |
| **Lucide React** | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | **ISC** | Lucide Contributors |
| **Vite** | [vitejs/vite](https://github.com/vitejs/vite) | **MIT** | Evan You & Vite Contributors |
| **TypeScript** | [microsoft/TypeScript](https://github.com/microsoft/TypeScript) | **Apache-2.0** | Microsoft Corporation |
| **ESLint** | [eslint/eslint](https://github.com/eslint/eslint) | **MIT** | Nicholas C. Zakas & ESLint Contributors |

---

## 4. Public Demonstration Sample Documents

- **`sample_archive_manuscript.pdf`:** Created specifically for The Midnight Archivist as an original demonstration manuscript (*Log of the Beacon Island Maritime Observatory, 1888*). Released into the public domain under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).
- **`shore_watchman_1888.txt`:** Original fictional period log (*Field Notes of Caleb Thorne, 1888*) created specifically for this repository's automated tests and demonstration archive. Released into the public domain under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).
