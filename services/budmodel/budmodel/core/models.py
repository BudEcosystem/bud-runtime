from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func


def get_db_uri():
    # with open('secrets.json') as f:
    #     secrets = json.load(f)
    #     uri =  secrets.get("db_uri")
    #     return uri
    # TODO: Use the PSQL service for db management and keep the models in the target modules
    pass


DATABASE_URL = get_db_uri()

# Set up the PostgreSQL database engine
# engine = create_engine(DATABASE_URL, echo=True)

# Declare a base for the models
Base = declarative_base()


class Sources(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    url = Column(Text(), nullable=False)
    wait_for = Column(Text(), nullable=True)
    js_code = Column(Text(), nullable=True)
    schema = Column(Text(), nullable=True)
    css_base_selector = Column(Text(), nullable=True)
    is_active = Column(Boolean, unique=False, default=True, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    models = relationship("Models", back_populates="source")


class Models(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=True)
    rank = Column(String(100), nullable=True)
    url = Column(Text, nullable=True)

    # APAC Eval Leaderboard fields
    lc_win_rate = Column(String, nullable=True)
    win_rate = Column(String, nullable=True)

    # Berkeley Leaderboard fields
    overall_accuracy = Column(String, nullable=True)
    latency_cost = Column(String, nullable=True)
    latency_mean = Column(String, nullable=True)
    latency_sd = Column(String, nullable=True)
    latency_p95 = Column(String, nullable=True)
    single_turn_non_live_ast_summary = Column(String, nullable=True)
    single_turn_non_live_ast_simple = Column(String, nullable=True)
    single_turn_non_live_ast_multiple = Column(String, nullable=True)
    single_turn_non_live_ast_parallel = Column(String, nullable=True)
    single_turn_non_live_ast_multiple_parallel = Column(String, nullable=True)
    single_turn_non_live_exe_summary = Column(String, nullable=True)
    single_turn_non_live_exe_simple = Column(String, nullable=True)
    single_turn_non_live_exe_multiple = Column(String, nullable=True)
    single_turn_non_live_exe_parallel = Column(String, nullable=True)
    single_turn_non_live_exe_multiple_parallel = Column(String, nullable=True)
    single_turn_live_ast_summary = Column(String, nullable=True)
    single_turn_live_ast_simple = Column(String, nullable=True)
    single_turn_live_ast_multiple = Column(String, nullable=True)
    single_turn_live_ast_parallel = Column(String, nullable=True)
    single_turn_live_ast_multiple_parallel = Column(String, nullable=True)
    multi_turn_overall_accuracy = Column(String, nullable=True)
    multi_turn_base = Column(String, nullable=True)
    multi_miss_func = Column(String, nullable=True)
    multi_miss_param = Column(String, nullable=True)
    multi_long_context = Column(String, nullable=True)
    multi_composite = Column(String, nullable=True)
    hallucination_measurement_relevance = Column(String, nullable=True)
    hallucination_measurement_irrelevance = Column(String, nullable=True)
    organization = Column(String(100), nullable=True)
    license = Column(String(100), nullable=True)

    # LiveCodeBench Leaderboard fields
    pass_1 = Column(String, nullable=True)
    easy_pass_1 = Column(String, nullable=True)
    medium_pass_1 = Column(String, nullable=True)
    hard_pass_1 = Column(String, nullable=True)

    # MTEB Leaderboard fields
    model_size_million_parameters = Column(String, nullable=True)
    memory_usage_gb_fp32 = Column(String, nullable=True)
    embedding_dimensions = Column(String, nullable=True)
    max_tokens = Column(String, nullable=True)
    average_56_datasets = Column(String, nullable=True)
    classification_average_12_datasets = Column(String, nullable=True)
    clustering_average_11_datasets = Column(String, nullable=True)
    pair_classification_average_3_datasets = Column(String, nullable=True)
    reranking_average_4_datasets = Column(String, nullable=True)
    retrieval_average_15_datasets = Column(String, nullable=True)
    sts_average_10_datasets = Column(String, nullable=True)
    summarization_average_1_datasets = Column(String, nullable=True)

    # UGI Leaderboard fields (with _score suffixes)
    ugi_score = Column(String, nullable=True)
    w_10_score = Column(String, nullable=True)
    i_10_score = Column(String, nullable=True)
    unruly_score = Column(String, nullable=True)
    internet_score = Column(String, nullable=True)
    stats_score = Column(String, nullable=True)
    writing_score = Column(String, nullable=True)
    polcontro_score = Column(String, nullable=True)

    # VLLM Leaderboard fields
    param_b = Column(String, nullable=True)
    language_model = Column(String(100), nullable=True)
    vision_model = Column(String(100), nullable=True)
    avg_score = Column(String, nullable=True)
    avg_rank = Column(String, nullable=True)
    mmbench_v11 = Column(String, nullable=True)
    mmstar = Column(String, nullable=True)
    mmmu_val = Column(String, nullable=True)
    mathvista = Column(String, nullable=True)
    ocrbench = Column(String, nullable=True)
    ai2d = Column(String, nullable=True)
    hallusionbench = Column(String, nullable=True)
    mmvet = Column(String, nullable=True)

    # Chatbot Arena Leaderboard fields
    rank_ub = Column(String(100), nullable=True)
    rank_style_ctrl = Column(String(100), nullable=True)
    arena_score = Column(String, nullable=True)
    confidence_interval = Column(String(100), nullable=True)
    votes = Column(String, nullable=True)
    knowledge_cutoff = Column(String(100), nullable=True)

    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    source = relationship("Sources", back_populates="models")


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    parallel_count = Column(Integer, default=5, nullable=False)
    status = Column(String(50), default="idle", nullable=False)  # e.g., 'idle', 'running', 'completed', 'failed'
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
