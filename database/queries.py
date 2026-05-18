from decimal import Decimal
import asyncpg


def _row(record) -> dict | None:
    return dict(record) if record is not None else None


async def get_client_by_contract(pool: asyncpg.Pool, contract: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT c.*, t.speed_limit, t.price as tariff_price 
               FROM clients c LEFT JOIN tariffs t ON c.tariff_id = t.id 
               WHERE c.contract_number = $1""", contract
        )
        return _row(row)


async def get_client_by_address(pool: asyncpg.Pool, address: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT c.*, t.speed_limit, t.price as tariff_price 
               FROM clients c LEFT JOIN tariffs t ON c.tariff_id = t.id 
               WHERE c.address ILIKE $1 LIMIT 1""",
            f"%{address}%",
        )
        return _row(row)


async def get_client_by_id(pool: asyncpg.Pool, client_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT c.*, t.speed_limit, t.price as tariff_price 
               FROM clients c LEFT JOIN tariffs t ON c.tariff_id = t.id 
               WHERE c.id = $1""", client_id
        )
        return _row(row)


async def get_onu_data(pool: asyncpg.Pool, client_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM onu_simulation WHERE client_id = $1", client_id
        )
        return _row(row)


async def create_ticket(
        pool: asyncpg.Pool,
        client_id: int,
        issue_type: str,
        diag_summary: str,
        user_indication: int = 0
) -> int:
    async with pool.acquire() as conn:
        ticket_id = await conn.fetchval(
            "INSERT INTO tickets (client_id, issue_type, diag_summary, user_indication, status) "
            "VALUES ($1, $2, $3, $4, 'open') RETURNING id",
            client_id, issue_type, diag_summary, user_indication
        )
        return ticket_id


async def close_ticket(pool: asyncpg.Pool, client_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tickets SET status = 'closed' WHERE client_id = $1 AND status = 'open'",
            client_id,
        )


async def get_open_ticket(pool: asyncpg.Pool, client_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tickets WHERE client_id = $1 AND status = 'open' "
            "ORDER BY created_at DESC LIMIT 1", client_id
        )
        return _row(row)
