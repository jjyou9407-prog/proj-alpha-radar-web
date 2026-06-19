'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { hasSupabase, supabase } from '../lib/supabase';

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
  reason: string;
  beginner_note: string;
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
};

type PortfolioItem = {
  id: string;
  symbol: string;
  avgPrice: number;
  qty: number;
};

const demo: Stock[] = [
  {
    symbol: 'NVDA', name: '엔비디아', market: 'US', score: 94, grade: 'S',
    price: 128.4, entry_price: 124.5, stop_price: 118.2, target_price: 139.8,
    reason: 'AI 반도체 섹터 강세 + 거래량 증가 + 실적 모멘텀 우수',
    beginner_note: 'Alpha Radar 분석 결과: S Grade. 좋은 종목이지만 급등 후에는 무리하지 말고 진입가 근처 조정을 기다리는 전략이 안전합니다.',
    change_text: '+2.8%', decision: '강력매수', risk_level: '낮음', action_text: '1차 분할매수 가능. 급등 시 추격매수 금지, 눌림목 우선.',
    trend_score: 24, volume_score: 18, news_score: 14, earnings_score: 14, flow_score: 14, risk_score: 10,
  },
];

function tvSymbol(s: Stock) {
  if (s.market === 'KR') return `KRX:${s.symbol}`;
  const nyse = ['BA','CAT','CRM','CVX','DE','DIS','ETN','GE','GEV','GS','HD','JPM','LLY','LMT','MA','NOC','NVO','ORCL','RTX','SHOP','SNOW','TSM','UBER','V','VRT','WMT','XOM'];
  if (nyse.includes(s.symbol.toUpperCase())) return `NYSE:${s.symbol}`;
  return `NASDAQ:${s.symbol}`;
}

function naverLink(s: Stock) {
  return `https://finance.naver.com/item/main.naver?code=${s.symbol}`;
}

function tradingViewLink(s: Stock) {
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol(s))}`;
}


function safePrice(value: number, fallback: number) {
  if (Number.isFinite(value) && value > 0) return value;
  return fallback;
}

function parsePercent(text?: string) {
  if (!text) return 0;
  const cleaned = String(text).replace('%', '').replace('+', '').replace(',', '.').trim();
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : 0;
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function getTradePlan(stock: Stock) {
  const price = safePrice(stock.price, 0);
  const entry1 = safePrice(stock.entry_price, price * 0.985);

  // v3.3 핵심 수정:
  // 1차/2차/3차 분할매수 구조에서는 손절가가 3차 매수가보다 반드시 아래여야 한다.
  // 이전 버전은 Supabase stop_price를 그대로 써서 3차 매수가보다 손절가가 위에 표시되는 문제가 있었다.
  const entry2 = stock.market === 'KR' ? entry1 * 0.97 : entry1 * 0.965;
  const entry3 = stock.market === 'KR' ? entry1 * 0.94 : entry1 * 0.93;

  const rawStop = safePrice(stock.stop_price, entry1 * 0.88);
  const stopBuffer = stock.market === 'KR' ? 0.965 : 0.96;
  const maxAllowedStop = entry3 * stopBuffer;
  const minAllowedStop = entry1 * 0.78;
  const stop = Math.max(Math.min(rawStop, maxAllowedStop), minAllowedStop);

  const target1 = safePrice(stock.target_price, entry1 * 1.08);
  const target2 = target1 * 1.045;
  const upside = entry1 > 0 ? ((target1 - entry1) / entry1) * 100 : 0;
  const downside = entry1 > 0 ? ((entry1 - stop) / entry1) * 100 : 0;
  const rr = downside > 0 ? upside / downside : 0;
  const currentPremium = entry1 > 0 ? ((price - entry1) / entry1) * 100 : 0;
  const targetGap = price > 0 ? ((target1 - price) / price) * 100 : 0;
  const dayMove = parsePercent(stock.change_text);
  const overheatingPenalty = Math.round(
    clamp(Math.max(dayMove - 4, 0) * 2 + Math.max(currentPremium - 3, 0) * 3 + Math.max(6 - targetGap, 0) * 2, 0, 25)
  );
  const timingScore = clamp(Math.round(stock.score - overheatingPenalty + Math.min(rr, 3) * 4), 0, 100);
  const adjustedStop = rawStop !== stop;
  return { price, entry1, entry2, entry3, stop, rawStop, adjustedStop, target1, target2, upside, downside, rr, currentPremium, targetGap, dayMove, overheatingPenalty, timingScore };
}

function getSignal(stock: Stock) {
  const p = getTradePlan(stock);
  const riskText = String(stock.risk_level ?? '').toLowerCase();
  const highRisk = riskText.includes('높') || riskText.includes('high');
  const danger = stock.score < 60 || p.rr < 1 || p.downside > 16 || p.targetGap < 3 || p.currentPremium > 8 || p.dayMove > 10 || highRisk;
  if (danger) {
    return { label: '🔴 매수금지', tone: 'danger', summary: '지금은 초보자가 따라가기 위험한 자리입니다.' };
  }
  if (stock.score >= 88 && p.timingScore >= 82 && p.rr >= 1.5) {
    return { label: '🔥 적극관심', tone: 'hot', summary: '단, 한 번에 몰빵 금지. 1차만 작게 들어가는 자리입니다.' };
  }
  if (stock.score >= 75 && p.timingScore >= 70 && p.rr >= 1.25) {
    return { label: '🟢 매수가능', tone: 'good', summary: '분할매수 기준으로 접근 가능한 자리입니다.' };
  }
  if (stock.score >= 65) {
    return { label: '🟡 대기', tone: 'wait', summary: '종목은 괜찮지만 진입 타이밍은 조금 더 기다리는 쪽입니다.' };
  }
  return { label: '⚪ 관찰', tone: 'neutral', summary: '관심종목에 두고 점수와 가격 변화를 더 확인하세요.' };
}

function formatPct(n: number) {
  if (!Number.isFinite(n)) return '-';
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

function planClassName(tone: string) {
  if (tone === 'danger') return 'item warn';
  if (tone === 'hot' || tone === 'good') return 'item good';
  return 'item';
}

function ActionPlanCard({ stock, fmt }: { stock: Stock; fmt: (n: number, m: string) => string; }) {
  const plan = getTradePlan(stock);
  const signal = getSignal(stock);
  const forbid: string[] = [];
  if (plan.currentPremium > 8) forbid.push('현재가가 1차 진입가보다 많이 높음: 추격매수 금지');
  if (plan.targetGap < 3) forbid.push('목표가와 너무 가까움: 상승여력 부족');
  if (plan.dayMove > 10) forbid.push('하루 급등폭 과다: 다음 눌림목 대기');
  if (plan.downside > 16) forbid.push('손절폭이 16% 이상: 초보자에게 위험');
  if (plan.rr < 1.2) forbid.push('손익비가 낮음: 벌 자리보다 잃을 자리가 큼');
  if (stock.score < 60) forbid.push('AI 점수 60점 미만: 우선순위 낮음');
  const beginnerBudget = stock.market === 'KR' ? '10만원' : '$100';

  return (
    <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
      <div className={planClassName(signal.tone)}>
        <b>🚦 지금 신호: {signal.label}</b>
        <span className="muted">타이밍 점수 {plan.timingScore}점 · 과열 감점 -{plan.overheatingPenalty}점 · {signal.summary}</span>
      </div>

      <div className="item good">
        <b>🎯 오늘 행동</b>
        <span className="muted">1차 매수: {fmt(plan.entry1, stock.market)} 이하</span>
        <span className="muted">2차 매수: {fmt(plan.entry2, stock.market)} 근처</span>
        <span className="muted">3차 매수: {fmt(plan.entry3, stock.market)} 근처</span>
        <span className="muted">손절: {fmt(plan.stop, stock.market)} 종가 이탈 시 정리</span>
        {plan.adjustedStop && <span className="muted">※ 3차 매수가보다 아래로 자동 보정됨</span>}
        <span className="muted">1차 목표: {fmt(plan.target1, stock.market)} · 최종 목표: {fmt(plan.target2, stock.market)}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <div className="num"><span>예상수익</span><b style={{ color: '#22c55e' }}>{formatPct(plan.upside)}</b></div>
        <div className="num"><span>예상손실</span><b style={{ color: '#ef4444' }}>-{plan.downside.toFixed(1)}%</b></div>
        <div className="num"><span>손익비</span><b>{plan.rr ? `${plan.rr.toFixed(2)} : 1` : '-'}</b></div>
      </div>

      <div className="item">
        <b>👶 초보자 따라하기</b>
        <span className="muted">{beginnerBudget} 기준: 1차 30%, 2차 30%, 3차 40%만 사용. 몰빵 금지.</span>
        <span className="muted">손절은 장중 터치가 아니라 종가 이탈 기준으로 판단. 단, 악재 뉴스가 터지면 예외.</span>
        <span className="muted">1차 목표 도달 시 절반 익절, 나머지는 본전 이상에서 관리.</span>
      </div>

      <div className={forbid.length ? 'item warn' : 'item good'}>
        <b>{forbid.length ? '🚫 매수금지 조건' : '✅ 초보자 진입 체크'}</b>
        {(forbid.length ? forbid : ['현재 기준 큰 금지 조건은 없음. 그래도 1차 소액 분할만 권장.']).map((x) => (
          <span className="muted" key={x}>• {x}</span>
        ))}
      </div>
    </div>
  );
}

function TradingViewUSChart({ stock }: { stock: Stock }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = '';

    const widgetBox = document.createElement('div');
    widgetBox.className = 'tradingview-widget-container__widget';
    containerRef.current.appendChild(widgetBox);

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [[stock.name, `${tvSymbol(stock)}|1D`]],
      chartOnly: false,
      width: '100%',
      height: 520,
      locale: 'kr',
      colorTheme: 'dark',
      autosize: false,
      showVolume: true,
      showMA: true,
      hideDateRanges: false,
      hideMarketStatus: false,
      hideSymbolLogo: false,
      scalePosition: 'right',
      scaleMode: 'Normal',
      fontFamily: '-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif',
      fontSize: '10',
      noTimeScale: false,
      valuesTracking: '1',
      changeMode: 'price-and-percent',
      chartType: 'candlesticks',
      maLineColor: '#2962FF',
      maLineWidth: 1,
      maLength: 9,
      lineWidth: 2,
      lineType: 0,
      dateRanges: ['1d|1', '1m|30', '3m|60', '12m|1D', '60m|1W', 'all|1M'],
    });
    containerRef.current.appendChild(script);
    return () => { if (containerRef.current) containerRef.current.innerHTML = ''; };
  }, [stock.symbol, stock.name, stock.market]);

  return (
    <div>
      <div className="item good" style={{ marginBottom: 10 }}>
        <b>{stock.name} · {stock.symbol}</b>
        <span className="muted">TradingView · {tvSymbol(stock)} · {stock.grade ?? 'C'} Grade · {stock.score}점</span>
      </div>
      <div ref={containerRef} className="tradingview-widget-container" style={{ width: '100%', height: 520, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, overflow: 'hidden', background: '#111' }} />
      <div style={{ marginTop: 10 }}>
        <a href={tradingViewLink(stock)} target="_blank" rel="noreferrer" style={{ display: 'inline-block', padding: '10px 14px', borderRadius: 10, background: '#2563eb', color: '#fff', textDecoration: 'none', fontWeight: 'bold', fontSize: 13 }}>TradingView 크게 열기</a>
      </div>
    </div>
  );
}

function KoreanPlanPanel({ stock, fmt }: { stock: Stock; fmt: (n: number, m: string) => string; }) {
  return (
    <div style={{ width: '100%', minHeight: 420, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, background: 'linear-gradient(180deg, rgba(18,24,38,0.98), rgba(10,12,18,0.98))', padding: 16, boxSizing: 'border-box' }}>
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>KOREA STOCK · {tvSymbol(stock)}</div>
        <div style={{ fontSize: 22, fontWeight: 900, color: '#fff' }}>{stock.name}</div>
        <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 4 }}>{stock.symbol} · {stock.market}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        <div className="num"><span>현재가</span><b>{fmt(stock.price, stock.market)}</b></div>
        <div className="num"><span>등락률</span><b>{stock.change_text || '관찰'}</b></div>
        <div className="num"><span>Alpha Grade</span><b>{stock.grade ?? 'C'}</b></div>
        <div className="num"><span>점수</span><b>{stock.score}점</b></div>
      </div>

      <div style={{ height: 150, borderRadius: 14, background: 'linear-gradient(135deg, rgba(16,185,129,0.18), rgba(59,130,246,0.08), rgba(239,68,68,0.12))', border: '1px solid rgba(255,255,255,0.08)', position: 'relative', overflow: 'hidden', marginBottom: 14 }}>
        <svg width="100%" height="150" viewBox="0 0 400 150" preserveAspectRatio="none" style={{ position: 'absolute', left: 0, top: 0 }}>
          <polyline points="0,115 40,108 80,112 120,92 160,96 200,70 240,76 280,52 320,60 360,40 400,45" fill="none" stroke="rgba(34,197,94,0.95)" strokeWidth="4" />
          <polyline points="0,125 40,118 80,122 120,102 160,106 200,80 240,86 280,62 320,70 360,50 400,55" fill="none" stroke="rgba(34,197,94,0.15)" strokeWidth="12" />
        </svg>
        <div style={{ position: 'absolute', left: 14, top: 12, color: '#d1fae5', fontSize: 12, fontWeight: 700 }}>AI 추세 시각화</div>
        <div style={{ position: 'absolute', right: 14, bottom: 12, color: '#fff', fontSize: 12, opacity: 0.8 }}>실제 매매 전 외부 차트 확인 필요</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
        <div className="num"><span>진입가</span><b>{fmt(stock.entry_price, stock.market)}</b></div>
        <div className="num"><span>손절가</span><b>{fmt(stock.stop_price, stock.market)}</b></div>
        <div className="num"><span>목표가</span><b>{fmt(stock.target_price, stock.market)}</b></div>
      </div>

      <div className="item good" style={{ marginBottom: 10 }}><b>판단 요약</b><span className="muted">{stock.action_text || '추가 확인 필요'}</span></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <a href={tradingViewLink(stock)} target="_blank" rel="noreferrer" style={{ display: 'inline-block', padding: '10px 14px', borderRadius: 10, background: '#2563eb', color: '#fff', textDecoration: 'none', fontWeight: 'bold', fontSize: 13 }}>TradingView 열기</a>
        <a href={naverLink(stock)} target="_blank" rel="noreferrer" style={{ display: 'inline-block', padding: '10px 14px', borderRadius: 10, background: '#16a34a', color: '#fff', textDecoration: 'none', fontWeight: 'bold', fontSize: 13 }}>네이버증권 열기</a>
      </div>
    </div>
  );
}

function ChartPanel({ stock, fmt }: { stock: Stock; fmt: (n: number, m: string) => string; }) {
  if (stock.market === 'US') return <TradingViewUSChart key={`${stock.market}-${stock.symbol}`} stock={stock} />;
  return <KoreanPlanPanel key={`${stock.market}-${stock.symbol}`} stock={stock} fmt={fmt} />;
}

function ScoreBreakdown({ stock }: { stock: Stock }) {
  const rows = [
    ['추세', stock.trend_score ?? 0, 25],
    ['거래량', stock.volume_score ?? 0, 20],
    ['뉴스', stock.news_score ?? 0, 15],
    ['실적', stock.earnings_score ?? 0, 15],
    ['수급', stock.flow_score ?? 0, 15],
    ['리스크', stock.risk_score ?? 0, 10],
  ];

  return (
    <div className="card">
      <h2>📊 AI 점수 세부내역</h2>
      {rows.map(([label, value, max]) => {
        const pct = Number(max) ? Math.round((Number(value) / Number(max)) * 100) : 0;
        return (
          <div key={String(label)} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 5 }}>
              <b>{label}</b>
              <span className="muted">{value} / {max}</span>
            </div>
            <div style={{ height: 8, background: 'rgba(255,255,255,0.08)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg,#2563eb,#22c55e)', borderRadius: 999 }} />
            </div>
          </div>
        );
      })}
      <div className="item good" style={{ marginTop: 12 }}>
        <b>총점 {stock.score}점</b>
        <span className="muted">{stock.grade ?? 'C'} Grade · {stock.decision || '관망'}</span>
      </div>
    </div>
  );
}

function PortfolioPanel({ stocks, fmt }: { stocks: Stock[]; fmt: (n: number, m: string) => string; }) {
  const [symbol, setSymbol] = useState('');
  const [avgPrice, setAvgPrice] = useState('');
  const [qty, setQty] = useState('');
  const [items, setItems] = useState<PortfolioItem[]>([]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('alphaRadarPortfolio');
      if (saved) setItems(JSON.parse(saved));
    } catch {}
  }, []);

  useEffect(() => {
    localStorage.setItem('alphaRadarPortfolio', JSON.stringify(items));
  }, [items]);

  const findStock = (code: string) => {
    const key = code.trim().toUpperCase();
    return stocks.find(
      (s) =>
        s.symbol.toUpperCase() === key ||
        s.name.toLowerCase() === code.trim().toLowerCase()
    );
  };

  const addItem = () => {
    const raw = symbol.trim();
    const matched = findStock(raw);
    const code = (matched?.symbol || raw).toUpperCase();
    const avg = Number(avgPrice.replace(/,/g, ''));
    const amount = Number(qty.replace(/,/g, '') || '1');

    if (!code || !avg || avg <= 0 || !amount || amount <= 0) {
      alert('종목코드, 평단가, 수량을 확인해줘.');
      return;
    }

    setItems((prev) => [
      {
        id: `${code}-${Date.now()}`,
        symbol: code,
        avgPrice: avg,
        qty: amount,
      },
      ...prev,
    ]);

    setSymbol('');
    setAvgPrice('');
    setQty('');
  };

  const analyzedItems = items.map((item) => {
    const stock = findStock(item.symbol);
    const currentValue = stock ? stock.price * item.qty : 0;
    const buyValue = item.avgPrice * item.qty;
    const pnlMoney = stock ? currentValue - buyValue : 0;
    const pnlPct = stock && buyValue ? (pnlMoney / buyValue) * 100 : 0;
    return { item, stock, currentValue, buyValue, pnlMoney, pnlPct };
  });

  const totalBuy = analyzedItems.reduce((sum, row) => sum + row.buyValue, 0);
  const totalValue = analyzedItems.reduce((sum, row) => sum + row.currentValue, 0);
  const totalPnl = totalValue - totalBuy;
  const totalPnlPct = totalBuy ? (totalPnl / totalBuy) * 100 : 0;

  const moneyFmt = (n: number, market?: string) => {
    if (!Number.isFinite(n)) return '-';
    return market === 'US'
      ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
      : `${Math.round(n).toLocaleString()}원`;
  };

  const portfolioDecision = (stock: Stock | undefined, pnlPct: number) => {
    if (!stock) return '데이터 대기';
    const signal = getSignal(stock);
    const plan = getTradePlan(stock);
    if (pnlPct <= -8 && (stock.score < 70 || signal.tone === 'danger')) return '손절/비중축소 우선';
    if (pnlPct >= 15 && plan.targetGap < 5) return '절반 익절 유리';
    if (pnlPct >= 10 && signal.tone === 'danger') return '수익 보호 우선';
    if (stock.score >= 85 && signal.tone !== 'danger') return '강한 보유';
    if (stock.score >= 70) return '보유 우위';
    if (stock.score >= 60) return '주의 관찰';
    return '비중 축소 검토';
  };

  return (
    <div className="card">
      <h2>📊 포트폴리오</h2>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.2fr 1fr 1fr',
          gap: 8,
          marginBottom: 8,
        }}
      >
        <input
          list="alpha-radar-stock-list"
          placeholder="종목코드/이름"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          style={{
            padding: 10,
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,0.12)',
            background: '#0b1220',
            color: '#fff',
            minWidth: 0,
          }}
        />
        <input
          placeholder="평단가"
          value={avgPrice}
          onChange={(e) => setAvgPrice(e.target.value)}
          style={{
            padding: 10,
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,0.12)',
            background: '#0b1220',
            color: '#fff',
            minWidth: 0,
          }}
        />
        <input
          placeholder="수량"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          style={{
            padding: 10,
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,0.12)',
            background: '#0b1220',
            color: '#fff',
            minWidth: 0,
          }}
        />
      </div>

      <datalist id="alpha-radar-stock-list">
        {stocks.map((s) => (
          <option key={`pf-option-${s.market}-${s.symbol}`} value={s.symbol}>
            {s.name} · {s.market}
          </option>
        ))}
      </datalist>

      <button className="tab" onClick={addItem} style={{ width: '100%', marginBottom: 12 }}>
        보유종목 추가
      </button>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: 8,
          marginBottom: 12,
        }}
      >
        <div className="num">
          <span>투입금</span>
          <b>{items.length ? Math.round(totalBuy).toLocaleString() : '-'}</b>
        </div>
        <div className="num">
          <span>평가금</span>
          <b>{items.length ? Math.round(totalValue).toLocaleString() : '-'}</b>
        </div>
        <div className="num">
          <span>총 손익률</span>
          <b style={{ color: totalPnl >= 0 ? '#22c55e' : '#ef4444' }}>
            {items.length ? `${totalPnlPct.toFixed(2)}%` : '-'}
          </b>
        </div>
      </div>

      {items.length === 0 && (
        <div className="item">
          <b>보유종목 등록 준비중</b>
          <span className="muted">종목코드와 평단가를 입력하면 수익률과 AI 재평가가 표시됩니다.</span>
        </div>
      )}

      {analyzedItems.map(({ item, stock, currentValue, buyValue, pnlMoney, pnlPct }) => {
        const positive = pnlMoney >= 0;
        const targetPct = stock && item.avgPrice ? ((stock.target_price - item.avgPrice) / item.avgPrice) * 100 : 0;
        const stopPct = stock && item.avgPrice ? ((stock.stop_price - item.avgPrice) / item.avgPrice) * 100 : 0;

        return (
          <div
            key={item.id}
            className={positive ? 'item good' : 'item warn'}
            style={{ marginBottom: 10 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <b>{stock ? `${stock.name} · ${stock.symbol}` : item.symbol}</b>
              <b style={{ color: positive ? '#22c55e' : '#ef4444' }}>
                {stock ? `${pnlPct.toFixed(2)}%` : '분석 대기'}
              </b>
            </div>

            <span className="muted">
              평단 {item.avgPrice.toLocaleString()} · 수량 {item.qty.toLocaleString()} · 현재{' '}
              {stock ? fmt(stock.price, stock.market) : '데이터 없음'}
            </span>

            <span className="muted">
              매입 {moneyFmt(buyValue, stock?.market)} · 평가 {stock ? moneyFmt(currentValue, stock.market) : '-'} · 손익{' '}
              {stock ? moneyFmt(pnlMoney, stock.market) : '-'}
            </span>

            {stock && (
              <span className="muted">
                AI 재평가: {portfolioDecision(stock, pnlPct)} · {stock.grade ?? 'C'} Grade · 목표까지{' '}
                {targetPct.toFixed(1)}% · 손절선 {stopPct.toFixed(1)}%
              </span>
            )}

            <button
              onClick={() => setItems((prev) => prev.filter((x) => x.id !== item.id))}
              style={{
                marginTop: 8,
                padding: '6px 10px',
                borderRadius: 8,
                border: 0,
                background: '#374151',
                color: '#fff',
                cursor: 'pointer',
              }}
            >
              삭제
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default function Page() {
  const [stocks, setStocks] = useState<Stock[]>(demo);
  const [tab, setTab] = useState('ALL');
  const [sel, setSel] = useState<Stock>(demo[0]);
  const [mode, setMode] = useState(hasSupabase ? 'Cloud 연결' : 'Demo 모드');
  const [query, setQuery] = useState('');
  const [watchSymbols, setWatchSymbols] = useState<string[]>([]);
  const [beginnerMode, setBeginnerMode] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const detailRef = useRef<HTMLDivElement | null>(null);

  const selectStock = (stock: Stock) => {
    setSel(stock);
    window.setTimeout(() => {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  };

  useEffect(() => {
    try {
      const saved = localStorage.getItem('alphaRadarWatchlist');
      if (saved) setWatchSymbols(JSON.parse(saved));
    } catch {}
  }, []);

  useEffect(() => {
    localStorage.setItem('alphaRadarWatchlist', JSON.stringify(watchSymbols));
  }, [watchSymbols]);

  useEffect(() => {
    async function load(keepSelection = false) {
      if (!hasSupabase || !supabase) return;
      const { data, error } = await supabase.from('rankings').select('*').order('score', { ascending: false }).limit(120);
      if (error) {
        console.error('Supabase rankings load error:', error);
        setMode('Supabase 오류');
        return;
      }
      if (data && data.length) {
        const mapped = data.map((r: any) => ({
          symbol: String(r.symbol ?? '').trim(), name: String(r.name ?? '').trim(), market: String(r.market ?? '').trim().toUpperCase(), score: Number(r.score ?? 0), grade: r.grade ?? 'C',
          price: Number(r.price ?? 0), entry_price: Number(r.entry_price ?? 0), stop_price: Number(r.stop_price ?? 0), target_price: Number(r.target_price ?? 0),
          reason: r.reason ?? '', beginner_note: r.beginner_note ?? '', change_text: r.change_text ?? '관찰', decision: r.decision ?? '관망', risk_level: r.risk_level ?? '보통', action_text: r.action_text ?? '추가 확인 필요',
          trend_score: Number(r.trend_score ?? 0), volume_score: Number(r.volume_score ?? 0), news_score: Number(r.news_score ?? 0), earnings_score: Number(r.earnings_score ?? 0), flow_score: Number(r.flow_score ?? 0), risk_score: Number(r.risk_score ?? 0),
        }));
        setStocks(mapped);
        setSel((prev) => {
          if (!keepSelection) return mapped[0];
          return mapped.find((x: Stock) => x.market === prev.market && x.symbol === prev.symbol) ?? mapped[0];
        });
        setMode('Supabase 실시간 연결');
        setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
      }
    }
    load(false);
    const timer = setInterval(() => load(true), 5000);
    return () => clearInterval(timer);
  }, []);

  const marketCounts = useMemo(() => ({
    ALL: stocks.length,
    US: stocks.filter((s) => s.market === 'US').length,
    KR: stocks.filter((s) => s.market === 'KR').length,
  }), [stocks]);

  const ranked = stocks
    .filter((s) => tab === 'ALL' || s.market === tab)
    .sort((a, b) => {
      const ap = getTradePlan(a);
      const bp = getTradePlan(b);
      return beginnerMode ? bp.timingScore - ap.timingScore : b.score - a.score;
    });

  // v3.4: 초보자 모드에서도 한국/미국 TOP7이 비어 보이지 않게 한다.
  // 먼저 매수금지 아닌 종목을 우선 표시하고, 7개가 부족하면 관망/매수금지도 뒤에 채운다.
  const preferred = beginnerMode ? ranked.filter((s) => getSignal(s).tone !== 'danger') : ranked;
  const fallback = beginnerMode ? ranked.filter((s) => getSignal(s).tone === 'danger') : [];
  const filtered = [...preferred, ...fallback].slice(0, 7);

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return stocks.filter((s) => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)).slice(0, 20);
  }, [query, stocks]);

  const watchlist = stocks.filter((s) => watchSymbols.includes(`${s.market}-${s.symbol}`));
  const toggleWatch = (s: Stock) => {
    const key = `${s.market}-${s.symbol}`;
    setWatchSymbols((prev) => prev.includes(key) ? prev.filter((x) => x !== key) : [key, ...prev]);
  };
  const isWatched = watchSymbols.includes(`${sel.market}-${sel.symbol}`);

  const fmt = (n: number, m: string) => m === 'KR' ? `${Math.round(n).toLocaleString()}원` : `$${Number(n).toLocaleString()}`;
  const gradeColor = (grade?: string) => {
    if (grade === 'S') return '#ff2d2d';
    if (grade === 'A') return '#ff6b35';
    if (grade === 'B') return '#ffd166';
    if (grade === 'C') return '#8ecae6';
    return '#999';
  };

  return (
    <main className="wrap">
      <div className="top">
        <div className="brand"><h1>Alpha Radar AI</h1><p>Made by YHJ · v3.5 Scroll + 5s Auto Refresh</p><p>실시간 데이터 · 진입 타이밍 · 초보자 행동 가이드 · 손익비 자동 계산</p></div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}><button className="tab" onClick={() => setBeginnerMode((v) => !v)}>{beginnerMode ? '👶 초보자 모드 ON' : '⚡ 전체 모드'}</button><div className="badge">{mode}{lastUpdated ? ` · ${lastUpdated}` : ''}</div></div>
      </div>

      <section className="grid">
        <div className="card">
          <h2>🏆 오늘의 TOP7</h2><div className="item good" style={{ marginBottom: 12 }}><b>{beginnerMode ? '👶 초보자 수익 모드' : '⚡ 전체 랭킹 모드'}</b><span className="muted">{beginnerMode ? '추천 종목을 우선 표시하고, 부족하면 관망/금지 종목도 뒤에 채워 TOP7을 유지합니다.' : '전체 종목을 AI 점수 순서로 보여줍니다.'}</span></div>
          <div style={{ position: 'relative', marginBottom: 12 }}>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="종목 검색: NVDA, 삼성전자, 한화오션" style={{ width: '100%', padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(255,255,255,0.12)', background: '#0b1220', color: '#fff', boxSizing: 'border-box' }} />
            {searchResults.length > 0 && (
              <div style={{ position: 'absolute', zIndex: 10, left: 0, right: 0, top: 48, background: '#111827', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12, overflow: 'hidden' }}>
                {searchResults.map((s) => (
                  <div key={`search-${s.market}-${s.symbol}`} onClick={() => { selectStock(s); setQuery(''); }} style={{ padding: 10, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    <b>{s.name} · {s.symbol}</b><span className="muted">{s.market} · {s.score}점</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="tabs"><button className="tab" onClick={() => setTab('ALL')}>전체 {marketCounts.ALL}</button><button className="tab" onClick={() => setTab('US')}>미국 {marketCounts.US}</button><button className="tab" onClick={() => setTab('KR')}>한국 {marketCounts.KR}</button></div>

          {filtered.map((s, i) => {
            const signal = getSignal(s);
            const plan = getTradePlan(s);
            return (
              <div className="rank" key={`${s.market}-${s.symbol}`} onClick={() => selectStock(s)}>
                <strong>{i + 1}</strong>
                <div><b>{s.name}</b><div className="muted">{s.symbol} · {s.market}</div><div style={{ color: gradeColor(s.grade), fontSize: '12px', fontWeight: 'bold', marginTop: 2 }}>⭐ {s.grade ?? 'C'} Grade · 타이밍 {plan.timingScore}점</div></div>
                <div className="score">{s.score}점</div><div className="pill">{signal.label}</div>
              </div>
            );
          })}

          <div className="detail" ref={detailRef}>
            <h3>{sel.name} 상세 분석</h3>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 12 }}>
              <div style={{ color: gradeColor(sel.grade), fontWeight: 'bold', fontSize: '20px' }}>📈 Alpha Grade {sel.grade ?? 'C'}</div>
              <button onClick={() => toggleWatch(sel)} style={{ padding: '8px 12px', borderRadius: 10, border: 0, background: isWatched ? '#f59e0b' : '#374151', color: '#fff', fontWeight: 'bold' }}>{isWatched ? '★ 관심해제' : '☆ 관심추가'}</button>
            </div>
            <p className="muted">{sel.reason}</p>
            <div className="nums"><div className="num"><span>현재가</span><b>{fmt(sel.price, sel.market)}</b></div><div className="num"><span>진입가</span><b>{fmt(sel.entry_price, sel.market)}</b></div><div className="num"><span>손절가</span><b>{fmt(sel.stop_price, sel.market)}</b></div><div className="num"><span>목표가</span><b>{fmt(sel.target_price, sel.market)}</b></div></div>
            <div className="item" style={{ marginTop: 12 }}><b>🎯 AI 판단</b><span className="muted">{sel.decision || '관망'}</span></div>
            <div className="item" style={{ marginTop: 8 }}><b>⚠️ 위험도</b><span className="muted">{sel.risk_level || '보통'}</span></div>
            <div className="item good" style={{ marginTop: 8 }}><b>📌 행동 가이드</b><span className="muted">{sel.action_text || '추가 확인 필요'}</span></div>
            <ActionPlanCard stock={sel} fmt={fmt} />
            <p>💡 {sel.beginner_note}</p>
          </div>
        </div>

        <div className="list">
          <div className="card"><h2>⭐ 관심종목</h2>{watchlist.length ? watchlist.map((s) => (<div key={`watch-${s.market}-${s.symbol}`} className="item good" style={{ marginBottom: 8, cursor: 'pointer' }} onClick={() => selectStock(s)}><b>{s.name} · {s.symbol}</b><span className="muted">{s.grade ?? 'C'} Grade · 점수 {s.score}점 · 목표가 {fmt(s.target_price, s.market)}</span></div>)) : stocks.slice(0, 3).map((s) => (<div key={`watch-auto-${s.market}-${s.symbol}`} className="item good" style={{ marginBottom: 8 }}><b>{s.name} · {s.symbol}</b><span className="muted">추천 관심 · {s.grade ?? 'C'} Grade · 점수 {s.score}점</span></div>))}</div>
          <ScoreBreakdown stock={sel} />
          <div className="card"><h2>📰 뉴스 요약</h2>{stocks.slice(0, 3).map((s) => (<div className="item" key={`news-${s.market}-${s.symbol}`} style={{ marginBottom: 8 }}><b>{s.name} · {s.symbol}</b><span className="muted">{s.reason || '뉴스/실적/추세 데이터 분석 중'}</span></div>))}</div>
          <div className="card"><h2>🚨 위험경고</h2><div className="item warn"><b>{stocks.filter((s) => getSignal(s).tone === 'danger').length}개 종목 매수금지</b><span className="muted">급등/손익비 부족/목표가 근접 종목은 초보자 모드에서 자동 제외됩니다.</span></div><div className="item good" style={{ marginTop: 8 }}><b>{stocks.filter((s) => getSignal(s).tone === 'hot' || getSignal(s).tone === 'good').length}개 종목 진입 후보</b><span className="muted">점수뿐 아니라 손익비와 진입가 괴리를 함께 통과한 종목입니다.</span></div></div>
          <PortfolioPanel stocks={stocks} fmt={fmt} />
          <div className="card chart-card"><h2>📈 차트 & 매매 플랜</h2><ChartPanel stock={sel} fmt={fmt} /></div>
        </div>
      </section>

      <div className="footer">Alpha Radar AI v3.5 · 투자 참고용이며 매수/매도 책임은 사용자에게 있습니다.</div>
    </main>
  );
}
