"""Catalogue summary statistics."""

import duckdb


class CatalogueStats:
    """Prints summary statistics for the artdig catalogue."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def run(self):
        self._counts()
        self._top_classifications()
        self._date_range()
        self._top_nationalities()

    def _counts(self):
        print("=== Record Counts ===")
        rows = self.conn.execute("""
            SELECT source, count(*) AS cnt
            FROM artworks
            GROUP BY source
            ORDER BY source
        """).fetchall()
        total = 0
        for source, cnt in rows:
            print(f"  {source}: {cnt:,}")
            total += cnt
        print(f"  total: {total:,}")
        print()

    def _top_classifications(self):
        print("=== Top Classifications ===")
        rows = self.conn.execute("""
            SELECT classification, count(*) AS cnt
            FROM artworks
            WHERE classification IS NOT NULL
            GROUP BY classification
            ORDER BY cnt DESC
            LIMIT 15
        """).fetchall()
        for cls, cnt in rows:
            print(f"  {cls}: {cnt:,}")
        print()

    def _date_range(self):
        print("=== Date Range ===")
        row = self.conn.execute("""
            SELECT
                min(date_start) AS earliest,
                max(date_end) AS latest,
                round(avg(date_start), 0) AS avg_start
            FROM artworks
            WHERE date_start IS NOT NULL
        """).fetchone()
        print(f"  earliest: {row[0]}")
        print(f"  latest:   {row[1]}")
        print(f"  avg start year: {int(row[2])}")
        print()

    def _top_nationalities(self):
        print("=== Top Artist Nationalities ===")
        rows = self.conn.execute("""
            SELECT artist_nationality, count(*) AS cnt
            FROM artworks
            WHERE artist_nationality IS NOT NULL
            GROUP BY artist_nationality
            ORDER BY cnt DESC
            LIMIT 10
        """).fetchall()
        for nat, cnt in rows:
            print(f"  {nat}: {cnt:,}")
        print()
