from kaizen import KaizenClient


client = KaizenClient()

response = client.akuma.query(
    dialect="postgres",
    prompt="Top 10 customers by MRR last month",
    mode="sql-only",
)

if response.error:
    raise RuntimeError(response.error)

print(response.sql)
