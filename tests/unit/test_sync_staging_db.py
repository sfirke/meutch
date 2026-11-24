import pytest

from sync_staging_db import strip_pg_attver


@pytest.mark.parametrize(
    "line, expected",
    [
        ("ALTER TABLE ONLY public.users ALTER COLUMN email SET (pg_attver=2);\n", ""),
        (
            "ALTER TABLE ONLY public.item ALTER COLUMN name SET (n_distinct=100, pg_attver=2);\n",
            "ALTER TABLE ONLY public.item ALTER COLUMN name SET (n_distinct=100);\n",
        ),
        (
            "ALTER TABLE ONLY public.item ALTER COLUMN name SET (n_distinct=100);\n",
            "ALTER TABLE ONLY public.item ALTER COLUMN name SET (n_distinct=100);\n",
        ),
    ],
)
def test_strip_pg_attver(line, expected):
    sql = f"CREATE TABLE public.t (id integer);\n{line}COPY public.t (id) FROM stdin;\n"
    assert strip_pg_attver(sql) == (
        f"CREATE TABLE public.t (id integer);\n{expected}COPY public.t (id) FROM stdin;\n"
    )
