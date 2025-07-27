from uuid import uuid4

from budmicroframe.commons import logging
from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase
from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import func

from ..commons.constants import LeaderboardDataOrigin, ModelDownloadStatus, ModelExtractionStatus


logger = logging.get_logger(__name__)


class Source(PSQLBase):
    """Sources model."""

    __tablename__ = "source"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False, index=True)
    url = Column(Text(), nullable=False)
    wait_for = Column(Text(), nullable=True)
    js_code = Column(Text(), nullable=True)
    schema = Column(Text(), nullable=True)
    css_base_selector = Column(Text(), nullable=True)
    is_active = Column(Boolean, unique=False, default=True, nullable=False)
    last_extracted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    leaderboards = relationship("Leaderboard", back_populates="source")

    def __repr__(self) -> str:
        """Represent the source model."""
        return f"<Sources(id={self.id}, name={self.name}, url={self.url})>"


class Leaderboard(PSQLBase):
    """Leaderboard model."""

    __tablename__ = "leaderboard"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    model_info_id = Column(UUID(as_uuid=True), ForeignKey("model_info.id"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("source.id"), nullable=True)

    # Dynamic metric fields
    eval_name = Column(String(100), nullable=False, index=True)
    normalised_eval_name = Column(String(100), nullable=False, index=True)
    eval_score = Column(Float, nullable=True)

    data_origin = Column(Enum(LeaderboardDataOrigin), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    model_info = relationship("ModelInfoSchema", back_populates="leaderboards")
    source = relationship("Source", back_populates="leaderboards")

    def __repr__(self):
        """Return string representation of Leaderboard."""
        return f"<Leaderboard(model_info_id={self.model_info_id}, benchmark_name={self.benchmark_name}, value={self.benchmark_value})>"


class LicenseInfoSchema(PSQLBase):
    __tablename__ = "license_info"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    license_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    url = Column(Text)
    faqs = Column(JSONB)
    type = Column(Text)
    description = Column(Text)
    suitability = Column(Text)
    is_extracted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    modified_at = Column(DateTime(timezone=True), onupdate=func.now())

    model_info = relationship("ModelInfoSchema", back_populates="license")

    def __repr__(self):
        """Return string representation of LicenseInfo."""
        return f"<LicenseInfo(id={self.id}, license_id={self.license_id}, name={self.name}, url={self.url})>"


class ModelInfoSchema(PSQLBase):
    __tablename__ = "model_info"

    id = Column(UUID(as_uuid=True), default=uuid4)
    author = Column(Text)
    description = Column(Text)
    uri = Column(Text, nullable=False)
    modality = Column(Text)
    tags = Column(JSONB)
    tasks = Column(JSONB)
    papers = Column(JSONB)
    github_url = Column(Text)
    provider_url = Column(Text)
    website_url = Column(Text)
    logo_url = Column(Text)
    use_cases = Column(JSONB)
    strengths = Column(JSONB)
    limitations = Column(JSONB)
    model_tree = Column(JSONB)
    languages = Column(JSONB)
    architecture = Column(JSONB)
    extraction_status = Column(Enum(ModelExtractionStatus), nullable=False)
    license_id = Column(UUID(as_uuid=True), ForeignKey("license_info.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    modified_at = Column(DateTime(timezone=True), onupdate=func.now())

    license = relationship("LicenseInfoSchema", back_populates="model_info")
    leaderboards = relationship(Leaderboard, back_populates="model_info")

    __table_args__ = (
        UniqueConstraint("uri", name="uq_model_info_uri"),  # Enforce unique constraint
        PrimaryKeyConstraint("id"),  # Keep the primary key on id
    )

    def __repr__(self):
        """Return string representation of ModelInfo."""
        return f"<ModelInfo(uri={self.uri}, modality={self.modality}, tasks={self.tasks})>"


class ModelDownloadHistory(PSQLBase):
    __tablename__ = "model_download_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    status = Column(Enum(ModelDownloadStatus), nullable=False)
    size = Column(Float, nullable=False)  # Size in GB
    path = Column(Text, nullable=False)  # Path to downloaded model
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    modified_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        """Return string representation of ModelDownloadHistory."""
        return (
            f"<ModelDownloadHistory(id={self.id}, status={self.status}, size={self.size}, "
            f"path={self.path}, created_at={self.created_at})>"
        )


class LicenseInfoCRUD(CRUDMixin[LicenseInfoSchema, None, None]):
    __model__ = LicenseInfoSchema

    def __init__(self):
        """Initialize LicenseInfoCRUD."""
        super().__init__(model=self.__model__)


class ModelInfoCRUD(CRUDMixin[ModelInfoSchema, None, None]):
    __model__ = ModelInfoSchema

    def __init__(self):
        """Initialize ModelInfoCRUD."""
        super().__init__(model=self.__model__)

    def check_existing_model(self, model_uri: str, extraction_status: ModelExtractionStatus) -> dict | None:
        """Check if model exists with given URI and extraction status."""
        session: Session = self.get_session()
        query = (
            session.query(ModelInfoSchema, LicenseInfoSchema)
            .join(LicenseInfoSchema, ModelInfoSchema.license_id == LicenseInfoSchema.id, isouter=True)
            .filter(ModelInfoSchema.uri == model_uri, ModelInfoSchema.extraction_status == extraction_status)
        )
        result = query.one_or_none()

        if result:
            existing_model, license_details = result

            license_dict = {
                "id": existing_model.license_id,
                "name": license_details.name if license_details else None,
                "url": license_details.url if license_details else None,
                "faqs": license_details.faqs if license_details else None,
                "type": license_details.type if license_details else None,
                "description": license_details.description if license_details else None,
                "suitability": license_details.suitability if license_details else None,
            }

            return {
                "author": existing_model.author,
                "description": existing_model.description,
                "uri": existing_model.uri,
                "modality": existing_model.modality,
                "tags": existing_model.tags,
                "tasks": existing_model.tasks,
                "papers": existing_model.papers,
                "github_url": existing_model.github_url,
                "provider_url": existing_model.provider_url,
                "website_url": existing_model.website_url,
                "logo_url": existing_model.logo_url,
                "use_cases": existing_model.use_cases,
                "strengths": existing_model.strengths,
                "limitations": existing_model.limitations,
                "model_tree": existing_model.model_tree,
                "languages": existing_model.languages,
                "architecture": existing_model.architecture,
                "license": license_dict,
                "extraction_status": existing_model.extraction_status,
            }
        return None


class ModelDownloadHistoryCRUD(CRUDMixin[ModelDownloadHistory, None, None]):
    __model__ = ModelDownloadHistory

    def __init__(self):
        """Initialize ModelDownloadHistoryCRUD."""
        super().__init__(model=self.__model__)
