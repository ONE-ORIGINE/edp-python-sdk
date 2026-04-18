from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .core import CausalMemory
from .operational import SemanticRelationalGraph


@dataclass
class GraphSnapshot:
    graph: Dict[str, Any]
    relation_counts: Dict[str, int] = field(default_factory=dict)
    node_count: int = 0
    edge_count: int = 0
    exported_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "graph": self.graph,
            "relation_counts": self.relation_counts,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "exported_at": self.exported_at,
        }, ensure_ascii=False, indent=2)


class JsonGraphStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path = self.path.with_suffix(self.path.suffix + ".index.json")

    def save(self, graph: SemanticRelationalGraph) -> Path:
        exported = graph.export()
        snapshot = GraphSnapshot(
            graph=exported,
            relation_counts=graph.relation_counts(),
            node_count=len(exported.get("nodes", {})),
            edge_count=len(exported.get("edges", [])),
        )
        self.path.write_text(snapshot.to_json(), encoding="utf-8")
        adjacency: Dict[str, List[str]] = {}
        for edge in exported.get("edges", []):
            adjacency.setdefault(edge.get("source_id", ""), []).append(edge.get("target_id", ""))
        self.index_path.write_text(json.dumps({
            "node_ids": sorted(exported.get("nodes", {}).keys()),
            "relations": snapshot.relation_counts,
            "adjacency": adjacency,
            "exported_at": snapshot.exported_at,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"graph": {"nodes": {}, "edges": []}, "exported_at": 0.0}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def load_index(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {"node_ids": [], "relations": {}, "exported_at": 0.0}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def merge_into(self, graph: SemanticRelationalGraph) -> Dict[str, int]:
        payload = self.load()
        return graph.merge_export(payload.get("graph", {}))


class JsonEventStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path = self.path.with_suffix(self.path.suffix + ".summary.json")
        self.journal_path = self.path.with_suffix(self.path.suffix + ".journal.json")

    def save_memory(self, memory: CausalMemory) -> Path:
        payload = memory.to_dict()
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.summary_path.write_text(json.dumps(memory.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.journal_path.write_text(json.dumps(memory.event_journal(), ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path

    def load_memory(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"events": [], "reactions": [], "interactions": [], "phenomena": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def load_summary(self) -> Dict[str, Any]:
        if not self.summary_path.exists():
            return {}
        return json.loads(self.summary_path.read_text(encoding="utf-8"))

    def load_journal(self) -> List[Dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        return json.loads(self.journal_path.read_text(encoding="utf-8"))

    def merge_into(self, memory: CausalMemory) -> Dict[str, int]:
        other = CausalMemory.from_dict(self.load_memory())
        return memory.merge(other)


# SQLite backends -------------------------------------------------------------

import sqlite3


class SQLiteGraphStore:
    """Persistent graph backend with simple relation / neighbor queries."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("create table if not exists nodes (node_id text primary key, kind text, payload text)")
            con.execute("create table if not exists edges (edge_id integer primary key autoincrement, source_id text, target_id text, relation text, payload text)")
            con.execute("create index if not exists idx_edges_relation on edges(relation)")
            con.execute("create index if not exists idx_edges_source on edges(source_id)")
            con.execute("create index if not exists idx_edges_target on edges(target_id)")
            con.commit()

    def save(self, graph: SemanticRelationalGraph) -> Path:
        exported = graph.export()
        with self._connect() as con:
            con.execute("delete from nodes")
            con.execute("delete from edges")
            for node_id, node in exported.get("nodes", {}).items():
                con.execute("insert into nodes(node_id, kind, payload) values(?,?,?)", (node_id, node.get("kind", ""), json.dumps(node, ensure_ascii=False)))
            for edge in exported.get("edges", []):
                con.execute("insert into edges(source_id, target_id, relation, payload) values(?,?,?,?)", (
                    edge.get("source_id", ""), edge.get("target_id", ""), edge.get("relation", ""), json.dumps(edge, ensure_ascii=False)
                ))
            con.commit()
        return self.path

    def export(self) -> Dict[str, Any]:
        with self._connect() as con:
            nodes = {row[0]: json.loads(row[2]) for row in con.execute("select node_id, kind, payload from nodes")}
            edges = [json.loads(row[0]) for row in con.execute("select payload from edges order by edge_id")]
        return {"nodes": nodes, "edges": edges}

    def query_relation(self, relation: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from edges where relation=? order by edge_id", (relation,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def neighbors(self, node_id: str) -> List[str]:
        with self._connect() as con:
            rows = con.execute("select target_id from edges where source_id=? union select source_id from edges where target_id=?", (node_id, node_id)).fetchall()
        return [r[0] for r in rows]

    def merge_into(self, graph: SemanticRelationalGraph) -> Dict[str, int]:
        return graph.merge_export(self.export())


class SQLiteEventStore:
    """Persistent causal memory backend with simple query helpers."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("create table if not exists events (sequence_number integer primary key, correlation_id text, actor_id text, context_name text, action_type text, payload text)")
            con.execute("create index if not exists idx_events_corr on events(correlation_id)")
            con.execute("create index if not exists idx_events_actor on events(actor_id)")
            con.execute("create index if not exists idx_events_ctx on events(context_name)")
            con.execute("create table if not exists reactions (reaction_id text primary key, correlation_id text, status text, payload text)")
            con.execute("create index if not exists idx_reactions_corr on reactions(correlation_id)")
            con.execute("create table if not exists interactions (id integer primary key autoincrement, category text, correlation_id text, payload text)")
            con.execute("create table if not exists phenomena (id integer primary key autoincrement, category text, correlation_id text, context_name text, payload text)")
            con.commit()

    def save_memory(self, memory: CausalMemory) -> Path:
        payload = memory.to_dict()
        with self._connect() as con:
            for table in ("events", "reactions", "interactions", "phenomena"):
                con.execute(f"delete from {table}")
            for e in payload.get("events", []):
                con.execute("insert into events(sequence_number, correlation_id, actor_id, context_name, action_type, payload) values(?,?,?,?,?,?)", (
                    int(e.get("sequence_number", 0)), e.get("correlation_id", ""), e.get("actor_id", ""), e.get("context_name", ""), e.get("action_type", ""), json.dumps(e, ensure_ascii=False)
                ))
            # reactions need correlation ids from events
            corr_by_reaction = {e.get("reaction_id"): e.get("correlation_id", "") for e in payload.get("events", [])}
            for r in payload.get("reactions", []):
                con.execute("insert into reactions(reaction_id, correlation_id, status, payload) values(?,?,?,?)", (
                    r.get("reaction_id", ""), corr_by_reaction.get(r.get("reaction_id"), ""), r.get("status", ""), json.dumps(r, ensure_ascii=False)
                ))
            for i in payload.get("interactions", []):
                con.execute("insert into interactions(category, correlation_id, payload) values(?,?,?)", (i.get("category", ""), i.get("correlation_id", ""), json.dumps(i, ensure_ascii=False)))
            for p in payload.get("phenomena", []):
                con.execute("insert into phenomena(category, correlation_id, context_name, payload) values(?,?,?,?)", (p.get("category", ""), p.get("correlation_id", ""), p.get("context_name", ""), json.dumps(p, ensure_ascii=False)))
            con.commit()
        return self.path

    def load_memory(self) -> Dict[str, Any]:
        with self._connect() as con:
            events = [json.loads(r[0]) for r in con.execute("select payload from events order by sequence_number")]
            reactions = [json.loads(r[0]) for r in con.execute("select payload from reactions order by rowid")]
            interactions = [json.loads(r[0]) for r in con.execute("select payload from interactions order by id")]
            phenomena = [json.loads(r[0]) for r in con.execute("select payload from phenomena order by id")]
        return {"events": events, "reactions": reactions, "interactions": interactions, "phenomena": phenomena}

    def by_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from events where correlation_id=? order by sequence_number", (correlation_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def by_actor(self, actor_id: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from events where actor_id=? order by sequence_number", (actor_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def by_context(self, context_name: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from events where context_name=? order by sequence_number", (context_name,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def merge_into(self, memory: CausalMemory) -> Dict[str, int]:
        other = CausalMemory.from_dict(self.load_memory())
        return memory.merge(other)


class SQLiteRuntimeStore:
    """Persistent store for runtime state snapshots, locks and executions."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("create table if not exists runtime_snapshots (id integer primary key autoincrement, runtime_id text, emitted_at real, payload text)")
            con.execute("create table if not exists runtime_locks (resource text primary key, owner text, expires_at real, payload text)")
            con.execute("create table if not exists runtime_executions (execution_id text primary key, state text, updated_at real, payload text)")
            con.execute("create table if not exists runtime_peers (peer_name text primary key, payload text)")
            con.commit()

    def save_runtime_state(self, state: Dict[str, Any]) -> Path:
        runtime_id = str(state.get('runtime_id') or state.get('environment_id') or 'runtime')
        emitted_at = float(state.get('emitted_at', time.time()))
        with self._connect() as con:
            con.execute("insert into runtime_snapshots(runtime_id, emitted_at, payload) values(?,?,?)", (runtime_id, emitted_at, json.dumps(state, ensure_ascii=False)))
            for lock in state.get('locks', []) or []:
                con.execute("insert or replace into runtime_locks(resource, owner, expires_at, payload) values(?,?,?,?)", (lock.get('resource',''), lock.get('owner',''), float(lock.get('expires_at',0.0)), json.dumps(lock, ensure_ascii=False)))
            for ex in state.get('executions', []) or []:
                exid = str(ex.get('execution_id') or ex.get('packet_id') or ex.get('name') or '')
                if exid:
                    con.execute("insert or replace into runtime_executions(execution_id, state, updated_at, payload) values(?,?,?,?)", (exid, str(ex.get('state','')), float(ex.get('completed_at', ex.get('started_at', emitted_at))), json.dumps(ex, ensure_ascii=False)))
            for peer_name, peer in (state.get('peers') or {}).items():
                con.execute("insert or replace into runtime_peers(peer_name, payload) values(?,?)", (peer_name, json.dumps(peer, ensure_ascii=False)))
            con.commit()
        return self.path

    def latest_runtime_state(self) -> Dict[str, Any]:
        with self._connect() as con:
            row = con.execute("select payload from runtime_snapshots order by id desc limit 1").fetchone()
        return json.loads(row[0]) if row else {}

    def list_locks(self) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from runtime_locks order by resource").fetchall()
        return [json.loads(r[0]) for r in rows]

    def list_executions(self) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from runtime_executions order by updated_at desc").fetchall()
        return [json.loads(r[0]) for r in rows]

    def list_peers(self) -> Dict[str, Any]:
        with self._connect() as con:
            rows = con.execute("select peer_name, payload from runtime_peers order by peer_name").fetchall()
        return {name: json.loads(payload) for name, payload in rows}



# Generation 2 iteration 10 — native specialized stores ----------------------
from typing import Optional

from .analytics import ImpactMatrix, ImpactRecord


class SQLiteContextMatrixStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("create table if not exists context_snapshots (id integer primary key autoincrement, captured_at real, payload text)")
            con.execute("create table if not exists context_rows (snapshot_id integer, context_kind text, dim_name text, weight real)")
            con.execute("create index if not exists idx_context_rows_kind on context_rows(context_kind)")
            con.commit()

    def save_contextualizer(self, contextualizer: Any) -> Path:
        exported = contextualizer.context_matrix_export() if hasattr(contextualizer, 'context_matrix_export') else {}
        rows = exported.get('rows', [])
        cols = exported.get('cols', [])
        matrix = exported.get('matrix', [])
        with self._connect() as con:
            con.execute("insert into context_snapshots(captured_at, payload) values(?,?)", (time.time(), json.dumps(exported, ensure_ascii=False)))
            snapshot_id = int(con.execute("select last_insert_rowid()").fetchone()[0])
            for row_name, values in zip(rows, matrix):
                for dim_name, value in zip(cols, values):
                    con.execute("insert into context_rows(snapshot_id, context_kind, dim_name, weight) values(?,?,?,?)", (snapshot_id, row_name, dim_name, float(value)))
            con.commit()
        return self.path

    def latest_snapshot(self) -> Dict[str, Any]:
        with self._connect() as con:
            row = con.execute("select payload from context_snapshots order by id desc limit 1").fetchone()
        return json.loads(row[0]) if row else {}

    def weights_for(self, context_kind: str) -> List[float]:
        latest = self.latest_snapshot()
        rows = latest.get('rows', [])
        matrix = latest.get('matrix', [])
        if context_kind in rows:
            return list(matrix[rows.index(context_kind)])
        return []

    def describe(self) -> Dict[str, Any]:
        latest = self.latest_snapshot()
        return {
            'path': str(self.path),
            'row_count': len(latest.get('rows', [])),
            'dim_count': len(latest.get('cols', [])),
        }


class SQLiteLearningStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("create table if not exists impact_records (id integer primary key autoincrement, correlation_id text, action_type text, reaction_type text, context_name text, status text, impact_score real, chain_depth integer, causal_delta real, timestamp real, components text)")
            con.execute("create index if not exists idx_learning_action on impact_records(action_type)")
            con.execute("create index if not exists idx_learning_context on impact_records(context_name)")
            con.execute("create table if not exists learning_snapshots (id integer primary key autoincrement, captured_at real, payload text)")
            con.commit()

    def append_record(self, record: ImpactRecord) -> Path:
        with self._connect() as con:
            con.execute(
                "insert into impact_records(correlation_id, action_type, reaction_type, context_name, status, impact_score, chain_depth, causal_delta, timestamp, components) values(?,?,?,?,?,?,?,?,?,?)",
                (record.correlation_id, record.action_type, record.reaction_type, record.context_name, record.status, float(record.impact_score), int(record.chain_depth), None if record.causal_delta is None else float(record.causal_delta), float(record.timestamp), json.dumps(record.components, ensure_ascii=False)),
            )
            con.commit()
        return self.path

    def save_impact_matrix(self, impact: ImpactMatrix) -> Path:
        with self._connect() as con:
            con.execute("delete from impact_records")
            for record in impact.records:
                con.execute(
                    "insert into impact_records(correlation_id, action_type, reaction_type, context_name, status, impact_score, chain_depth, causal_delta, timestamp, components) values(?,?,?,?,?,?,?,?,?,?)",
                    (record.correlation_id, record.action_type, record.reaction_type, record.context_name, record.status, float(record.impact_score), int(record.chain_depth), None if record.causal_delta is None else float(record.causal_delta), float(record.timestamp), json.dumps(record.components, ensure_ascii=False)),
                )
            projection = impact.learning_projection().to_dict()
            con.execute("insert into learning_snapshots(captured_at, payload) values(?,?)", (time.time(), json.dumps(projection, ensure_ascii=False)))
            con.commit()
        return self.path

    def load_records(self) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select correlation_id, action_type, reaction_type, context_name, status, impact_score, chain_depth, causal_delta, timestamp, components from impact_records order by id").fetchall()
        out = []
        for row in rows:
            out.append({
                'correlation_id': row[0], 'action_type': row[1], 'reaction_type': row[2], 'context_name': row[3], 'status': row[4], 'impact_score': row[5], 'chain_depth': row[6], 'causal_delta': row[7], 'timestamp': row[8], 'components': json.loads(row[9] or '{}'),
            })
        return out

    def latest_projection(self) -> Dict[str, Any]:
        with self._connect() as con:
            row = con.execute("select payload from learning_snapshots order by id desc limit 1").fetchone()
        return json.loads(row[0]) if row else {}

    def action_history(self, action_type: str) -> List[Dict[str, Any]]:
        return [row for row in self.load_records() if row.get('action_type') == action_type]

    def context_history(self, context_name: str) -> List[Dict[str, Any]]:
        return [row for row in self.load_records() if row.get('context_name') == context_name]

    def backend_state(self) -> Dict[str, Any]:
        records = self.load_records()
        return {
            'path': str(self.path),
            'record_count': len(records),
            'actions': sorted({row['action_type'] for row in records}),
            'contexts': sorted({row['context_name'] for row in records}),
            'latest_projection': self.latest_projection(),
        }

    def merge_into(self, impact: ImpactMatrix) -> Dict[str, int]:
        before = len(impact.records)
        impact.extend(ImpactRecord.from_dict(row) for row in self.load_records())
        return {'records_before': before, 'records_after': len(impact.records)}


class SQLiteCausalDatasetStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("create table if not exists dataset_snapshots (id integer primary key autoincrement, environment_id text, captured_at real, payload text)")
            con.execute("create table if not exists dataset_events (id integer primary key autoincrement, action_type text, correlation_id text, context_name text, payload text)")
            con.execute("create index if not exists idx_dataset_events_action on dataset_events(action_type)")
            con.execute("create index if not exists idx_dataset_events_corr on dataset_events(correlation_id)")
            con.execute("create table if not exists dataset_phenomena (id integer primary key autoincrement, category text, correlation_id text, context_name text, payload text)")
            con.execute("create index if not exists idx_dataset_phenomena_cat on dataset_phenomena(category)")
            con.commit()

    def save_dataset(self, dataset: Dict[str, Any], *, environment_id: str = 'environment') -> Path:
        with self._connect() as con:
            con.execute("delete from dataset_events")
            con.execute("delete from dataset_phenomena")
            con.execute("insert into dataset_snapshots(environment_id, captured_at, payload) values(?,?,?)", (environment_id, time.time(), json.dumps(dataset, ensure_ascii=False)))
            for event in dataset.get('events', []):
                con.execute("insert into dataset_events(action_type, correlation_id, context_name, payload) values(?,?,?,?)", (event.get('action_type',''), event.get('correlation_id',''), event.get('context_name',''), json.dumps(event, ensure_ascii=False)))
            for ph in dataset.get('phenomena', []):
                con.execute("insert into dataset_phenomena(category, correlation_id, context_name, payload) values(?,?,?,?)", (ph.get('category',''), ph.get('correlation_id',''), ph.get('context_name',''), json.dumps(ph, ensure_ascii=False)))
            con.commit()
        return self.path

    def save_environment(self, environment: Any) -> Path:
        from .canonical import EnvironmentCanonicalBody
        body = EnvironmentCanonicalBody.from_environment(environment)
        return self.save_dataset(body.causal_dataset_projection(), environment_id=getattr(environment, 'environment_id', 'environment'))

    def latest_dataset(self) -> Dict[str, Any]:
        with self._connect() as con:
            row = con.execute("select payload from dataset_snapshots order by id desc limit 1").fetchone()
        return json.loads(row[0]) if row else {}

    def by_action(self, action_type: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from dataset_events where action_type=? order by id", (action_type,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def by_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from dataset_events where correlation_id=? order by id", (correlation_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def phenomena_by_category(self, category: str) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("select payload from dataset_phenomena where category=? order by id", (category,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def describe(self) -> Dict[str, Any]:
        latest = self.latest_dataset()
        return {
            'path': str(self.path),
            'event_count': len(latest.get('events', [])),
            'phenomenon_count': len(latest.get('phenomena', [])),
        }


class NativeSpecializedStoreSuite:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.events = SQLiteEventStore(self.base_dir / 'events.sqlite')
        self.graph = SQLiteGraphStore(self.base_dir / 'graph.sqlite')
        self.runtime = SQLiteRuntimeStore(self.base_dir / 'runtime.sqlite')
        self.context = SQLiteContextMatrixStore(self.base_dir / 'context.sqlite')
        self.learning = SQLiteLearningStore(self.base_dir / 'learning.sqlite')
        self.dataset = SQLiteCausalDatasetStore(self.base_dir / 'causal_dataset.sqlite')

    def save_environment(self, environment: Any, runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.events.save_memory(environment.memory)
        self.graph.save(environment.semantic_graph)
        self.context.save_contextualizer(environment.contextualizer)
        self.learning.save_impact_matrix(environment.impact)
        self.dataset.save_environment(environment)
        if runtime_state:
            self.runtime.save_runtime_state(runtime_state)
        return self.summary()

    def merge_into(self, environment: Any) -> Dict[str, Any]:
        return {
            'memory_merge': self.events.merge_into(environment.memory),
            'graph_merge': self.graph.merge_into(environment.semantic_graph),
            'learning_merge': self.learning.merge_into(environment.impact),
        }

    def summary(self) -> Dict[str, Any]:
        return {
            'base_dir': str(self.base_dir),
            'events': {'path': str(self.events.path)},
            'graph': {'path': str(self.graph.path)},
            'runtime': {'path': str(self.runtime.path), 'snapshots': len(self.runtime.list_executions())},
            'context': self.context.describe(),
            'learning': self.learning.backend_state(),
            'dataset': self.dataset.describe(),
        }

__all__ = [name for name in globals() if not name.startswith('_')]
