'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { hasSupabase, supabase } from '../lib/supabase';

type Category = 'US' | 'KR' | 'COIN' | 'FUTURES';
type MainTab = 'PICKS' | 'SEARCH' | 'DETAIL' | 'PAPER' | 'HISTORY';
type PaperStatus = 'PENDING' | 'FILLED' | 'CLOSED' | 'CANCELED';

type Stock = {
  symbol: string;
  name: string;
  market: string;
  score: number;
  grade?: string;
  price: number;
  entry_price: number;
  stop_price: number;
  target_price: number;
  reason?: string;
  beginner_note?: string;
  change_text?: string;
  decision?: string;
  risk_level?: string;
  action_text?: string;
  trend_score?: number;
  volume_score?: number;
  news_score?: number;
  earnings_score?: number;
  flow_score?: number;
  risk_score?: number;
  timing_score?: number;
  win_rate?: number;
  expected_return?: number;
  loss_risk?: number;
  final_score?: number;
  confidence_grade?: string;
  asset_class?: string;
  trade_type?: string;
  side?: string;
};

type PaperTrade = {
  id: string;
  user_id?: string;
  symbol: string;
  name: string;
  market: string;
  category: Category;
  side: string;
  status: PaperStatus;
  requestedPrice: number;
  fillPrice?: number;
  closePrice?: number;
  qty: number;
  pnlPct?: number;
  pnlMoney?: number;
  createdAt: string;
  filledAt?: string;
  closedAt?: string;
};

type LeaderboardRow = {
  user_id?: string;
  display_name?: string;
  email?: string;
  total_trades?: number;
  wins?: number;
  losses?: number;
  win_rate?: number;
  avg_pnl_pct?: number;
  total_pnl?: number;
};

const demo: Stock[] = [
  {
    symbol: 'NVDA', name: '엔비디아', market: 'US', score: 92, grade: 'S', price: 135.68,
    entry_price: 128.9, stop_price: 119.8, target_price: 152.5, reason: '데모 데이터 · AI 수익률 우선 랭킹',
    beginner_note: '데모 모드입니다.', change_text: '+2.35%', decision: '관찰 매수', risk_level: '보통', action_text: '1차 진입가 부근 대기',
    timing_score: 16, trend_score: 18, volume_score: 13, news_score: 8, earnings_score: 9, flow_score: 8, risk_score: 7,
    win_rate: 72, expected_return: 12.3, loss_risk: 28, final_score: 88, asset_class: 'STOCK', trade_type: 'SWING', side: 'LONG', confidence_grade: 'A',
  },
];

const CATS: { id: Category; label: string }[] = [
  { id: 'US', label: '🇺🇸 미국 TOP10' },
  { id: 'KR', label: '🇰🇷 한국 TOP10' },
  { id: 'COIN', label: '₿ 코인 TOP10' },
  { id: 'FUTURES', label: '⚡ 선물 TOP10' },
];

function num(v: any, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function normalizePercent(v?: number) {
  const n = num(v, 0);
  if (n > 0 && n <= 1) return n * 100;
  return n;
}

function parsePct(text?: string) {
  if (!text) return 0;
  const n = Number(String(text).replace('%', '').replace('+', '').replace(',', '.').trim());
  return Number.isFinite(n) ? n : 0;
}

function getCategory(s: Stock): Category {
  const market = String(s.market || '').toUpperCase();
  const asset = String(s.asset_class || '').toUpperCase();
  const trade = String(s.trade_type || '').toUpperCase();
  const side = String(s.side || '').toUpperCase();
  if (asset.includes('FUT') || trade.includes('FUT') || trade.includes('PERP')) return 'FUTURES';
  if ((side === 'SHORT' || side === 'LONG') && !['US', 'KR'].includes(market) && (trade.includes('LONG') || trade.includes('SHORT'))) return 'FUTURES';
  if (asset.includes('COIN') || asset.includes('CRYPTO') || market.includes('COIN') || market.includes('CRYPTO')) return 'COIN';
  if (market === 'KR') return 'KR';
  return 'US';
}

function categoryName(c: Category) {
  if (c === 'US') return '미국';
  if (c === 'KR') return '한국';
  if (c === 'COIN') return '코인';
  return '선물';
}

function marketBadge(c: Category) {
  if (c === 'US') return 'US';
  if (c === 'KR') return 'KR';
  if (c === 'COIN') return 'COIN';
  return 'FUT';
}

function maxPositions(c: Category) {
  if (c === 'US' || c === 'KR') return 7;
  if (c === 'COIN') return 5;
  return 3;
}

function sideLabel(s: Stock) {
  const c = getCategory(s);
  const side = String(s.side || 'LONG').toUpperCase();
  if (c === 'FUTURES') return side === 'SHORT' ? 'SHORT' : 'LONG';
  if (c === 'COIN') return 'SPOT';
  return 'SWING';
}

function profitScore(s: Stock) {
  const finalScore = num(s.final_score, 0);
  if (finalScore > 0) return finalScore;
  const win = normalizePercent(s.win_rate);
  const exp = normalizePercent(s.expected_return);
  const risk = normalizePercent(s.loss_risk);
  const timing = num(s.timing_score, 0);
  return clamp(num(s.score) * 0.45 + win * 0.3 + exp * 0.8 + timing * 0.35 - risk * 0.18, 0, 100);
}

function derivedWinRate(s: Stock) {
  const direct = normalizePercent(s.win_rate);
  if (direct > 0) return clamp(direct, 35, 95);
  const timing = num(s.timing_score, 0);
  const dayMove = parsePct(s.change_text);
  const risk = String(s.risk_level || '').includes('높') ? 8 : 0;
  return clamp(42 + num(s.score) * 0.25 + timing * 0.35 - Math.max(dayMove - 5, 0) * 1.5 - risk, 35, 88);
}

function derivedExpectedReturn(s: Stock) {
  const direct = normalizePercent(s.expected_return);
  if (direct !== 0) return direct;
  const entry = num(s.entry_price, s.price);
  const target = num(s.target_price, entry);
  return entry > 0 ? ((target - entry) / entry) * 100 : 0;
}

function derivedLossRisk(s: Stock) {
  const direct = normalizePercent(s.loss_risk);
  if (direct > 0) return clamp(direct, 0, 100);
  const entry = num(s.entry_price, s.price);
  const stop = num(s.stop_price, entry * 0.9);
  const lossPct = entry > 0 ? Math.max(0, ((entry - stop) / entry) * 100) : 0;
  return clamp(lossPct * 3.2 + Math.max(parsePct(s.change_text) - 6, 0) * 4, 0, 100);
}

function money(n: number, market: string) {
  if (!Number.isFinite(n) || n <= 0) return '-';
  const m = String(market || '').toUpperCase();
  if (m === 'KR') return `${Math.round(n).toLocaleString()}원`;
  if (n >= 1000) return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 4 })}`;
}

function pct(n: number) {
  if (!Number.isFinite(n)) return '-';
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

function getEntryGuide(s: Stock, baseEntry?: number) {
  const cat = getCategory(s);
  const side = String(s.side || 'LONG').toUpperCase();
  const isShort = cat === 'FUTURES' && side === 'SHORT';
  const entry1 = num(baseEntry, num(s.entry_price, s.price));
  let entry2 = entry1 * 0.965;
  let entry3 = entry1 * 0.93;
  if (cat === 'KR' || cat === 'COIN') {
    entry2 = entry1 * 0.97;
    entry3 = entry1 * 0.94;
  }
  if (cat === 'FUTURES') {
    entry2 = isShort ? entry1 * 1.025 : entry1 * 0.975;
    entry3 = isShort ? entry1 * 1.05 : entry1 * 0.95;
  }
  const ranges = [
    { label: '1차', price: entry1, note: isShort ? '첫 숏' : '첫 진입' },
    { label: '2차', price: entry2, note: isShort ? '추가 숏' : '눌림 추가' },
    { label: '3차', price: entry3, note: isShort ? '최종 숏' : '최종 분할' },
  ];
  return { isShort, ranges };
}


function getTodayAction(s: Stock) {
  const cat = getCategory(s);
  const side = String(s.side || 'LONG').toUpperCase();
  const isShort = cat === 'FUTURES' && side === 'SHORT';
  const current = num(s.price);
  const entry = num(s.entry_price, current);
  const stop = num(s.stop_price);
  const target = num(s.target_price);
  const win = derivedWinRate(s);

  if (!current || !entry) return s.action_text || '데이터 확인 후 진입 판단';

  if (isShort) {
    if (current >= entry * 0.995) return `오늘 행동: 1차 숏 구간 접근 · 분할 진입 가능 · 승률 ${win.toFixed(0)}%`;
    if (target > 0 && current <= target * 1.03) return '오늘 행동: 목표가 근처 · 신규 숏보다는 수익 관리 우선';
    return `오늘 행동: 추격 숏 금지 · ${money(entry, s.market)} 부근까지 대기`;
  }

  if (stop > 0 && current <= stop * 1.025) return '오늘 행동: 손절가 근처 · 신규 진입 보류 · 반등 확인 필요';
  if (current <= entry * 1.01) return `오늘 행동: 1차 진입가 근처 · 분할 진입 가능 · 승률 ${win.toFixed(0)}%`;
  if (current > entry * 1.045) return `오늘 행동: 이미 상승 구간 · 추격매수 금지 · ${money(entry, s.market)} 부근 대기`;
  if (target > 0 && current >= target * 0.96) return '오늘 행동: 목표가 근처 · 신규 진입보다 수익 실현 계획 우선';
  return s.action_text || `오늘 행동: 1차 진입가 ${money(entry, s.market)} 근처까지 대기`;
}


function getActionTone(s: Stock) {
  const cat = getCategory(s);
  const side = String(s.side || 'LONG').toUpperCase();
  const isShort = cat === 'FUTURES' && side === 'SHORT';
  const current = num(s.price);
  const entry = num(s.entry_price, current);
  const stop = num(s.stop_price);
  const target = num(s.target_price);
  if (!current || !entry) return 'wait';
  if (isShort) {
    if (target > 0 && current <= target * 1.03) return 'danger';
    if (current >= entry * 0.995) return 'buy';
    return 'wait';
  }
  if (stop > 0 && current <= stop * 1.025) return 'danger';
  if (target > 0 && current >= target * 0.96) return 'danger';
  if (current <= entry * 1.01) return 'buy';
  return 'wait';
}

function getActionToneLabel(s: Stock) {
  const tone = getActionTone(s);
  if (tone === 'buy') return '진입 가능';
  if (tone === 'danger') return '주의';
  return '대기';
}

function shouldFillOrder(p: PaperTrade, currentPrice: number) {
  if (p.status !== 'PENDING' || !Number.isFinite(currentPrice) || currentPrice <= 0) return false;
  const isShort = String(p.side).toUpperCase() === 'SHORT';
  return isShort ? currentPrice >= p.requestedPrice : currentPrice <= p.requestedPrice;
}

function calcPnlPct(p: PaperTrade, currentPrice: number) {
  const base = p.fillPrice || p.requestedPrice;
  if (!base || base <= 0) return 0;
  const isShort = String(p.side).toUpperCase() === 'SHORT';
  return (isShort ? (base - currentPrice) / base : (currentPrice - base) / base) * 100;
}

function stockKey(s: Stock) {
  return `${getCategory(s)}-${s.symbol}-${String(s.side || 'LONG').toUpperCase()}`;
}

function tradeKey(p: PaperTrade) {
  return `${p.category}-${p.symbol}-${String(p.side || 'LONG').toUpperCase()}`;
}

export default function Page() {
  const [stocks, setStocks] = useState<Stock[]>(demo);
  const [activeTab, setActiveTab] = useState<MainTab>('PICKS');
  const [activeCat, setActiveCat] = useState<Category>('US');
  const [sel, setSel] = useState<Stock>(demo[0]);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState(hasSupabase ? 'Cloud 연결' : 'Demo 모드');
  const [lastUpdated, setLastUpdated] = useState('');
  const [user, setUser] = useState<any>(null);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [paperEntry, setPaperEntry] = useState('');
  const [paperQty, setPaperQty] = useState('1');
  const [authBusy, setAuthBusy] = useState(false);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  const [showAuth, setShowAuth] = useState(false);
  const [paperMode, setPaperMode] = useState<'HOLD' | 'PENDING' | 'CLOSED'>('HOLD');
  const searchRef = useRef<HTMLInputElement | null>(null);

  const selectedEntry = num(String(paperEntry).replace(/,/g, ''), num(sel.entry_price, sel.price));
  const selectedQty = num(String(paperQty).replace(/,/g, ''), 1);
  const selectedCategory = getCategory(sel);
  const entryGuide = getEntryGuide(sel, selectedEntry);

  const upsertProfile = async (u: any) => {
    if (!hasSupabase || !supabase || !u) return;
    await supabase.from('profiles').upsert({
      id: u.id,
      email: u.email,
      display_name: u.user_metadata?.full_name || u.email?.split('@')[0] || 'Alpha Trader',
      avatar_url: u.user_metadata?.avatar_url || null,
      updated_at: new Date().toISOString(),
    });
  };

  const validateAuthForm = () => {
    const email = authEmail.trim();
    if (!email || !authPassword) {
      alert('이메일과 비밀번호를 입력해줘.');
      return null;
    }
    if (authPassword.length < 6) {
      alert('비밀번호는 최소 6자 이상이어야 해.');
      return null;
    }
    return { email, password: authPassword };
  };

  const signInEmail = async () => {
    if (!hasSupabase || !supabase) return alert('Supabase 연결이 필요합니다.');
    const form = validateAuthForm();
    if (!form) return;
    setAuthBusy(true);
    setAuthMessage('');
    const { error } = await supabase.auth.signInWithPassword(form);
    if (error) {
      alert(error.message);
    } else {
      setAuthMessage('로그인 완료');
      setShowAuth(false);
    }
    setAuthBusy(false);
  };

  const signUpEmail = async () => {
    if (!hasSupabase || !supabase) return alert('Supabase 연결이 필요합니다.');
    const form = validateAuthForm();
    if (!form) return;
    setAuthBusy(true);
    setAuthMessage('');
    const { data, error } = await supabase.auth.signUp({
      email: form.email,
      password: form.password,
      options: { data: { full_name: form.email.split('@')[0] } },
    });
    if (error) {
      alert(error.message);
    } else {
      setAuthMessage(data.session ? '회원가입 및 로그인 완료' : '회원가입 완료. 바로 로그인을 눌러줘.');
      if (data.session) setShowAuth(false);
    }
    setAuthBusy(false);
  };

  const signOut = async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUser(null);
    setTrades([]);
    setShowAuth(false);
  };

  const loadLeaderboard = async () => {
    if (!hasSupabase || !supabase) return;
    const { data } = await supabase.from('paper_trade_leaderboard').select('*').order('win_rate', { ascending: false }).limit(20);
    if (data) setLeaderboard(data as LeaderboardRow[]);
  };

  const loadPaperTrades = async (uid?: string) => {
    if (!hasSupabase || !supabase || !uid) {
      setTrades([]);
      return;
    }
    const { data, error } = await supabase.from('paper_trades').select('*').eq('user_id', uid).order('created_at', { ascending: false }).limit(500);
    if (error) {
      console.error('paper_trades load error:', error);
      return;
    }
    const mapped: PaperTrade[] = (data || []).map((r: any) => ({
      id: String(r.id), user_id: String(r.user_id), symbol: String(r.symbol), name: String(r.name || r.symbol), market: String(r.market || ''),
      category: String(r.category || 'US') as Category, side: String(r.side || 'LONG'), status: String(r.status || 'PENDING') as PaperStatus,
      requestedPrice: num(r.requested_price), fillPrice: r.fill_price == null ? undefined : num(r.fill_price), closePrice: r.close_price == null ? undefined : num(r.close_price),
      qty: num(r.qty, 1), pnlPct: r.pnl_pct == null ? undefined : num(r.pnl_pct), pnlMoney: r.pnl_money == null ? undefined : num(r.pnl_money),
      createdAt: String(r.created_at || new Date().toISOString()), filledAt: r.filled_at || undefined, closedAt: r.closed_at || undefined,
    }));
    setTrades(mapped);
  };

  useEffect(() => {
    if (!hasSupabase || !supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      const u = data.session?.user ?? null;
      setUser(u);
      if (u) {
        upsertProfile(u);
        loadPaperTrades(u.id);
        loadLeaderboard();
      }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event: any, session: any) => {
      const u = session?.user ?? null;
      setUser(u);
      if (u) {
        upsertProfile(u);
        loadPaperTrades(u.id);
        loadLeaderboard();
      } else {
        setTrades([]);
      }
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const entry = num(sel.entry_price, sel.price);
    setPaperEntry(entry > 0 ? String(entry) : '');
    setPaperQty('1');
  }, [sel.symbol, sel.market, sel.entry_price, sel.price]);

  useEffect(() => {
    if (activeTab === 'SEARCH') {
      const t = setTimeout(() => searchRef.current?.focus(), 120);
      return () => clearTimeout(t);
    }
  }, [activeTab]);

  useEffect(() => {
    async function load(keepSelection = false) {
      if (!hasSupabase || !supabase) return;
      const { data, error } = await supabase.from('rankings').select('*').order('score', { ascending: false }).limit(1500);
      if (error) {
        console.error('Supabase rankings load error:', error);
        setMode('Supabase 오류');
        return;
      }
      if (data && data.length) {
        const mapped: Stock[] = data.map((r: any) => ({
          symbol: String(r.symbol ?? '').trim(),
          name: String(r.name ?? '').trim() || String(r.symbol ?? '').trim(),
          market: String(r.market ?? '').trim().toUpperCase(),
          score: num(r.score), grade: r.grade ?? 'C', price: num(r.price), entry_price: num(r.entry_price), stop_price: num(r.stop_price), target_price: num(r.target_price),
          reason: r.reason ?? '', beginner_note: r.beginner_note ?? '', change_text: r.change_text ?? '관찰', decision: r.decision ?? '관망', risk_level: r.risk_level ?? '보통', action_text: r.action_text ?? '추가 확인 필요',
          trend_score: num(r.trend_score), volume_score: num(r.volume_score), news_score: num(r.news_score), earnings_score: num(r.earnings_score), flow_score: num(r.flow_score), risk_score: num(r.risk_score), timing_score: num(r.timing_score),
          win_rate: num(r.win_rate), expected_return: num(r.expected_return), loss_risk: num(r.loss_risk), final_score: num(r.final_score), confidence_grade: r.confidence_grade ?? '',
          asset_class: r.asset_class ?? '', trade_type: r.trade_type ?? '', side: r.side ?? '',
        }));
        mapped.sort((a, b) => profitScore(b) - profitScore(a));
        setStocks(mapped);
        setSel((prev) => {
          if (!keepSelection) return mapped.find((s) => getCategory(s) === activeCat) ?? mapped[0];
          return mapped.find((x) => x.symbol === prev.symbol && getCategory(x) === getCategory(prev) && String(x.side || 'LONG') === String(prev.side || 'LONG')) ?? prev;
        });
        setMode('Supabase 실시간 연결');
        setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
      }
    }
    load(false);
    const timer = setInterval(() => load(true), 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const check = async () => {
      if (!user || !hasSupabase || !supabase || trades.length === 0) return;
      const pending = trades.filter((p) => p.status === 'PENDING');
      for (const p of pending) {
        const stock = stocks.find((s) => s.symbol === p.symbol && getCategory(s) === p.category && String(s.side || 'LONG').toUpperCase() === String(p.side || 'LONG').toUpperCase());
        const cur = stock?.price || 0;
        if (shouldFillOrder(p, cur)) {
          const now = new Date().toISOString();
          await supabase.from('paper_trades').update({ status: 'FILLED', fill_price: cur, filled_at: now, updated_at: now }).eq('id', p.id).eq('user_id', user.id);
          await supabase.from('paper_trade_events').insert({ trade_id: p.id, user_id: user.id, event_type: 'FILLED', price: cur, qty: p.qty, note: '가격 도달 자동체결' });
          await loadPaperTrades(user.id);
          await loadLeaderboard();
        }
      }
    };
    check();
  }, [stocks, trades, user]);

  const topByCat = useMemo(() => {
    const out: Record<Category, Stock[]> = { US: [], KR: [], COIN: [], FUTURES: [] };
    CATS.forEach((c) => {
      out[c.id] = stocks.filter((s) => getCategory(s) === c.id).sort((a, b) => profitScore(b) - profitScore(a)).slice(0, 10);
    });
    return out;
  }, [stocks]);

  const ranked = topByCat[activeCat];

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return stocks.filter((s) => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)).sort((a, b) => profitScore(b) - profitScore(a)).slice(0, 60);
  }, [query, stocks]);

  const counts = useMemo(() => ({
    US: stocks.filter((s) => getCategory(s) === 'US').length,
    KR: stocks.filter((s) => getCategory(s) === 'KR').length,
    COIN: stocks.filter((s) => getCategory(s) === 'COIN').length,
    FUTURES: stocks.filter((s) => getCategory(s) === 'FUTURES').length,
  }), [stocks]);

  const activeTrades = trades.filter((p) => p.status === 'FILLED');
  const pendingTrades = trades.filter((p) => p.status === 'PENDING');
  const closedTrades = trades.filter((p) => p.status === 'CLOSED');

  const portfolioRows = useMemo(() => activeTrades.map((p) => {
    const stock = stocks.find((s) => s.symbol === p.symbol && getCategory(s) === p.category && String(s.side || 'LONG').toUpperCase() === String(p.side || 'LONG').toUpperCase());
    const cur = stock?.price ?? p.fillPrice ?? p.requestedPrice;
    const pnlPct = calcPnlPct(p, cur);
    const base = p.fillPrice || p.requestedPrice;
    const pnlMoney = (pnlPct / 100) * base * p.qty;
    return { p, stock, cur, pnlPct, pnlMoney };
  }), [activeTrades, stocks]);

  const totalValue = portfolioRows.reduce((a, r) => a + r.cur * r.p.qty, 0);
  const totalCost = portfolioRows.reduce((a, r) => a + (r.p.fillPrice || r.p.requestedPrice) * r.p.qty, 0);
  const totalPnl = portfolioRows.reduce((a, r) => a + r.pnlMoney, 0);
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const closedWinRate = closedTrades.length ? (closedTrades.filter((t) => num(t.pnlPct) > 0).length / closedTrades.length) * 100 : 0;

  const openOrder = async (s: Stock, requestPrice: number, qty: number) => {
    if (!user) return alert('먼저 로그인해주세요.');
    if (!hasSupabase || !supabase) return alert('Supabase 연결이 필요합니다.');
    const cat = getCategory(s);
    const existing = activeTrades.filter((p) => p.category === cat).length + pendingTrades.filter((p) => p.category === cat).length;
    if (existing >= maxPositions(cat)) return alert(`${categoryName(cat)} 모의투자는 대기+보유 합산 최대 ${maxPositions(cat)}개입니다.`);
    if (!requestPrice || requestPrice <= 0 || !qty || qty <= 0) return alert('진입가와 수량을 확인해줘.');
    const side = cat === 'FUTURES' ? String(s.side || 'LONG').toUpperCase() : 'LONG';
    const now = new Date().toISOString();
    const { error } = await supabase.from('paper_trades').insert({
      user_id: user.id, symbol: s.symbol, name: s.name, market: s.market, category: cat, side,
      status: 'PENDING', requested_price: requestPrice, qty, created_at: now, updated_at: now,
    });
    if (error) return alert(error.message);
    await loadPaperTrades(user.id);
    setActiveTab('PAPER');
  };

  const closeTrade = async (p: PaperTrade) => {
    if (!user || !hasSupabase || !supabase) return;
    const stock = stocks.find((s) => s.symbol === p.symbol && getCategory(s) === p.category && String(s.side || 'LONG').toUpperCase() === String(p.side || 'LONG').toUpperCase());
    const cur = stock?.price ?? p.fillPrice ?? p.requestedPrice;
    const pnlPct = calcPnlPct(p, cur);
    const base = p.fillPrice || p.requestedPrice;
    const pnlMoney = (pnlPct / 100) * base * p.qty;
    const now = new Date().toISOString();
    const { error } = await supabase.from('paper_trades').update({ status: 'CLOSED', close_price: cur, pnl_pct: pnlPct, pnl_money: pnlMoney, closed_at: now, updated_at: now }).eq('id', p.id).eq('user_id', user.id);
    if (error) return alert(error.message);
    await supabase.from('paper_trade_events').insert({ trade_id: p.id, user_id: user.id, event_type: 'CLOSED', price: cur, qty: p.qty, pnl_pct: pnlPct, pnl_money: pnlMoney, note: '사용자 모의청산' });
    await loadPaperTrades(user.id);
    await loadLeaderboard();
  };

  const cancelTrade = async (p: PaperTrade) => {
    if (!user || !hasSupabase || !supabase) return;
    const now = new Date().toISOString();
    const { error } = await supabase.from('paper_trades').update({ status: 'CANCELED', updated_at: now }).eq('id', p.id).eq('user_id', user.id);
    if (error) return alert(error.message);
    await supabase.from('paper_trade_events').insert({ trade_id: p.id, user_id: user.id, event_type: 'CANCELED', price: p.requestedPrice, qty: p.qty, note: '사용자 주문취소' });
    await loadPaperTrades(user.id);
  };

  const selectStock = (s: Stock) => {
    setSel(s);
    setActiveCat(getCategory(s));
    setActiveTab('DETAIL');
  };

  const Header = () => (
    <header className="topbar">
      <button className="backBtn" onClick={() => setActiveTab('PICKS')} aria-label="home">‹</button>
      <div className="brand">
        <b>Alpha Radar AI</b>
        <em>Made By YHJ</em>
        <span><i />{mode} {lastUpdated ? `· ${lastUpdated}` : ''}</span>
      </div>
      {user ? <button className="userBtn" onClick={signOut}>👤 {user.email?.split('@')[0]} · 로그아웃</button> : <button className="paperTop" onClick={() => setShowAuth(true)}>로그인</button>}
      <button className="menuBtn" onClick={() => { setActiveTab('SEARCH'); setTimeout(() => searchRef.current?.focus(), 100); }}>☰</button>
    </header>
  );

  const AuthPanel = ({ compact = false }: { compact?: boolean }) => (
    <div className={compact ? 'authPanel compact' : 'authPanel'}>
      <div className="sectionTitle"><b>로그인</b><span>이메일 + 비밀번호</span></div>
      <div className="authInputs">
        <input
          type="email"
          value={authEmail}
          onChange={(e) => setAuthEmail(e.target.value)}
          placeholder="이메일"
          autoComplete="email"
        />
        <input
          type="password"
          value={authPassword}
          onChange={(e) => setAuthPassword(e.target.value)}
          placeholder="비밀번호 6자 이상"
          autoComplete="current-password"
          onKeyDown={(e) => { if (e.key === 'Enter') signInEmail(); }}
        />
      </div>
      {authMessage && <p className="authMsg">{authMessage}</p>}
      <div className="authActions">
        <button className="primary" onClick={signInEmail} disabled={authBusy}>{authBusy ? '처리중...' : '로그인'}</button>
        <button className="ghostBtn" onClick={signUpEmail} disabled={authBusy}>회원가입</button>
      </div>
      <p className="authHint">메일 인증번호 없이 이메일/비밀번호로 로그인합니다. 한 번 로그인하면 세션이 유지됩니다.</p>
    </div>
  );

  const BottomNav = () => (
    <nav className="bottomNav">
      <button className={activeTab === 'PICKS' ? 'on' : ''} onClick={() => setActiveTab('PICKS')}>⌂<span>홈</span></button>
      <button className={activeTab === 'SEARCH' ? 'on' : ''} onClick={() => { setActiveTab('SEARCH'); setTimeout(() => searchRef.current?.focus(), 120); }}>⌕<span>검색</span></button>
      <button className={activeTab === 'DETAIL' ? 'on' : ''} onClick={() => setActiveTab('DETAIL')}>◇<span>상세</span></button>
      <button className={activeTab === 'PAPER' ? 'on paperNav' : 'paperNav'} onClick={() => setActiveTab('PAPER')}>◔{pendingTrades.length > 0 && <i className="navBadge">{pendingTrades.length}</i>}<span>모의투자</span></button>
      <button className={activeTab === 'HISTORY' ? 'on' : ''} onClick={() => setActiveTab('HISTORY')}>♙<span>마이페이지</span></button>
    </nav>
  );

  const StockCard = ({ s, i }: { s: Stock; i: number }) => {
    const cat = getCategory(s);
    return (
      <button className="stockCard topCard" onClick={() => selectStock(s)}>
        <strong className="rankNo">{i + 1}</strong>
        <div className="stockMain">
          <div className="stockTitleRow"><b>{s.name}</b><span className={`marketTag ${cat.toLowerCase()}`}>{marketBadge(cat)}</span></div>
          <span>{s.symbol} · {categoryName(cat)} · {sideLabel(s)}</span>
          <em>{s.grade || s.confidence_grade || 'B'} Grade · 확률점수 {Math.round(profitScore(s))}</em>
        </div>
        <div className="stockNums"><b>{derivedWinRate(s).toFixed(0)}%</b><span>{pct(derivedExpectedReturn(s))}</span></div>
      </button>
    );
  };

  const PicksView = () => (
    <section className="screen">
      <div className="heroCard">
        <div><span className="muted">{mode} {lastUpdated ? `· ${lastUpdated}` : ''}</span><h1>오늘의 수익 후보 TOP10</h1><p>화면에는 핵심 10개만, 검색은 전체 종목에서 찾습니다.</p></div>
        <button className="paperTop big" onClick={() => setActiveTab('PAPER')}>💼 모의투자</button>
      </div>
      <div className="catTabs">{CATS.map((c) => <button key={c.id} className={activeCat === c.id ? 'on' : ''} onClick={() => setActiveCat(c.id)}>{c.label}</button>)}</div>
      <div className="listCards">{ranked.map((s, i) => <StockCard key={`${stockKey(s)}-${i}`} s={s} i={i} />)}</div>
    </section>
  );

  const SearchView = () => (
    <section className="screen searchScreen">
      <h1>종목 검색</h1>
      <input
        ref={searchRef}
        className="searchInput"
        value={query}
        autoFocus
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="예: NVDA, TSLA, 삼성전자, BTC"
      />
      <p className="hint">검색 탭에서는 타이핑 중 화면이 이동하지 않도록 고정했습니다. 순위 밖 종목도 검색됩니다.</p>
      <div className="listCards searchResults">{searchResults.map((s, i) => <StockCard key={`${stockKey(s)}-search-${i}`} s={s} i={i} />)}</div>
      {!query && <div className="empty">검색어를 입력해줘.</div>}
      {query && searchResults.length === 0 && <div className="empty">검색 결과 없음. 엔진 universe에 추가가 필요할 수 있음.</div>}
    </section>
  );

  const DetailView = () => (
    <section className="screen detailScreen">
      <div className="stockHero">
        <div className="heroLeft">
          <h1>{sel.name}</h1>
          <p>{sel.symbol} · {categoryName(selectedCategory)} · {sideLabel(sel)}</p>
          <div className="judgementRow"><span>AI 판단</span><b>승률 {derivedWinRate(sel).toFixed(0)}%</b></div>
          <em>{sel.decision || '관찰'} · AI 모델 3.2</em>
        </div>
        <div className="pricePanel">
          <span>현재가</span>
          <b>{money(sel.price, sel.market)}</b>
          <strong className={parsePct(sel.change_text) >= 0 ? 'green' : 'red'}>{sel.change_text || '실시간'}</strong>
          <div className="spark"><i /></div>
        </div>
      </div>

      <div className={`actionStrip ${getActionTone(sel)}`}>
        <span>{getActionToneLabel(sel)}</span>
        <b>{getTodayAction(sel)}</b>
      </div>

      <div className="metricGrid premiumMetrics">
        <div><span>목표가</span><b className="green">{money(sel.target_price, sel.market)}</b></div>
        <div><span>손절가</span><b className="red">{money(sel.stop_price, sel.market)}</b></div>
        <div><span>기대수익</span><b>{pct(derivedExpectedReturn(sel))}</b></div>
        <div><span>신뢰도</span><b>{(s => s === 'S' ? '5.0' : s === 'A' ? '4.5' : s === 'B' ? '4.0' : '3.5')(String(sel.confidence_grade || sel.grade || 'B').toUpperCase())} / 5.0</b></div>
      </div>

      <div className="entryBox premiumBox">
        <div className="sectionTitle"><b>추천 진입가</b><span>분할 진입 전략</span></div>
        <div className="entryMiniGrid">
          {entryGuide.ranges.map((r) => <div className="entryMini" key={r.label}><span>{r.label} · {r.note}</span><b>{money(r.price, sel.market)}</b><em>진입 가능</em></div>)}
        </div>
      </div>

      <div className="orderBox premiumBox compactOrder">
        <div className="sectionTitle"><b>모의투자 주문</b><span>{selectedCategory === 'FUTURES' && String(sel.side).toUpperCase() === 'SHORT' ? 'SHORT 예약' : 'LONG/현물 예약'}</span></div>
        <div className="orderInputs"><label>진입가<input value={paperEntry} onChange={(e) => setPaperEntry(e.target.value)} /></label><label>수량<input value={paperQty} onChange={(e) => setPaperQty(e.target.value)} /></label></div>
        <button className="primary" onClick={() => openOrder(sel, selectedEntry, selectedQty)}>예약주문 등록</button>
      </div>

      <div className="analysisBox premiumBox">
        <div className="sectionTitle"><b>AI 종합 분석</b><span>자세히 보기 ›</span></div>
        <div className="analysisGrid">
          <div><span>추세</span><b>상승 추세</b><span>모멘텀</span><b>강함</b><span>시장심리</span><b className="green">긍정적</b></div>
          <div><span>거래량</span><b>증가</b><span>변동성</span><b>보통</b><span>리스크</span><b className="yellow">보통</b></div>
        </div>
        <div className="pointGrid">
          <div><b>핵심 포인트</b><p>• 승률 {derivedWinRate(sel).toFixed(0)}% 구간 진입<br/>• 분할 진입으로 리스크 관리 권장<br/>• {sel.reason || sel.action_text || 'AI 분석 대기'}</p></div>
          <div><b>주의 사항</b><p>• 시장 변동성 확대 구간 주의<br/>• 손절가 이탈 시 손실 최소화<br/>• 단기 급등 시 추격 매수 금지</p></div>
        </div>
        <div className="modelInfo"><span>업데이트<br/><b>{lastUpdated || '-'}</b></span><span>데이터 소스<br/><b>Supabase 실시간</b></span><span>모델 버전<br/><b>Alpha Radar v3.2</b></span></div>
      </div>
    </section>
  );

  const TradeRow = ({ row }: { row: { p: PaperTrade; stock?: Stock; cur: number; pnlPct: number; pnlMoney: number } }) => (
    <div className="holdCard">
      <div className="holdTop"><div><b>{row.p.name}</b><span>{row.p.symbol} · {categoryName(row.p.category)} · {row.p.side}</span></div><strong className={row.pnlPct >= 0 ? 'green' : 'red'}>{pct(row.pnlPct)}</strong></div>
      <div className="holdMetrics"><span>진입 {money(row.p.fillPrice || row.p.requestedPrice, row.p.market)}</span><span>현재 {money(row.cur, row.p.market)}</span><span>손익 {row.pnlMoney >= 0 ? '+' : ''}{row.pnlMoney.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span></div>
      <div className="holdActions"><button className="sell" onClick={() => closeTrade(row.p)}>매도/청산</button><button className="buy" onClick={() => { setSel(row.stock || sel); setPaperEntry(String(row.cur)); setActiveTab('DETAIL'); }}>추가매수</button></div>
    </div>
  );

  const PaperView = () => (
    <section className="screen paperScreen">
      <div className="portfolioHero">
        <div><h1>모의투자</h1><p>예약주문 · 보유종목 · 거래기록을 한 화면에서 관리합니다.</p></div>
        <button className="paperTop" onClick={() => setActiveTab('PICKS')}>+ 종목 찾기</button>
      </div>
      {!user && <div className="loginBox"><b>로그인 필요</b><p>로그인 후 예약주문/거래기록이 Supabase에 저장됩니다.</p><AuthPanel compact /></div>}
      <div className="paperDashboard premiumBox">
        <div className="sectionTitle"><b>내 모의투자 성과</b><span>청산 완료 기준</span></div>
        <div className="performanceHero">
          <div><span>승률</span><b>{closedTrades.length ? `${closedWinRate.toFixed(1)}%` : '-'}</b><em>{closedTrades.length}건 완료</em></div>
          <div><span>총손익</span><b className={totalPnl >= 0 ? 'green' : 'red'}>{totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString(undefined, { maximumFractionDigits: 2 })}</b><em>보유 기준</em></div>
        </div>
        <div className="summaryGrid paperSummary">
          <div><span>평가금</span><b>{totalValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}</b></div>
          <div><span>평균수익</span><b className={avgClosedPnl >= 0 ? 'green' : 'red'}>{closedTrades.length ? pct(avgClosedPnl) : '-'}</b></div>
          <div><span>최근10회</span><b>{recentTen.length ? `${recentWinRate.toFixed(1)}%` : '-'}</b></div>
          <div><span>최고수익</span><b className="green">{closedTrades.length ? pct(bestClosedPnl) : '-'}</b></div>
        </div>
      </div>
      <div className="paperTabs">
        <button className={paperMode === 'HOLD' ? 'on' : ''} onClick={() => setPaperMode('HOLD')}>보유중 <b>{portfolioRows.length}</b></button>
        <button className={paperMode === 'PENDING' ? 'on' : ''} onClick={() => setPaperMode('PENDING')}>대기주문 <b>{pendingTrades.length}</b></button>
        <button className={paperMode === 'CLOSED' ? 'on' : ''} onClick={() => setPaperMode('CLOSED')}>거래기록 <b>{closedTrades.length}</b></button>
      </div>
      {paperMode === 'HOLD' && (portfolioRows.length ? portfolioRows.map((r) => <TradeRow key={r.p.id} row={r} />) : <div className="empty">보유 종목 없음</div>)}
      {paperMode === 'PENDING' && (pendingTrades.length ? pendingTrades.map((p) => <div key={p.id} className="pendingCard"><div><b>{p.name}</b><span>{p.symbol} · 예약가 {money(p.requestedPrice, p.market)}</span></div><button onClick={() => cancelTrade(p)}>취소</button></div>) : <div className="empty">대기 주문 없음</div>)}
      {paperMode === 'CLOSED' && (closedTrades.length ? closedTrades.map((p) => <div key={p.id} className="historyLine"><div><b>{p.name}</b><span>{p.symbol} · {categoryName(p.category)} · {p.side}</span></div><strong className={num(p.pnlPct) >= 0 ? 'green' : 'red'}>{pct(num(p.pnlPct))}</strong></div>) : <div className="empty">거래 기록 없음</div>)}
    </section>
  );

  const recentTen = closedTrades.slice(0, 10);
  const recentWinRate = recentTen.length ? (recentTen.filter((t) => num(t.pnlPct) > 0).length / recentTen.length) * 100 : 0;
  const avgClosedPnl = closedTrades.length ? closedTrades.reduce((a, t) => a + num(t.pnlPct), 0) / closedTrades.length : 0;
  const bestClosedPnl = closedTrades.length ? Math.max(...closedTrades.map((t) => num(t.pnlPct))) : 0;
  const totalClosedPnl = closedTrades.reduce((a, t) => a + num(t.pnlMoney), 0);

  const HistoryView = () => (
    <section className="screen">
      <h1>내 투자 기록</h1>
      <div className="heroCard historyHero">
        <div>
          <span className="muted">청산 완료 거래 기준</span>
          <h1>{closedTrades.length ? `${closedWinRate.toFixed(1)}%` : '-'} 승률</h1>
          <p>랭킹 없이 내 모의투자 성과만 깔끔하게 봅니다.</p>
        </div>
      </div>
      <div className="summaryGrid">
        <div><span>총 거래수</span><b>{closedTrades.length}</b></div>
        <div><span>평균수익</span><b className={avgClosedPnl >= 0 ? 'green' : 'red'}>{closedTrades.length ? pct(avgClosedPnl) : '-'}</b></div>
        <div><span>최근10회</span><b>{recentTen.length ? `${recentWinRate.toFixed(1)}%` : '-'}</b></div>
      </div>
      <div className="summaryGrid">
        <div><span>현재 보유</span><b>{activeTrades.length}</b></div>
        <div><span>대기 주문</span><b>{pendingTrades.length}</b></div>
        <div><span>누적손익</span><b className={totalClosedPnl >= 0 ? 'green' : 'red'}>{totalClosedPnl >= 0 ? '+' : ''}{totalClosedPnl.toLocaleString(undefined, { maximumFractionDigits: 2 })}</b></div>
      </div>
      <h2>📜 청산 기록</h2>
      {closedTrades.length ? closedTrades.map((p) => <div key={p.id} className="historyLine"><div><b>{p.name}</b><span>{p.symbol} · {categoryName(p.category)} · {p.side}</span></div><strong className={num(p.pnlPct) >= 0 ? 'green' : 'red'}>{pct(num(p.pnlPct))}</strong></div>) : <div className="empty">청산 기록 없음</div>}
    </section>
  );

  return (
    <main className="app">
      <Header />
      <div className="content">
        {activeTab === 'PICKS' && PicksView()}
        {activeTab === 'SEARCH' && SearchView()}
        {activeTab === 'DETAIL' && DetailView()}
        {activeTab === 'PAPER' && PaperView()}
        {activeTab === 'HISTORY' && HistoryView()}
      </div>
      {showAuth && !user && (
        <div className="authOverlay" onClick={() => setShowAuth(false)}>
          <div onClick={(e) => e.stopPropagation()}>
            <button className="authClose" onClick={() => setShowAuth(false)}>×</button>
            <AuthPanel />
          </div>
        </div>
      )}
      <BottomNav />
      <style jsx>{`
        :global(body){margin:0;background:#03070d;color:#eef4ff;font-family:Inter,Apple SD Gothic Neo,Segoe UI,Arial,sans-serif;}
        :global(*){box-sizing:border-box;}
        .app{min-height:100vh;background:radial-gradient(circle at 20% 0%,rgba(18,93,75,.35),transparent 34%),radial-gradient(circle at 95% 10%,rgba(26,44,71,.55),transparent 40%),#05080d;padding-bottom:92px;}
        .content{width:100%;max-width:860px;margin:0 auto;padding:16px 14px 20px;}
        .screen{animation:fade .18s ease;}@keyframes fade{from{opacity:.55;transform:translateY(5px)}to{opacity:1;transform:none}}
        h1{font-size:26px;line-height:1.1;margin:4px 0 7px;letter-spacing:-.04em}h2{font-size:17px;margin:18px 0 10px}.muted,.hint{color:#9ca7b8;font-size:12px}.green{color:#20d58a}.red{color:#ff5454}.yellow{color:#f5c84b}
        .topbar{position:sticky;top:0;z-index:80;display:flex;align-items:center;gap:10px;min-height:74px;padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.05);background:linear-gradient(180deg,rgba(3,7,13,.96),rgba(3,7,13,.72));backdrop-filter:blur(18px);}
        .backBtn,.menuBtn{width:32px;height:42px;border:0;background:transparent;color:#eaf2ff;font-size:34px;line-height:1}.menuBtn{font-size:25px}.brand{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.brand b{font-size:24px;letter-spacing:-.04em}.brand em{display:block;color:#b9c2cf;font-style:normal;font-weight:700;font-size:14px}.brand span{color:#94a3b8;font-size:12px}.brand span i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#20d58a;margin-right:5px}.paperTop,.userBtn{border:1px solid rgba(32,213,138,.7);background:rgba(32,213,138,.08);color:#33e79a;border-radius:999px;padding:10px 14px;font-weight:900;white-space:nowrap}.userBtn{max-width:112px;overflow:hidden;text-overflow:ellipsis}.paperTop.big{padding:12px 15px}.miniSearch{display:none}
        .heroCard,.detailHeader,.portfolioHero,.loginBox,.aiBox,.entryBox,.orderBox,.stockHero,.premiumBox{border:1px solid rgba(148,163,184,.15);background:linear-gradient(145deg,rgba(16,22,29,.94),rgba(8,12,17,.94));border-radius:22px;padding:16px;box-shadow:0 18px 42px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.04)}.heroCard,.portfolioHero,.detailHeader{display:flex;justify-content:space-between;gap:12px;align-items:center}.heroCard p{margin:0;color:#9fb0c7;font-size:13px;line-height:1.4}
        .catTabs{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:12px 0}.catTabs button{border:1px solid rgba(148,163,184,.14);background:#101820;color:#d4deea;border-radius:15px;padding:11px 8px;font-weight:900}.catTabs button span{display:none}.catTabs .on{background:rgba(32,213,138,.13);border-color:rgba(32,213,138,.55);color:#20d58a}.listCards{display:grid;gap:10px}.stockCard{display:grid;grid-template-columns:38px 1fr auto;align-items:center;gap:10px;width:100%;text-align:left;border:1px solid rgba(148,163,184,.13);background:linear-gradient(145deg,rgba(16,22,29,.94),rgba(8,12,17,.94));border-radius:18px;padding:14px;color:#e5eefb;box-shadow:0 10px 28px rgba(0,0,0,.20)}.rankNo{width:30px;height:30px;border-radius:10px;background:rgba(32,213,138,.14);display:grid;place-items:center;color:#20d58a!important}.stockMain b{display:block;font-size:17px}.stockMain span,.stockNums span{display:block;color:#96a2b1;font-size:12px;margin-top:3px}.stockMain em{display:block;color:#b8c1ce;font-size:11px;font-style:normal;margin-top:4px}.stockNums{text-align:right}.stockNums b{color:#20d58a;font-size:22px}.searchInput{width:100%;border:1px solid rgba(148,163,184,.18);background:#09111a;color:white;border-radius:16px;padding:15px;font-size:16px;outline:none}.empty{border:1px dashed rgba(148,163,184,.24);border-radius:18px;padding:18px;text-align:center;color:#94a3b8;background:rgba(15,23,42,.38)}
        .detailScreen{display:grid;gap:10px}.stockHero{display:grid;grid-template-columns:1fr 1.05fr;gap:12px;align-items:stretch}.heroLeft h1{font-size:30px;margin:0 0 10px}.heroLeft p{margin:0 0 18px;color:#9aa6b5;font-size:16px}.heroLeft em{display:block;color:#98a3b2;font-style:normal;margin-top:10px}.judgementRow{display:flex;align-items:center;gap:12px}.judgementRow span{border:1px solid rgba(32,213,138,.6);color:#20d58a;border-radius:10px;padding:7px 10px;font-weight:900}.judgementRow b{font-size:26px;color:#20d58a}.pricePanel{position:relative;border:1px solid rgba(148,163,184,.14);background:rgba(8,13,19,.72);border-radius:18px;padding:14px;min-height:138px;overflow:hidden}.pricePanel span{color:#a3adbb}.pricePanel b{display:block;font-size:24px;margin:8px 0}.pricePanel strong{font-size:15px}.spark{position:absolute;right:12px;bottom:12px;width:42%;height:72px;border-radius:14px;background:linear-gradient(180deg,rgba(32,213,138,.2),rgba(32,213,138,.03));overflow:hidden}.spark i{position:absolute;left:8px;right:8px;bottom:20px;height:3px;background:#20d58a;transform:skewY(-24deg);box-shadow:18px -14px 0 -1px #20d58a,38px -8px 0 -1px #20d58a,58px -24px 0 -1px #20d58a}
        .actionStrip{display:flex;gap:10px;align-items:flex-start;border:1px solid rgba(32,213,138,.34);background:linear-gradient(135deg,rgba(32,213,138,.13),rgba(8,13,19,.84));border-radius:18px;padding:12px 14px;box-shadow:0 12px 28px rgba(0,0,0,.22)}.actionStrip span{flex:0 0 auto;color:#20d58a;font-size:12px;font-weight:1000;border:1px solid rgba(32,213,138,.45);border-radius:999px;padding:5px 8px}.actionStrip b{font-size:15px;line-height:1.45;color:#eef4ff;font-weight:900}
        .metricGrid,.summaryGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:0}.summaryGrid{grid-template-columns:repeat(3,1fr);margin:10px 0}.metricGrid div,.summaryGrid div{background:rgba(16,24,33,.8);border:1px solid rgba(148,163,184,.13);border-radius:15px;padding:13px}.metricGrid span,.summaryGrid span{display:block;color:#99a5b5;font-size:13px}.metricGrid b,.summaryGrid b{display:block;margin-top:6px;font-size:18px}.sectionTitle{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.sectionTitle:before{content:'';width:4px;height:24px;border-radius:99px;background:#20d58a;margin-right:10px}.sectionTitle b{font-size:19px;flex:1}.sectionTitle span{color:#aab4c2;font-size:13px}.entryMiniGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.entryMini{background:rgba(12,18,26,.9);border:1px solid rgba(148,163,184,.13);border-radius:15px;padding:13px}.entryMini span{display:block;color:#9ea9b8;font-size:13px}.entryMini b{display:block;margin:10px 0;color:#eef4ff;font-size:20px}.entryMini em{display:inline-block;background:rgba(32,213,138,.14);color:#20d58a;border-radius:8px;padding:5px 8px;font-size:12px;font-style:normal;font-weight:800}.compactOrder{padding-top:14px}.orderInputs{display:grid;grid-template-columns:1fr 1fr;gap:8px}.orderInputs label{font-size:12px;color:#94a3b8}.orderInputs input{width:100%;margin-top:5px;border:1px solid rgba(148,163,184,.18);background:#081120;color:white;border-radius:12px;padding:11px}.primary{width:100%;border:0;background:linear-gradient(135deg,#16a34a,#20d58a);color:#05110c;font-weight:1000;border-radius:14px;padding:13px;margin-top:10px}.analysisGrid,.pointGrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.analysisGrid div,.pointGrid div{background:rgba(12,18,26,.82);border:1px solid rgba(148,163,184,.12);border-radius:15px;padding:13px}.analysisGrid span{display:inline-block;width:82px;color:#98a4b3;margin:6px 0}.analysisGrid b{font-weight:900}.pointGrid b{display:block;margin-bottom:10px}.pointGrid p{margin:0;color:#bbc5d3;line-height:1.62}.modelInfo{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px;background:rgba(8,13,19,.62);border-radius:14px;padding:10px}.modelInfo span{text-align:center;color:#9aa6b5;font-size:12px}.modelInfo b{color:#dfe7f3;font-weight:700}
        .holdCard,.pendingCard,.historyLine,.rankLine{border:1px solid rgba(148,163,184,.13);background:rgba(15,23,42,.82);border-radius:15px;padding:12px;margin-bottom:9px}.holdTop,.pendingCard,.historyLine,.rankLine{display:flex;justify-content:space-between;gap:10px;align-items:center}.holdTop span,.pendingCard span,.historyLine span,.rankLine span{display:block;color:#8da0b8;font-size:12px;margin-top:3px}.holdMetrics{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;margin:10px 0;color:#b8c4d6;font-size:13px}.holdActions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.sell,.buy,.pendingCard button{border:0;border-radius:12px;padding:10px;color:white;font-weight:900}.sell{background:#dc2626}.buy{background:#16a34a}.pendingCard button{background:#374151;padding:8px 12px}.loginBox{margin-bottom:12px}
        .authOverlay{position:fixed;inset:0;z-index:250;display:grid;place-items:center;background:rgba(0,0,0,.62);backdrop-filter:blur(8px);padding:18px}.authOverlay>div{position:relative;width:min(420px,100%)}.authClose{position:absolute;right:12px;top:10px;z-index:2;width:34px;height:34px;border:0;border-radius:12px;background:rgba(255,255,255,.08);color:#eaf2ff;font-size:24px}.authPanel{border:1px solid rgba(148,163,184,.17);background:linear-gradient(145deg,rgba(16,22,29,.98),rgba(8,12,17,.98));border-radius:22px;padding:18px;box-shadow:0 24px 70px rgba(0,0,0,.55)}.authPanel.compact{margin-top:12px;padding:14px;box-shadow:none}.authInputs{display:grid;gap:9px}.authInputs input{width:100%;border:1px solid rgba(148,163,184,.2);background:#081120;color:white;border-radius:14px;padding:13px;font-size:15px;outline:none}.authActions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.authActions .primary{margin-top:0}.ghostBtn{border:1px solid rgba(148,163,184,.2);background:rgba(148,163,184,.08);color:#eaf2ff;font-weight:900;border-radius:14px;padding:13px}.authHint,.authMsg{margin:10px 0 0;color:#97a5b7;font-size:12px;line-height:1.45}.authMsg{color:#20d58a;font-weight:800}
        .actionStrip.buy{border-color:rgba(32,213,138,.45);background:linear-gradient(135deg,rgba(32,213,138,.16),rgba(8,13,19,.86))}.actionStrip.buy span{color:#20d58a;border-color:rgba(32,213,138,.55)}
        .actionStrip.wait{border-color:rgba(245,200,75,.35);background:linear-gradient(135deg,rgba(245,200,75,.12),rgba(8,13,19,.86))}.actionStrip.wait span{color:#f5c84b;border-color:rgba(245,200,75,.45)}
        .actionStrip.danger{border-color:rgba(255,84,84,.38);background:linear-gradient(135deg,rgba(255,84,84,.12),rgba(8,13,19,.86))}.actionStrip.danger span{color:#ff5454;border-color:rgba(255,84,84,.45)}
        .paperDashboard{margin:10px 0 12px}.performanceHero{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}.performanceHero div{background:linear-gradient(145deg,rgba(13,20,28,.95),rgba(7,11,16,.95));border:1px solid rgba(148,163,184,.13);border-radius:16px;padding:14px}.performanceHero span{display:block;color:#9ba7b6;font-size:12px}.performanceHero b{display:block;margin-top:5px;font-size:25px;letter-spacing:-.04em}.performanceHero em{display:block;margin-top:5px;color:#8793a4;font-style:normal;font-size:11px}.paperSummary{grid-template-columns:repeat(4,1fr)!important}.paperSummary div{padding:10px 8px}.paperSummary b{font-size:15px!important}
        .bottomNav{position:fixed;left:0;right:0;bottom:0;z-index:100;height:76px;background:rgba(6,10,15,.93);backdrop-filter:blur(18px);border-top:1px solid rgba(148,163,184,.13);display:grid;grid-template-columns:repeat(5,1fr);padding:7px 8px 8px}.bottomNav button{border:0;background:transparent;color:#9ba6b4;border-radius:16px;font-size:25px;font-weight:800}.bottomNav span{display:block;font-size:11px;margin-top:2px}.bottomNav .on{color:#20d58a;background:rgba(32,213,138,.10)}

        .searchScreen{padding-bottom:96px}.searchInput{position:sticky;top:70px;z-index:20;box-shadow:0 14px 30px rgba(0,0,0,.35)}.searchResults{margin-top:10px}
        @media (min-width:760px){.content{max-width:430px}.screen{max-width:430px;margin:0 auto}.metricGrid{grid-template-columns:repeat(2,1fr)}.bottomNav{max-width:430px;left:50%;transform:translateX(-50%);bottom:12px;border-radius:24px;border:1px solid rgba(148,163,184,.16);box-shadow:0 16px 40px rgba(0,0,0,.5)}}
        @media (max-width:480px){.actionStrip{padding:10px 11px;border-radius:15px}.actionStrip span{font-size:11px;padding:4px 7px}.actionStrip b{font-size:13px;line-height:1.35}}
        @media (max-width:480px){.content{padding:12px 10px 18px}.topbar{gap:6px;min-height:68px;padding:10px}.brand b{font-size:21px}.brand em{font-size:13px}.brand span{font-size:11px}.paperTop,.userBtn{padding:8px 11px;font-size:12px}.menuBtn{width:28px}.stockHero{grid-template-columns:1fr}.pricePanel{min-height:104px}.spark{height:58px}.heroLeft h1{font-size:25px}.heroLeft p{font-size:14px;margin-bottom:12px}.judgementRow b{font-size:22px}.premiumMetrics{grid-template-columns:repeat(4,1fr);gap:6px}.metricGrid div{padding:10px 8px}.metricGrid span{font-size:11px}.metricGrid b{font-size:15px}.entryMiniGrid{grid-template-columns:repeat(3,1fr);gap:6px}.entryMini{padding:10px 8px}.entryMini span{font-size:11px}.entryMini b{font-size:16px}.analysisGrid,.pointGrid{grid-template-columns:1fr}.modelInfo{grid-template-columns:1fr 1fr 1fr}.catTabs{grid-template-columns:repeat(2,1fr)}.holdMetrics{grid-template-columns:1fr}.performanceHero{grid-template-columns:1fr 1fr}.performanceHero b{font-size:20px}.paperSummary{grid-template-columns:repeat(2,1fr)!important}.bottomNav{height:74px}.bottomNav button{font-size:23px}.bottomNav span{font-size:10px}}
      `}</style>
    </main>
  );
}
