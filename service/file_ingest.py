
import io, re
import pandas as pd

TEXT_ALIASES = ("text", "review", "content", "comment", "message")

# TEXT_ALIASES là một tuple chứa các tên cột gợi ý mà code đoán là cột chứa text:
def _choose_text_col(df: pd.DataFrame, stt_key: str | None) -> str | None:
    # Ưu tiên theo alias
    # Chuẩn hoá tên cột: bỏ BOM \ufeff, strip và lower
    import re
    lower_map = {re.sub(r"\s+", "", c.lower()): c for c in df.columns}

    # nếu có cột chứa tên trong TEXT_ALIASES thì chọn cột đó
    for k in TEXT_ALIASES:
        if k in lower_map:
            return lower_map[k]
    # Nếu có cột stt thì chọn cột còn lại khác stt
    if stt_key:
        for c in df.columns:
            if c != stt_key:
                return c
    # Fallback: cột đầu
    return df.columns[0] if len(df.columns) else None

def _looks_invalid_text(series: pd.Series) -> bool:
    """'Xấu' nếu đa số là số/rỗng (không phải câu chữ)."""
    # convert toàn bộ sang str
    s = series.astype(str).str.strip()
    # nếu k có thì nghĩa là review invalid
    if s.empty:
        return True
    # True = 1, False = 0, lấy mean của cột, nếu hơn 60% cột invalid thì cột đó được xem là invalid
    frac_bad = ((s == "") | s.str.fullmatch(r"\d+")).mean()
    return frac_bad >= 0.6

# ---------- TXT ----------
def parse_txt_bytes(b: bytes, encoding: str = "utf-8") -> list[tuple[str, str]]:
    # Decode byte sang string (UTF-8)
    s = b.decode(encoding, errors="ignore")
    # tách dòng, strip và loại bỏ dòng rỗng
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return []
    # Header kiểu: "stt text" hoặc "stt review", bỏ qua viết hoa
    if re.match(r"^stt(\s+|\t+)(text|review)\b", lines[0], flags=re.I):
        # nếu match thì append từng dòng vào rows
        rows: list[tuple[str, str]] = []
        for ln in lines[1:]:
            m = re.match(r"^(\d+)\s+(.+)$", ln)
            if m:
                rows.append((m.group(1), m.group(2).strip().strip('"')))
        return rows
    #nếu k match thì mỗi dòng là 1 review và tự gán stt
    return [(str(i + 1), ln) for i, ln in enumerate(lines)]

# ---------- CSV ----------
def parse_csv_bytes(b: bytes) -> list[tuple[str, str]]:
    # đoán seperator vì những file csv sẽ có nhiều kiểu seperator khác nhau 
    # biến bytes upload thành "file" trong RAM để Pandas đọc, thử các seperator và cho phép Pandas đọc regex separator
    for sep_try in [None, ",", ";", r"\s+"]:
        try:
            df = pd.read_csv(io.BytesIO(b), sep=sep_try, engine="python")
            # nếu đọc thành công thì break
            if df.shape[1] >= 1:
                break
        except Exception:
            continue

    # Chuẩn hoá header (strip + remove BOM)
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    lower_map = {c.lower(): c for c in df.columns}
    # chọn stt và cột chứa text
    stt_key = lower_map.get("stt")
    txt_key = _choose_text_col(df, stt_key)
    # kiểm tra cột có valid không, nếu không thì tìm cột khác
    if stt_key and txt_key:
        s_stt = df[stt_key]
        s_txt = df[txt_key]
        if _looks_invalid_text(s_txt):
            for c in df.columns:
                if c != stt_key and not _looks_invalid_text(df[c]):
                    txt_key = c
                    s_txt = df[c]
                    break
        # gom 2 cột đã chọn (STT và TEXT) thành một DataFrame nhỏ gọn, rồi loại bỏ dòng rỗng và biến df thành list
        sub = pd.DataFrame({"stt": s_stt, "text": s_txt}).dropna()
        return [(str(r["stt"]).strip(), str(r["text"]).strip()) for _, r in sub.iterrows()]

    # Không có 'stt' → coi cột văn bản là txt_key, tự gán stt
    if txt_key:
        texts = df[txt_key].dropna().astype(str).str.strip().tolist()
        return [(str(i + 1), t) for i, t in enumerate(texts)]

    return []

# ---------- XLSX ----------
def parse_xlsx_bytes(b: bytes) -> list[tuple[str, str]]:
    df = pd.read_excel(io.BytesIO(b))
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    lower_map = {c.lower(): c for c in df.columns}

    stt_key = lower_map.get("stt")
    txt_key = _choose_text_col(df, stt_key)

    if stt_key and txt_key:
        s_stt = df[stt_key]
        s_txt = df[txt_key]
        if _looks_invalid_text(s_txt):
            for c in df.columns:
                if c != stt_key and not _looks_invalid_text(df[c]):
                    txt_key = c
                    s_txt = df[c]
                    break
        sub = pd.DataFrame({"stt": s_stt, "text": s_txt}).dropna()
        return [(str(r["stt"]).strip(), str(r["text"]).strip()) for _, r in sub.iterrows()]

    if txt_key:
        texts = df[txt_key].dropna().astype(str).str.strip().tolist()
        return [(str(i + 1), t) for i, t in enumerate(texts)]

    return []
