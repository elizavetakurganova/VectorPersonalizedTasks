"""
База знаний для RAG (Retrieval Augmented Generation)
"""
import os
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
import logging
from pathlib import Path
import pickle
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from rank_bm25 import BM25Okapi
import re

from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)


class DifficultyLevel(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class TopicCategory(Enum):
    LINEAR_EQUATIONS = "linear_equations"
    QUADRATIC_EQUATIONS = "quadratic_equations"
    FRACTIONS = "fractions"
    PERCENTAGES = "percentages"
    GEOMETRY = "geometry"
    MOTION = "motion"
    INEQUALITIES = "inequalities"
    TRIGONOMETRY = "trigonometry"
    LOGARITHMS = "logarithms"
    DERIVATIVES = "derivatives"
    INTEGRALS = "integrals"
    PROBABILITY = "probability"
    SEQUENCES = "sequences"
    MATRICES = "matrices"
    VECTORS = "vectors"


@dataclass
class KnowledgeChunk:
    text: str
    topic: str
    difficulty: str
    example: str = ""
    keywords: List[str] = field(default_factory=list)
    solution_steps: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    success_rate: float = 0.5
    source: str = "base"
    tags: List[str] = field(default_factory=list)
    embedding_cache_key: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def get_searchable_text(self) -> str:
        return f"{self.text} {self.example} {' '.join(self.keywords)} {' '.join(self.solution_steps)}"
    
    def compute_cache_key(self) -> str:
        content = self.get_searchable_text()
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class SearchResult:
    chunk: KnowledgeChunk
    score: float
    score_details: Dict[str, float] = field(default_factory=dict)
    rank: int = 0


class HybridRetriever:
    def __init__(self, bm25_weight: float = 0.4, embedding_weight: float = 0.6):
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        self.bm25_index = None
        self.corpus = []
        
    def build_bm25(self, chunks: List[KnowledgeChunk]):
        self.corpus = [chunk.get_searchable_text() for chunk in chunks]
        tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
        self.bm25_index = BM25Okapi(tokenized_corpus)
    
    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())
    
    def search(self, query: str, chunks: List[KnowledgeChunk], embeddings: np.ndarray,
               query_embedding: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        if self.bm25_index is None:
            self.build_bm25(chunks)
        
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25_index.get_scores(tokenized_query)
        bm25_scores = self._normalize_scores(bm25_scores)
        
        embedding_similarities = np.dot(embeddings, query_embedding)
        embedding_similarities = self._normalize_scores(embedding_similarities)
        
        hybrid_scores = (self.bm25_weight * bm25_scores + 
                        self.embedding_weight * embedding_similarities)
        
        top_indices = np.argsort(hybrid_scores)[-top_k:][::-1]
        
        results = []
        for rank, idx in enumerate(top_indices):
            result = SearchResult(
                chunk=chunks[idx],
                score=float(hybrid_scores[idx]),
                score_details={
                    'bm25': float(bm25_scores[idx]),
                    'embedding': float(embedding_similarities[idx]),
                    'hybrid': float(hybrid_scores[idx])
                },
                rank=rank
            )
            results.append(result)
        
        return results
    
    @staticmethod
    def _normalize_scores(scores: np.ndarray) -> np.ndarray:
        min_score = np.min(scores)
        max_score = np.max(scores)
        if max_score - min_score < 1e-8:
            return np.ones_like(scores)
        return (scores - min_score) / (max_score - min_score)


class KnowledgeBase:
    def __init__(self, data_file: Optional[str] = None, use_embeddings: bool = True,
                 cache_dir: Optional[str] = None, model_name: str = 'intfloat/multilingual-e5-large',
                 max_chunks: int = 1000):
        self.knowledge_chunks: List[KnowledgeChunk] = []
        self.embeddings: Optional[np.ndarray] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self.use_embeddings = use_embeddings
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / '.knowledge_base_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.max_chunks = max_chunks
        self.retriever = HybridRetriever()
        
        self._load_data(data_file)
        
        if use_embeddings and self.knowledge_chunks:
            try:
                self._init_embeddings()
                self.retriever.build_bm25(self.knowledge_chunks)
            except Exception as e:
                logger.warning(f"Embedding initialization failed: {e}")
                self.use_embeddings = False
    
    def _load_data(self, data_file: Optional[str]):
        if data_file and Path(data_file).exists():
            try:
                if data_file.endswith('.csv'):
                    self._load_from_csv(data_file)
                elif data_file.endswith('.json'):
                    self._load_from_json(data_file)
                elif data_file.endswith('.pkl'):
                    self._load_from_pickle(data_file)
                else:
                    self._create_base_examples()
            except Exception as e:
                logger.warning(f"Failed to load {data_file}: {e}")
                self._create_base_examples()
        else:
            self._create_base_examples()
        
        logger.info(f"Loaded {len(self.knowledge_chunks)} knowledge chunks")
    
    def _load_from_csv(self, file_path: str):
        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            chunk = KnowledgeChunk(
                text=row.get('text', ''),
                topic=row.get('topic', 'general'),
                difficulty=row.get('difficulty', 'medium'),
                example=row.get('example', ''),
                keywords=eval(row.get('keywords', '[]')) if isinstance(row.get('keywords'), str) else [],
                solution_steps=eval(row.get('solution_steps', '[]')) if isinstance(row.get('solution_steps'), str) else [],
                prerequisites=eval(row.get('prerequisites', '[]')) if isinstance(row.get('prerequisites'), str) else [],
                common_mistakes=eval(row.get('common_mistakes', '[]')) if isinstance(row.get('common_mistakes'), str) else [],
                success_rate=row.get('success_rate', 0.5),
                tags=eval(row.get('tags', '[]')) if isinstance(row.get('tags'), str) else []
            )
            if len(self.knowledge_chunks) < self.max_chunks:
                self.knowledge_chunks.append(chunk)
    
    def _load_from_json(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data[:self.max_chunks]:
            self.knowledge_chunks.append(KnowledgeChunk(**item))
    
    def _load_from_pickle(self, file_path: str):
        with open(file_path, 'rb') as f:
            chunks = pickle.load(f)
        self.knowledge_chunks = chunks[:self.max_chunks]
    
    def _create_base_examples(self):
        examples = [
            KnowledgeChunk(
                text="Solve linear equations of the form ax + b = c",
                topic=TopicCategory.LINEAR_EQUATIONS.value,
                difficulty=DifficultyLevel.EASY.value,
                example="2x + 3 = 7 → x = 2",
                keywords=["linear", "ax+b=c", "simple equation"],
                solution_steps=["Isolate the term with x", "Divide both sides by coefficient"],
                prerequisites=["Basic arithmetic", "Algebraic operations"],
                common_mistakes=["Forgetting to apply operation to both sides", "Sign errors"],
                success_rate=0.85,
                tags=["algebra", "beginner"]
            ),
            KnowledgeChunk(
                text="Solve linear equations with variables on both sides",
                topic=TopicCategory.LINEAR_EQUATIONS.value,
                difficulty=DifficultyLevel.MEDIUM.value,
                example="3x + 5 = 2x + 10 → x = 5",
                keywords=["variables both sides", "linear equation"],
                solution_steps=["Move variables to left side", "Move constants to right side", "Solve for x"],
                prerequisites=["ax+b=c equations", "Like terms"],
                common_mistakes=["Incorrect sign when moving terms", "Missing terms"],
                success_rate=0.75,
                tags=["algebra", "intermediate"]
            ),
            KnowledgeChunk(
                text="Solve quadratic equations using discriminant",
                topic=TopicCategory.QUADRATIC_EQUATIONS.value,
                difficulty=DifficultyLevel.MEDIUM.value,
                example="x² - 5x + 6 = 0 → x = 2, 3",
                keywords=["quadratic", "discriminant", "ax²+bx+c=0"],
                solution_steps=["Calculate D = b² - 4ac", "Apply formula x = (-b ± √D)/(2a)"],
                prerequisites=["Square roots", "Linear equations"],
                common_mistakes=["Wrong sign in formula", "Discriminant calculation errors"],
                success_rate=0.70,
                tags=["algebra", "quadratic"]
            ),
            KnowledgeChunk(
                text="Add fractions with different denominators",
                topic=TopicCategory.FRACTIONS.value,
                difficulty=DifficultyLevel.MEDIUM.value,
                example="1/2 + 1/3 = 5/6",
                keywords=["fraction addition", "different denominators", "common denominator"],
                solution_steps=["Find LCM of denominators", "Convert fractions", "Add numerators"],
                prerequisites=["Fraction basics", "Multiplication"],
                common_mistakes=["Adding numerators without finding common denominator"],
                success_rate=0.78,
                tags=["arithmetic", "fractions"]
            ),
            KnowledgeChunk(
                text="Calculate percentage of a number",
                topic=TopicCategory.PERCENTAGES.value,
                difficulty=DifficultyLevel.EASY.value,
                example="20% of 150 = 30",
                keywords=["percentage", "percent of number"],
                solution_steps=["Convert percentage to decimal", "Multiply by the number"],
                prerequisites=["Decimal multiplication"],
                common_mistakes=["Forgetting to divide by 100", "Wrong multiplication"],
                success_rate=0.88,
                tags=["arithmetic", "percentages"]
            ),
            KnowledgeChunk(
                text="Apply Pythagorean theorem for right triangles",
                topic=TopicCategory.GEOMETRY.value,
                difficulty=DifficultyLevel.MEDIUM.value,
                example="a² + b² = c² for legs 3 and 4 → hypotenuse = 5",
                keywords=["pythagorean", "right triangle", "hypotenuse"],
                solution_steps=["Identify legs and hypotenuse", "Apply a² + b² = c²", "Take square root"],
                prerequisites=["Square numbers", "Square roots"],
                common_mistakes=["Confusing legs with hypotenuse", "Adding without squaring"],
                success_rate=0.80,
                tags=["geometry", "trigonometry"]
            ),
            KnowledgeChunk(
                text="Solve inequality with sign reversal when multiplying by negative",
                topic=TopicCategory.INEQUALITIES.value,
                difficulty=DifficultyLevel.MEDIUM.value,
                example="-2x > 6 → x < -3",
                keywords=["inequality", "negative multiplication", "sign reversal"],
                solution_steps=["Isolate variable", "Reverse inequality sign when multiplying/dividing by negative"],
                prerequisites=["Linear equations", "Number line"],
                common_mistakes=["Forgetting to reverse inequality sign"],
                success_rate=0.65,
                tags=["algebra", "inequalities"]
            ),
            KnowledgeChunk(
                text="Calculate probability of independent events",
                topic=TopicCategory.PROBABILITY.value,
                difficulty=DifficultyLevel.MEDIUM.value,
                example="P(A and B) = P(A) × P(B)",
                keywords=["probability", "independent events", "multiplication rule"],
                solution_steps=["Verify events are independent", "Multiply individual probabilities"],
                prerequisites=["Basic probability", "Fractions"],
                common_mistakes=["Adding instead of multiplying", "Assuming dependence incorrectly"],
                success_rate=0.72,
                tags=["statistics", "probability"]
            ),
            KnowledgeChunk(
                text="Find derivative of polynomial functions",
                topic=TopicCategory.DERIVATIVES.value,
                difficulty=DifficultyLevel.HARD.value,
                example="d/dx (x³ + 2x² - 5x) = 3x² + 4x - 5",
                keywords=["derivative", "polynomial", "power rule", "calculus"],
                solution_steps=["Apply power rule: d/dx(xⁿ) = nxⁿ⁻¹", "Differentiate term by term"],
                prerequisites=["Exponents", "Limits"],
                common_mistakes=["Decrementing exponent incorrectly", "Forgetting coefficient"],
                success_rate=0.60,
                tags=["calculus", "derivatives"]
            ),
            KnowledgeChunk(
                text="Solve logarithmic equations",
                topic=TopicCategory.LOGARITHMS.value,
                difficulty=DifficultyLevel.HARD.value,
                example="log₂(x) + log₂(3) = 4 → x = 16/3",
                keywords=["logarithm", "log equation", "log properties"],
                solution_steps=["Use product rule: log(a)+log(b)=log(ab)", "Convert to exponential form", "Solve for variable"],
                prerequisites=["Exponent rules", "Logarithm properties"],
                common_mistakes=["Mixing product and sum rules", "Domain errors"],
                success_rate=0.55,
                tags=["algebra", "logarithms"]
            )
        ]
        
        self.knowledge_chunks = examples
        logger.info(f"Created {len(examples)} base examples")
    
    def _init_embeddings(self):
        try:
            os.environ['HF_ENDPOINT'] = 'https://huggingface.co'
            
            cache_file = self.cache_dir / f"embeddings_{hashlib.md5(str([c.compute_cache_key() for c in self.knowledge_chunks]).encode()).hexdigest()[:10]}.npy"
            chunks_cache_file = self.cache_dir / f"chunks_{cache_file.stem.replace('embeddings_', '')}.pkl"
            
            if cache_file.exists() and chunks_cache_file.exists():
                self.embeddings = np.load(cache_file)
                with open(chunks_cache_file, 'rb') as f:
                    self.knowledge_chunks = pickle.load(f)
                logger.info("Loaded cached embeddings")
                return
            
            self.embedding_model = SentenceTransformer(self.model_name, device='cpu')
            
            texts = [chunk.get_searchable_text() for chunk in self.knowledge_chunks]
            batch_size = 32
            all_embeddings = []
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i+batch_size]
                    batch_embeddings = self.embedding_model.encode(batch, normalize_embeddings=True)
                    all_embeddings.append(batch_embeddings)
            
            self.embeddings = np.vstack(all_embeddings)
            
            np.save(cache_file, self.embeddings)
            with open(chunks_cache_file, 'wb') as f:
                pickle.dump(self.knowledge_chunks, f)
            
            logger.info(f"Created embeddings for {len(self.knowledge_chunks)} chunks")
        except Exception as e:
            logger.error(f"Embedding initialization failed: {e}")
            raise
    
    @lru_cache(maxsize=128)
    def _get_query_embedding(self, query: str) -> np.ndarray:
        if self.embedding_model:
            return self.embedding_model.encode([query], normalize_embeddings=True)[0]
        return np.zeros(384)
    
    def search(self, query: str, topic: Optional[str] = None, difficulty: Optional[str] = None,
               top_k: int = 5, min_similarity: float = 0.0, diversity_factor: float = 0.3) -> List[SearchResult]:
        candidates = self.knowledge_chunks
        
        if topic:
            candidates = [c for c in candidates if c.topic == topic]
        if difficulty:
            candidates = [c for c in candidates if c.difficulty == difficulty]
        
        if not candidates:
            return []
        
        if self.use_embeddings and self.embeddings is not None:
            query_embedding = self._get_query_embedding(query)
            candidate_indices = [self.knowledge_chunks.index(c) for c in candidates]
            candidate_embeddings = self.embeddings[candidate_indices]
            
            results = self.retriever.search(query, candidates, candidate_embeddings, query_embedding, top_k * 2)
            
            if diversity_factor > 0:
                results = self._diversify_results(results, diversity_factor)
            
            results = [r for r in results if r.score >= min_similarity][:top_k]
            return results
        
        return self._keyword_search(query, candidates, top_k)
    
    def _diversify_results(self, results: List[SearchResult], diversity_factor: float) -> List[SearchResult]:
        if len(results) <= 1:
            return results
        
        diversified = [results[0]]
        remaining = results[1:]
        
        while remaining and len(diversified) < len(results):
            best_idx = 0
            best_score = -1
            
            for i, candidate in enumerate(remaining):
                diversity_penalty = 0
                for selected in diversified:
                    topic_sim = 1.0 if candidate.chunk.topic == selected.chunk.topic else 0.0
                    diversity_penalty += topic_sim
                
                adjusted_score = candidate.score - diversity_factor * diversity_penalty
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_idx = i
            
            diversified.append(remaining.pop(best_idx))
        
        return diversified
    
    def _keyword_search(self, query: str, candidates: List[KnowledgeChunk], top_k: int) -> List[SearchResult]:
        query_words = set(re.findall(r'\w+', query.lower()))
        
        scored = []
        for chunk in candidates:
            score = 0.0
            searchable_text = chunk.get_searchable_text().lower()
            
            for word in query_words:
                if word in searchable_text:
                    score += 2.0
                if word in chunk.example.lower():
                    score += 1.0
                if any(word in kw.lower() for kw in chunk.keywords):
                    score += 3.0
            
            if score > 0:
                scored.append(SearchResult(chunk=chunk, score=score))
        
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]
    
    def add_example(self, text: str, topic: str, difficulty: str, example: str = "",
                   keywords: List[str] = None, solution_steps: List[str] = None,
                   prerequisites: List[str] = None, common_mistakes: List[str] = None,
                   success_rate: float = 0.5, tags: List[str] = None):
        chunk = KnowledgeChunk(
            text=text,
            topic=topic,
            difficulty=difficulty,
            example=example,
            keywords=keywords or [],
            solution_steps=solution_steps or [],
            prerequisites=prerequisites or [],
            common_mistakes=common_mistakes or [],
            success_rate=success_rate,
            tags=tags or []
        )
        
        self.knowledge_chunks.append(chunk)
        
        if self.use_embeddings and self.embedding_model:
            new_embedding = self.embedding_model.encode([chunk.get_searchable_text()], normalize_embeddings=True)
            self.embeddings = np.vstack([self.embeddings, new_embedding]) if self.embeddings is not None else new_embedding
            self.retriever.build_bm25(self.knowledge_chunks)
        
        logger.info(f"Added example on topic: {topic}")
    
    def get_statistics(self) -> Dict[str, Any]:
        topics = [c.topic for c in self.knowledge_chunks]
        difficulties = [c.difficulty for c in self.knowledge_chunks]
        
        return {
            'total_chunks': len(self.knowledge_chunks),
            'unique_topics': len(set(topics)),
            'topics_distribution': {t: topics.count(t) for t in set(topics)},
            'difficulty_distribution': {d: difficulties.count(d) for d in set(difficulties)},
            'avg_success_rate': np.mean([c.success_rate for c in self.knowledge_chunks]),
            'has_embeddings': self.embeddings is not None,
            'embedding_dim': self.embeddings.shape[1] if self.embeddings is not None else 0
        }
    
    def export_knowledge_base(self, file_path: str, format: str = 'json'):
        data = [chunk.to_dict() for chunk in self.knowledge_chunks]
        
        if format == 'json':
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == 'csv':
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
        elif format == 'pkl':
            with open(file_path, 'wb') as f:
                pickle.dump(self.knowledge_chunks, f)
        
        logger.info(f"Exported {len(data)} chunks to {file_path}")
    
    def search_by_similar_example(self, example_text: str, top_k: int = 3) -> List[SearchResult]:
        return self.search(example_text, top_k=top_k)
    
    def get_recommended_prerequisites(self, topic: str, current_skill_level: str = 'beginner') -> List[str]:
        relevant_chunks = [c for c in self.knowledge_chunks if c.topic == topic]
        if not relevant_chunks:
            return []
        
        all_prerequisites = set()
        difficulty_order = {'easy': 1, 'medium': 2, 'hard': 3, 'expert': 4}
        current_level_num = difficulty_order.get(current_skill_level, 1)
        
        for chunk in relevant_chunks:
            chunk_level_num = difficulty_order.get(chunk.difficulty, 2)
            if chunk_level_num <= current_level_num:
                all_prerequisites.update(chunk.prerequisites)
        
        return sorted(list(all_prerequisites))