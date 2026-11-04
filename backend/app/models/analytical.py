"""
Modelos analíticos alimentados pela camada Gold (CSVs exportados pelo pipeline).
Tratados como SOMENTE LEITURA pelo portal e pelo agente de IA.
"""
from sqlalchemy import Column, String, Integer, BigInteger, Numeric, Index
from app.db.base import Base


class GoldIndicador(Base):
    """
    Agregação de indicadores da camada Gold.
    No PostgreSQL, valores monetários utilizam Numeric/Decimal para evitar imprecisão de float.
    """
    __tablename__ = "gold_indicadores"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    competencia = Column(String(7), nullable=False, index=True)  # YYYY-MM
    municipio = Column(String(100), nullable=True, index=True)
    bairro = Column(String(100), nullable=True)
    classe = Column(String(50), nullable=True, index=True)
    # Numeric com escala 2 para valores financeiros (R$)
    receita_total = Column(Numeric(precision=14, scale=2), nullable=True)
    # Numeric com escala 4 para medidas de energia (kWh)
    energia_consumida_kwh = Column(Numeric(precision=14, scale=4), nullable=True)
    ucs_ativas = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_gold_ind_comp_mun_classe", "competencia", "municipio", "classe"),
    )
