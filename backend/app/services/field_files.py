"""CSV operacional de campo; não altera tabelas analíticas."""
import csv
import io
import base64
import zipfile

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.schemas.inspections import OrderResultRequest
from app.services import inspections


class FieldUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv: str | None = Field(None, min_length=1, max_length=1_000_000)
    xlsx: str | None = Field(None, min_length=1, max_length=1_400_000)

    @model_validator(mode="after")
    def one_format(self):
        if (self.csv is None) == (self.xlsx is None):
            raise ValueError("Envie somente um arquivo CSV ou XLSX.")
        return self


def read_xlsx(content: str) -> str:
    from openpyxl import load_workbook
    raw = base64.b64decode(content, validate=True)
    if len(raw) > 1_000_000:
        raise ValueError("Arquivo excede 1 MB.")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 10_000_000 or len(archive.infolist()) > 100:
            raise ValueError("Planilha excessivamente grande.")
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    try:
        sheet = workbook['Resultados']
        output = io.StringIO(newline='')
        writer = csv.writer(output, delimiter=';')
        for index, row in enumerate(sheet.iter_rows(), 1):
            if index > 501 or len(row) > 4:
                raise ValueError("Use até 500 ordens e as quatro colunas do modelo.")
            values = []
            for cell in row:
                if cell.data_type == 'f':
                    raise ValueError("Fórmulas não são aceitas na planilha de resultados.")
                values.append(cell.value)
            if index == 1 and values != ['ordem_id', 'versao', 'uc_id', 'resultado']:
                raise ValueError("Cabeçalho diferente do modelo.")
            if not any(value is not None for value in values):
                continue
            writer.writerow(values)
        return output.getvalue()
    finally:
        workbook.close()


def field_template(db: Session) -> dict:
    from openpyxl import Workbook
    from app.models.operational import InspectionOrder, OrderStatus
    orders = db.query(InspectionOrder).filter(InspectionOrder.status == OrderStatus.IN_PROGRESS).order_by(InspectionOrder.id).limit(501).all()
    if len(orders) > 500:
        raise ValueError("Há mais de 500 ordens em andamento. Reduza o lote antes de baixar o modelo.")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Resultados'
    sheet.append(['ordem_id', 'versao', 'uc_id', 'resultado'])
    for order in orders:
        sheet.append([str(order.id), order.version, order.uc_id, None])
        sheet.cell(sheet.max_row, 3).data_type = 's'
    sheet.freeze_panes = 'D2'
    for column, width in [('A', 22), ('B', 12), ('C', 24), ('D', 80)]:
        sheet.column_dimensions[column].width = width
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return {'xlsx': base64.b64encode(output.getvalue()).decode(), 'count': len(orders)}


def import_results(db: Session, content: str, actor: str) -> dict:
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')), delimiter=';')
    if reader.fieldnames not in (['ordem_id', 'versao', 'resultado'], ['ordem_id', 'versao', 'uc_id', 'resultado']):
        return {"imported": 0, "errors": [{"line": 1, "message": "Use as colunas ordem_id;versao;resultado, nesta ordem."}]}
    try:
        rows = list(reader)
    except csv.Error:
        return {"imported": 0, "errors": [{"line": 1, "message": "CSV inválido ou campo excessivamente grande."}]}
    if not rows or len(rows) > 500:
        return {"imported": 0, "errors": [{"line": 1, "message": "Envie de 1 a 500 resultados."}]}
    imported, errors, seen = 0, [], set()
    for line, row in enumerate(rows, 2):
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError()
            order_id = int(row['ordem_id'])
            if order_id < 1 or order_id > 9223372036854775807 or order_id in seen:
                raise ValueError()
            seen.add(order_id)
            payload = OrderResultRequest(version=int(row['versao']), result=row['resultado'])
        except (ValueError, ValidationError):
            errors.append({"line": line, "message": "ID/versão inválido, ordem repetida ou resultado vazio/excessivo."})
            continue
        try:
            if 'uc_id' in row:
                existing = inspections.get_order(db, order_id)
                if existing is not None and row['uc_id'] != existing.uc_id:
                    errors.append({"line": line, "message": "A UC não corresponde à ordem do modelo."})
                    continue
            order = inspections.register_result(db, order_id, payload, actor=actor)
            if order is None:
                errors.append({"line": line, "message": "Ordem não encontrada."})
            else:
                imported += 1
        except inspections.OrderConflictError as exc:
            db.rollback()
            errors.append({"line": line, "message": str(exc)})
    return {"imported": imported, "errors": errors}
