from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.base import Base

# Configuração de engine e pool de conexões otimizado para PostgreSQL
engine_kwargs = {
    "echo": settings.DB_ECHO,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Boas práticas de pooling para PostgreSQL
    engine_kwargs.update(
        {
            "pool_pre_ping": True,  # Testa conexão antes de reutilizar para evitar conexões mortas
            "pool_size": settings.DB_POOL_SIZE,  # Conexões ativas mantidas no pool
            "max_overflow": settings.DB_MAX_OVERFLOW,  # Conexões adicionais temporárias em picos
            "pool_timeout": settings.DB_POOL_TIMEOUT,  # Tempo máx de espera por uma conexão livre (segundos)
            "pool_recycle": settings.DB_POOL_RECYCLE,  # Reciclagem periódica para evitar timeouts do servidor
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session and ensures closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
