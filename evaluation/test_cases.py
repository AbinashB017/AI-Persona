"""
evaluation/test_cases.py
Ground-truth Q&A pairs for evaluating the AI Persona.
Based on Abinash Behera's actual resume and GitHub repos.
"""

# Format: {"question": str, "expected_keywords": list[str], "source_type": str}
TEST_CASES = [
    # ── Resume / Background ──
    {
        "question": "What is Abinash's educational background?",
        "expected_keywords": ["IIIT Nagpur", "Computer Science", "B.Tech", "CGPA", "9.00"],
        "source_type": "resume",
        "category": "education",
    },
    {
        "question": "What programming languages does Abinash know?",
        "expected_keywords": ["Python", "C++", "JavaScript"],
        "source_type": "resume",
        "category": "skills",
    },
    {
        "question": "What certifications does Abinash have?",
        "expected_keywords": ["Coursera", "NVIDIA", "Machine Learning"],
        "source_type": "resume",
        "category": "certifications",
    },
    {
        "question": "What ML frameworks does Abinash use?",
        "expected_keywords": ["TensorFlow", "PyTorch", "LangChain"],
        "source_type": "resume",
        "category": "skills",
    },

    # ── Projects ──
    {
        "question": "Tell me about AutoMedRAG",
        "expected_keywords": ["PubMed", "FAISS", "BM25", "medical", "FastAPI"],
        "source_type": "github_readme",
        "category": "projects",
    },
    {
        "question": "What is the agentic data analyser project?",
        "expected_keywords": ["LangGraph", "LLaMA", "EDA", "Streamlit", "Plotly"],
        "source_type": "github_readme",
        "category": "projects",
    },
    {
        "question": "Tell me about the sign language detection project",
        "expected_keywords": ["OpenCV", "MediaPipe", "LSTM", "TensorFlow", "ASL"],
        "source_type": "resume",
        "category": "projects",
    },
    {
        "question": "What is the transaction detection project about?",
        "expected_keywords": ["GraphSAGE", "Bitcoin", "fraud", "Elliptic", "F1"],
        "source_type": "resume",
        "category": "projects",
    },

    # ── Grounding / Hallucination tests ──
    {
        "question": "Does Abinash have 10 years of industry experience?",
        "expected_keywords": ["don't", "not", "information", "unavailable"],
        "source_type": "any",
        "category": "hallucination_guard",
        "expect_refusal": True,
    },
    {
        "question": "What is Abinash's home address?",
        "expected_keywords": ["don't", "not", "information"],
        "source_type": "any",
        "category": "hallucination_guard",
        "expect_refusal": True,
    },
    {
        "question": "Has Abinash worked at Google?",
        "expected_keywords": ["don't", "not", "information", "unavailable"],
        "source_type": "any",
        "category": "hallucination_guard",
        "expect_refusal": True,
    },

    # ── Contact / Scheduling ──
    {
        "question": "How can I schedule an interview with Abinash?",
        "expected_keywords": ["schedule", "book", "interview", "meeting"],
        "source_type": "any",
        "category": "scheduling",
    },
    {
        "question": "What is Abinash's email?",
        "expected_keywords": ["avinashapms@gmail.com"],
        "source_type": "resume",
        "category": "contact",
    },
]
