"""Tests for Emblem AI."""

import pytest
import time

from config.agent_config import AgentConfig, LLMConfig, EmblemConfig, MemoryConfig
from config.persona import Persona, PersonaTrait, ADAM_PERSONA
from skills.crypto.wallet import Chain, TokenBalance, WalletSummary
from skills.crypto.trading import TradeRequest, TradeResult, TradingEngine, TradeDirection, OrderType, OrderStatus
from skills.crypto.bridge import BridgeEngine, BridgeRequest
from skills.portfolio.tracker import PortfolioTracker, PortfolioSnapshot, PortfolioAlert
from skills.research.market import TokenInfo, MarketOverview, ResearchEngine
from skills.assistant.tasks import TaskManager, Task, TaskPriority, TaskStatus, Note
from skills.scheduling.scheduler import Scheduler, ScheduledJob
from memory.store import MemoryStore, MemoryEntry, MemoryType
from gateway.adapters import IncomingMessage, OutgoingMessage, Platform
from tools.llm_client import LLMClient, LLMResponse


class TestConfig:
    def test_load(self):
        config = AgentConfig()
        assert config.name == "Emblem AI"
        assert config.owner == "Adam McBride"

    def test_validate_warns(self):
        config = AgentConfig()
        warnings = config.validate()
        assert len(warnings) > 0  # No API keys set.

    def test_to_dict(self):
        config = AgentConfig()
        d = config.to_dict()
        assert "name" in d
        assert "supported_chains" in d


class TestPersona:
    def test_default_persona(self):
        p = ADAM_PERSONA
        assert p.name == "Emblem AI"
        assert p.owner == "Adam McBride"
        assert len(p.traits) > 0

    def test_build_system_prompt(self):
        prompt = ADAM_PERSONA.build_system_prompt()
        assert "Adam McBride" in prompt
        assert "Emblem Vault" in prompt
        assert "Emblem AI" in prompt

    def test_trait_prompt(self):
        trait = PersonaTrait("direct", "gives short answers", 0.9)
        frag = trait.to_prompt_fragment()
        assert "strongly" in frag
        assert "direct" in frag


class TestChain:
    def test_from_name(self):
        assert Chain.from_name("solana") == Chain.SOLANA
        assert Chain.from_name("SOL") == Chain.SOLANA
        assert Chain.from_name("eth") == Chain.ETHEREUM
        assert Chain.from_name("btc") == Chain.BITCOIN

    def test_unknown_chain(self):
        with pytest.raises(ValueError):
            Chain.from_name("fake_chain")


class TestTokenBalance:
    def test_format(self):
        bal = TokenBalance(symbol="SOL", name="Solana", balance=12.5, usd_value=2500.0, chain=Chain.SOLANA, price_usd=200.0)
        assert bal.is_native
        assert "$" in bal.format_usd()
        assert "12.5" in bal.format_balance()

    def test_large_balance(self):
        bal = TokenBalance(symbol="BONK", name="Bonk", balance=5_000_000, usd_value=50.0, chain=Chain.SOLANA)
        assert "M" in bal.format_balance()


class TestWalletSummary:
    def test_top_holdings(self):
        summary = WalletSummary(
            balances=[
                TokenBalance("SOL", "Solana", 10, 2000, Chain.SOLANA),
                TokenBalance("ETH", "Ethereum", 1, 3000, Chain.ETHEREUM),
                TokenBalance("BONK", "Bonk", 1000000, 5, Chain.SOLANA),
            ],
            total_usd=5005,
            chain_breakdown={"solana": 2005, "ethereum": 3000},
        )
        top = summary.top_holdings(2)
        assert len(top) == 2
        assert top[0].symbol == "ETH"  # Highest value first.


class TestTrading:
    def test_trade_request(self):
        req = TradeRequest(
            direction=TradeDirection.SWAP,
            from_token="SOL",
            to_token="USDC",
            amount=1.0,
            chain=Chain.SOLANA,
        )
        assert "SOL" in req.describe()
        assert "USDC" in req.describe()

    def test_validation(self):
        engine = TradingEngine()
        req = TradeRequest(
            direction=TradeDirection.SWAP,
            from_token="SOL",
            to_token="SOL",
            amount=1.0,
            chain=Chain.SOLANA,
        )
        # Can't swap same token.
        result = engine._validate_trade(req)
        assert result is not None

    def test_zero_amount(self):
        engine = TradingEngine()
        req = TradeRequest(
            direction=TradeDirection.BUY,
            from_token="USDC",
            to_token="SOL",
            amount=0,
            chain=Chain.SOLANA,
        )
        result = engine._validate_trade(req)
        assert result is not None


class TestBridge:
    def test_supported_route(self):
        engine = BridgeEngine()
        assert engine.is_route_supported(Chain.SOLANA, Chain.ETHEREUM, "USDC")
        assert not engine.is_route_supported(Chain.SOLANA, Chain.BITCOIN, "USDC")

    def test_supported_tokens(self):
        engine = BridgeEngine()
        tokens = engine.get_supported_tokens(Chain.SOLANA, Chain.ETHEREUM)
        assert "USDC" in tokens


class TestPortfolio:
    def test_record_snapshot(self):
        tracker = PortfolioTracker()
        summary = WalletSummary(
            balances=[TokenBalance("SOL", "Solana", 10, 2000, Chain.SOLANA)],
            total_usd=2000,
            chain_breakdown={"solana": 2000},
        )
        alerts = tracker.record_snapshot(summary)
        assert isinstance(alerts, list)

    def test_performance_not_enough_data(self):
        tracker = PortfolioTracker()
        perf = tracker.get_performance()
        assert "error" in perf

    def test_allocation_drift(self):
        tracker = PortfolioTracker()
        tracker.set_target_allocation({"solana": 60, "ethereum": 40})
        summary = WalletSummary(
            total_usd=10000,
            chain_breakdown={"solana": 8000, "ethereum": 2000},
        )
        tracker.record_snapshot(summary)
        drift = tracker.get_allocation_drift()
        assert "solana" in drift
        assert drift["solana"]["drift_pct"] > 0


class TestTasks:
    def test_add_and_complete(self):
        mgr = TaskManager()
        task = mgr.add_task("Test task", priority="high")
        assert task.status == TaskStatus.OPEN
        result = mgr.complete_task(task.id)
        assert result is not None
        assert result.status == TaskStatus.DONE

    def test_overdue(self):
        mgr = TaskManager()
        task = mgr.add_task("Old task", due_at=time.time() - 3600)
        overdue = mgr.get_overdue_tasks()
        assert len(overdue) == 1

    def test_notes(self):
        mgr = TaskManager()
        note = mgr.add_note("Remember this", tags=["crypto"])
        results = mgr.search_notes("remember")
        assert len(results) == 1

    def test_briefing(self):
        mgr = TaskManager()
        mgr.add_task("Urgent thing", priority="urgent")
        briefing = mgr.format_daily_briefing()
        assert "Urgent" in briefing


class TestScheduler:
    def test_default_jobs(self):
        sched = Scheduler()
        jobs = sched.get_jobs()
        assert len(jobs) >= 4  # At least the default jobs.

    def test_add_remove(self):
        sched = Scheduler()
        job = sched.add_job("test", "0 * * * *", "test job", "test_handler")
        assert sched.remove_job(job.id)

    def test_enable_disable(self):
        sched = Scheduler()
        jobs = sched.get_jobs()
        job_id = jobs[0].id
        sched.disable_job(job_id)
        assert not next(j for j in sched.get_jobs() if j.id == job_id).enabled
        sched.enable_job(job_id)
        assert next(j for j in sched.get_jobs() if j.id == job_id).enabled


class TestMemoryStore:
    def test_store_and_search(self, tmp_path):
        store = MemoryStore(str(tmp_path / "test.db"))
        entry = MemoryEntry(
            content="Adam prefers Solana for trading",
            memory_type=MemoryType.PREFERENCE,
            tags=["solana", "preference"],
        )
        store.store(entry)
        results = store.search("solana trading")
        assert len(results) > 0
        store.close()

    def test_recent(self, tmp_path):
        store = MemoryStore(str(tmp_path / "test.db"))
        store.store(MemoryEntry(content="first", memory_type=MemoryType.EPISODIC))
        store.store(MemoryEntry(content="second", memory_type=MemoryType.EPISODIC))
        recent = store.recent(limit=1)
        assert len(recent) == 1
        assert recent[0].content == "second"
        store.close()

    def test_conversation(self, tmp_path):
        store = MemoryStore(str(tmp_path / "test.db"))
        store.store_conversation("sess1", "user", "hello")
        store.store_conversation("sess1", "assistant", "hi there")
        conv = store.get_conversation("sess1")
        assert len(conv) == 2
        store.close()

    def test_stats(self, tmp_path):
        store = MemoryStore(str(tmp_path / "test.db"))
        store.store(MemoryEntry(content="test", memory_type=MemoryType.FACT))
        stats = store.stats()
        assert stats["total_memories"] == 1
        store.close()

    def test_decay(self, tmp_path):
        store = MemoryStore(str(tmp_path / "test.db"))
        store.store(MemoryEntry(content="fading", memory_type=MemoryType.EPISODIC, salience=0.01))
        removed = store.apply_decay(rate=0.02)
        assert removed >= 0
        store.close()


class TestGateway:
    def test_incoming_message(self):
        msg = IncomingMessage(text="hello", platform=Platform.CLI, user_id="1", user_name="Adam")
        assert msg.text == "hello"
        d = msg.to_dict()
        assert d["platform"] == "cli"

    def test_outgoing_truncate(self):
        msg = OutgoingMessage(text="x" * 5000, platform=Platform.TELEGRAM)
        truncated = msg.truncate(100)
        assert len(truncated.text) <= 100


class TestLLMResponse:
    def test_to_dict(self):
        resp = LLMResponse(text="hello world", model="test", tokens_used=10)
        d = resp.to_dict()
        assert d["model"] == "test"
        assert d["tokens_used"] == 10
