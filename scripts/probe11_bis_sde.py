"""Dossier-11 probe: BIS debt securities statistics bulk (WS_SDE) — government
and corporate securities by residual maturity, for the maturing-principal proxy
(M2 government variant) and as an S.12 debt-stock source.

Run: uv run python scripts/probe11_bis_sde.py
"""

import io
import zipfile

import httpx
import polars as pl

URL = "https://data.bis.org/static/bulk/WS_SDE_csv_col.zip"


def main() -> None:
    with httpx.Client(follow_redirects=True, timeout=300) as client:
        r = client.get(URL, headers={"User-Agent": "debt-monitor-probe/0.1"})
        print(f"HTTP {r.status_code} content-type={r.headers.get('content-type')} bytes={len(r.content)}")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        print(f"members: {zf.namelist()}")
        # data file is the largest csv
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        data_name = max(names, key=lambda n: zf.getinfo(n).file_size)
        print(f"\ndata file: {data_name} ({zf.getinfo(data_name).file_size // 1024} KB)")
        df = pl.read_csv(io.BytesIO(zf.read(data_name)))
        print(f"shape={df.shape}")
        print(f"columns: {df.columns}")

        for col in df.columns:
            if col and col[0].isupper() and df[col].dtype == pl.String:
                vals = df[col].unique().to_list()
                if len(vals) <= 25:
                    print(f"  {col}: {sorted(vals)}")

        # sample: US government debt, maturity <= 1y, latest periods
        dim_cols = [c for c in df.columns if not c[:1].isdigit()]
        period_cols = [c for c in df.columns if c[:1].isdigit()]
        print(f"\nperiod range: {period_cols[0]} .. {period_cols[-1]}")

        cty_col = next(c for c in df.columns if "COUNTRY" in c.upper())
        mat_col = next((c for c in df.columns if "RMAT" in c.upper() or "MATURITY" in c.upper()), None)
        print(f"country col={cty_col}, maturity col={mat_col}")
        if mat_col:
            print(f"maturity codes: {sorted(df[mat_col].unique().to_list())}")
        sec_col = next(
            (c for c in df.columns if "SECTOR" in c.upper() and "BORROWERS" not in c.upper() and "LENDERS" not in c.upper()),
            None,
        )
        print(f"issuer sector col={sec_col}: {sorted(df[sec_col].unique().to_list()) if sec_col else '-'}")

        # latest column values for US rows
        last = period_cols[-1]
        us = df.filter(pl.col(cty_col) == "United States")
        print(f"\nUS rows: {us.height}; distinct series keys sample:")
        for row in us.head(12).iter_rows(named=True):
            dims = {c: row[c] for c in dim_cols}
            print(f"  {dims} -> {row[last]}")


if __name__ == "__main__":
    main()
