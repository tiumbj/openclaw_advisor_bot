from __future__ import annotations

import json
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..market_data.schemas import BarRecord, TickRecord
from ..market_data.timeframes import Timeframe
from .atomic import atomic_write

TICK_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.string()),
        pa.field("collector_version", pa.string()),
        pa.field("logical_symbol", pa.string()),
        pa.field("broker_symbol", pa.string()),
        pa.field("market_time_utc", pa.string()),
        pa.field("market_time_msc", pa.int64()),
        pa.field("received_at_utc", pa.string()),
        pa.field("bid", pa.float64()),
        pa.field("ask", pa.float64()),
        pa.field("last", pa.float64()),
        pa.field("volume", pa.float64()),
        pa.field("volume_real", pa.float64()),
        pa.field("flags", pa.int64()),
        pa.field("spread_points", pa.int64()),
        pa.field("sequence_id", pa.string()),
        pa.field("data_quality", pa.string()),
        pa.field("quality_flags", pa.list_(pa.string())),
    ]
)

BAR_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.string()),
        pa.field("collector_version", pa.string()),
        pa.field("logical_symbol", pa.string()),
        pa.field("broker_symbol", pa.string()),
        pa.field("timeframe", pa.string()),
        pa.field("open_time_utc", pa.string()),
        pa.field("close_time_utc", pa.string()),
        pa.field("open", pa.float64()),
        pa.field("high", pa.float64()),
        pa.field("low", pa.float64()),
        pa.field("close", pa.float64()),
        pa.field("tick_volume", pa.int64()),
        pa.field("real_volume", pa.int64()),
        pa.field("spread", pa.int64()),
        pa.field("is_closed", pa.bool_()),
        pa.field("bar_id", pa.string()),
        pa.field("data_quality", pa.string()),
        pa.field("quality_flags", pa.list_(pa.string())),
    ]
)


class ParquetStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def write_ticks(self, records: list[TickRecord], dry_run: bool = False) -> list[Path]:
        grouped: dict[tuple[str, str], list[TickRecord]] = defaultdict(list)
        for record in records:
            grouped[(record.logical_symbol, record.market_time_utc.date().isoformat())].append(
                record
            )
        written: list[Path] = []
        for (logical_symbol, partition_date), batch in grouped.items():
            rows = [record.to_dict() for record in batch]
            target_path = (
                self.root_dir
                / "ticks"
                / f"symbol={logical_symbol}"
                / f"date={partition_date}"
                / self._file_name(
                    "ticks",
                    logical_symbol,
                    None,
                    partition_date,
                    batch[0].sequence_id,
                    batch[-1].sequence_id,
                    len(batch),
                )
            )
            if not dry_run:
                self._write_table(target_path, rows, TICK_SCHEMA)
            written.append(target_path)
        return written

    def write_bars(self, records: list[BarRecord], dry_run: bool = False) -> list[Path]:
        grouped: dict[tuple[str, str, str], list[BarRecord]] = defaultdict(list)
        for record in records:
            grouped[
                (
                    record.logical_symbol,
                    record.timeframe,
                    record.open_time_utc.date().isoformat(),
                )
            ].append(record)
        written: list[Path] = []
        for (logical_symbol, timeframe, partition_date), batch in grouped.items():
            rows = [record.to_dict() for record in batch]
            target_path = (
                self.root_dir
                / "bars"
                / f"symbol={logical_symbol}"
                / f"timeframe={timeframe}"
                / f"date={partition_date}"
                / self._file_name(
                    "bars",
                    logical_symbol,
                    Timeframe(timeframe),
                    partition_date,
                    batch[0].bar_id,
                    batch[-1].bar_id,
                    len(batch),
                )
            )
            if not dry_run:
                self._write_table(target_path, rows, BAR_SCHEMA)
            written.append(target_path)
        return written

    def _write_table(
        self,
        target_path: Path,
        rows: list[dict[str, object]],
        schema: pa.Schema,
    ) -> None:
        table = pa.Table.from_pylist(rows, schema=schema)

        def _writer(temp_path: Path) -> None:
            pq.write_table(
                table,
                temp_path,
                compression="zstd",
                version="2.6",
            )
            validation_schema = pq.read_schema(temp_path)
            if not validation_schema.equals(schema, check_metadata=False):
                raise ValueError("Parquet schema mismatch after write")

        atomic_write(target_path, _writer)

    def _file_name(
        self,
        dataset_name: str,
        logical_symbol: str,
        timeframe: Timeframe | None,
        partition_date: str,
        first_id: str,
        last_id: str,
        count: int,
    ) -> str:
        timeframe_value = "tick" if timeframe is None else timeframe.value
        payload = json.dumps(
            [
                dataset_name,
                logical_symbol,
                timeframe_value,
                partition_date,
                first_id,
                last_id,
                count,
            ]
        )
        checksum = sha256(payload.encode("utf-8")).hexdigest()[:16]
        return (
            f"{dataset_name}-{logical_symbol}-{timeframe_value}-"
            f"{partition_date}-{count}-{checksum}.parquet"
        )
