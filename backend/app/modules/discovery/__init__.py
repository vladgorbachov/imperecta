"""Discovery module: marketplace URL discovery and gated pool persistence."""

from app.modules.discovery.gate_persist import (
    PoolInsertDTO,
    PoolWriteResult,
    write_pool_dtos_sync,
)

__all__ = [
    "PoolInsertDTO",
    "PoolWriteResult",
    "write_pool_dtos_sync",
]
