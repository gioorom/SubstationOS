from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database.database import Base


class Document(Base):

    __tablename__ = "documents"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    filename = Column(
        String,
        nullable=False
    )

    category = Column(
        String,
        default="Unknown"
    )

    project = Column(
        String,
        default="Unknown"
    )

    revision = Column(
        String,
        default="00"
    )

    file_path = Column(
        String,
        nullable=False
    )

    uploaded_at = Column(
        DateTime,
        default=datetime.utcnow
    )