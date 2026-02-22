"""CSV/Excel import service for products."""

from decimal import Decimal
from io import BytesIO
from uuid import UUID

import pandas as pd


def parse_products_file(
    content: bytes,
    filename: str,
    user_id: UUID,
) -> tuple[list[dict], list[dict]]:
    """
    Parse CSV or Excel file. Returns (products_to_create, errors).
    Columns: name, sku, price, url, category.
    """
    errors: list[dict] = []
    products: list[dict] = []

    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        elif filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(BytesIO(content))
        else:
            return [], [{"row": 0, "message": "Unsupported file format. Use CSV or Excel."}]
    except Exception as e:
        return [], [{"row": 0, "message": str(e)}]

    required_columns = {"name", "price"}
    df_columns = set(c.lower().strip() for c in df.columns)
    if not required_columns.issubset(df_columns):
        missing = required_columns - df_columns
        return [], [{"row": 0, "message": f"Missing required columns: {', '.join(missing)}"}]

    column_map = {c.lower().strip(): c for c in df.columns}

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # 1-based, +1 for header
        try:
            name = _get_cell(row, column_map, "name")
            if not name or (isinstance(name, str) and not name.strip()):
                errors.append({"row": row_num, "message": "Name is required"})
                continue

            price_val = _get_cell(row, column_map, "price")
            if price_val is None or (isinstance(price_val, str) and not price_val.strip()):
                errors.append({"row": row_num, "message": "Price is required"})
                continue

            try:
                price = Decimal(str(price_val).replace(",", ".").replace(" ", ""))
            except Exception:
                errors.append({"row": row_num, "message": "Invalid price format"})
                continue

            if price < 0:
                errors.append({"row": row_num, "message": "Price must be non-negative"})
                continue

            sku = _get_cell(row, column_map, "sku")
            url = _get_cell(row, column_map, "url")
            category = _get_cell(row, column_map, "category")

            products.append({
                "user_id": user_id,
                "name": str(name).strip()[:500],
                "sku": str(sku).strip()[:100] if sku and str(sku).strip() else None,
                "current_price": price,
                "currency": "RUB",
                "url": str(url).strip() if url and str(url).strip() else None,
                "category": str(category).strip()[:200] if category and str(category).strip() else None,
            })
        except Exception as e:
            errors.append({"row": row_num, "message": str(e)})

    return products, errors


def _get_cell(row, column_map: dict, key: str):
    """Get cell value by column name (case-insensitive)."""
    for col_key, col_orig in column_map.items():
        if col_key == key.lower():
            val = row.get(col_orig)
            if pd.isna(val):
                return None
            return val
    return None


def get_csv_template() -> str:
    """Return CSV template content with headers."""
    return "name,sku,price,url,category\n"


def preview_products_file(
    content: bytes,
    filename: str,
    limit: int = 5,
) -> tuple[list[dict], list[dict]]:
    """
    Parse CSV or Excel and return first N rows as preview.
    Returns (preview_rows, errors). Preview rows are dicts with keys: name, sku, price, url, category.
    """
    errors: list[dict] = []
    preview: list[dict] = []

    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        elif filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(BytesIO(content))
        else:
            return [], [{"row": 0, "message": "Unsupported file format. Use CSV or Excel."}]
    except Exception as e:
        return [], [{"row": 0, "message": str(e)}]

    required_columns = {"name", "price"}
    df_columns = set(c.lower().strip() for c in df.columns)
    if not required_columns.issubset(df_columns):
        missing = required_columns - df_columns
        return [], [{"row": 0, "message": f"Missing required columns: {', '.join(missing)}"}]

    column_map = {c.lower().strip(): c for c in df.columns}

    for idx, row in df.head(limit).iterrows():
        try:
            name = _get_cell(row, column_map, "name")
            price_val = _get_cell(row, column_map, "price")
            sku = _get_cell(row, column_map, "sku")
            url = _get_cell(row, column_map, "url")
            category = _get_cell(row, column_map, "category")

            preview.append({
                "name": str(name).strip() if name else "",
                "sku": str(sku).strip() if sku else "",
                "price": str(price_val) if price_val is not None else "",
                "url": str(url).strip() if url else "",
                "category": str(category).strip() if category else "",
            })
        except Exception:
            preview.append({"name": "", "sku": "", "price": "", "url": "", "category": ""})

    return preview, errors
