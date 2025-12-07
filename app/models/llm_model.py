"""LLM Model with benchmark scores matching DevPort API schema"""

from sqlalchemy import Column, BigInteger, String, Text, DateTime, DECIMAL, Index, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime

from app.config.database import Base


class LLMModel(Base):
    """
    LLM Model with comprehensive benchmark scores

    Data source: Artificial Analysis API
    https://api.artificialanalysis.ai/v1/get/data/llms/models
    """
    __tablename__ = "llm_models"

    id = Column(BigInteger, primary_key=True, index=True)

    # API identifiers
    external_id = Column(String(100), unique=True, nullable=True, index=True)  # API "id": "4559e9f0-8aad-4681-89fb-68cb915e0f16"
    slug = Column(String(200), unique=True, nullable=True, index=True)  # API "slug": "qwen3-14b-instruct-reasoning"

    # Model identification
    model_id = Column(String(100), nullable=False, unique=True, index=True)  # Your internal ID (can use slug or generate)
    model_name = Column(String(200), nullable=False)  # e.g., "GPT-4 Turbo"
    release_date = Column(Date, nullable=True)  # API "release_date": "2025-04-28"

    # Provider (legacy field - now optional, use model_creator relationship instead)
    provider = Column(String(100), nullable=True, index=True)  # e.g., "OpenAI", "Anthropic"

    # Model Creator relationship (new)
    model_creator_id = Column(BigInteger, ForeignKey('model_creators.id'), nullable=True, index=True)
    model_creator = relationship("ModelCreator", backref="models")

    description = Column(Text, nullable=True)

    # Pricing (USD per million tokens)
    price_input = Column(DECIMAL(10, 2), nullable=True)  # Input token price
    price_output = Column(DECIMAL(10, 2), nullable=True)  # Output token price
    price_blended = Column(DECIMAL(10, 2), nullable=True)  # Blended price (3:1 ratio)

    # Performance metrics
    context_window = Column(BigInteger, nullable=True)  # Max tokens (e.g., 1000000 for 1M)
    output_speed_median = Column(DECIMAL(10, 2), nullable=True)  # Tokens per second
    latency_ttft = Column(DECIMAL(10, 4), nullable=True)  # Time to first token (seconds)
    median_time_to_first_answer_token = Column(DECIMAL(10, 4), nullable=True)  # Time to first answer token (seconds)
    license = Column(String(50), nullable=True)  # "Open" or "Proprietary"

    # Benchmark Scores - Agentic Capabilities (2)
    score_terminal_bench_hard = Column(DECIMAL(5, 2), nullable=True)  # Agentic Coding & Terminal
    score_tau_bench_telecom = Column(DECIMAL(5, 2), nullable=True)  # Agentic Tool Use

    # Benchmark Scores - Reasoning & Knowledge (4)
    score_aa_lcr = Column(DECIMAL(5, 2), nullable=True)  # Long Context Reasoning
    score_humanitys_last_exam = Column(DECIMAL(5, 2), nullable=True)  # Reasoning & Knowledge
    score_mmlu_pro = Column(DECIMAL(5, 2), nullable=True)  # Reasoning & Knowledge
    score_gpqa_diamond = Column(DECIMAL(5, 2), nullable=True)  # Scientific Reasoning

    # Benchmark Scores - Coding (2)
    score_livecode_bench = Column(DECIMAL(5, 2), nullable=True)  # Coding
    score_scicode = Column(DECIMAL(5, 2), nullable=True)  # Coding

    # Benchmark Scores - Specialized Skills (6)
    score_ifbench = Column(DECIMAL(5, 2), nullable=True)  # Instruction Following
    score_math_500 = Column(DECIMAL(5, 2), nullable=True)  # Math 500
    score_aime = Column(DECIMAL(5, 2), nullable=True)  # AIME (general)
    score_aime_2025 = Column(DECIMAL(5, 2), nullable=True)  # AIME 2025 (specific year)
    score_crit_pt = Column(DECIMAL(5, 2), nullable=True)  # Physics Reasoning
    score_mmmu_pro = Column(DECIMAL(5, 2), nullable=True)  # Visual Reasoning

    # Benchmark Scores - Composite Indices (4)
    score_aa_intelligence_index = Column(DECIMAL(5, 2), nullable=True, index=True)  # Overall Intelligence
    score_aa_omniscience_index = Column(DECIMAL(5, 2), nullable=True)  # Omniscience Index
    score_aa_coding_index = Column(DECIMAL(5, 2), nullable=True)  # Coding Index
    score_aa_math_index = Column(DECIMAL(5, 2), nullable=True)  # Math Index

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for performance
    __table_args__ = (
        Index('idx_llm_provider', 'provider'),
        Index('idx_llm_model_id', 'model_id'),
        Index('idx_llm_intelligence_score', 'score_aa_intelligence_index'),
    )

    def __repr__(self):
        return f"<LLMModel {self.model_id}: {self.model_name}>"
